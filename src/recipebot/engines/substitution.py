"""Evidence-based ingredient substitution.

1. Find the lines to replace in the recipe, and the ingredient's roles there (roles.yaml).
2. Collect evidence from the dataset:
   - direct: ingredient lines that offer a choice ("1 cup butter or margarine") and
     instruction sentences that mention substituting;
   - comparative (indirect): among similar recipes, ingredients that are much more common
     in those WITHOUT the target than in those with it.
   Candidates that break a restriction are dropped; uncertain ones are flagged.
3. Describe each candidate: which of the target's roles it provides (fully, partly, not),
   and how much of it to use, from the dataset only:
   - supported: an "X or Y" line or a note gives the amount ("2 eggs or 1/2 cup egg
     substitute"), or offers the alternative at the same amount;
   - estimated: a recipe of the same dish without the target uses the candidate, and its
     amount is scaled to this recipe by a shared ingredient (usually flour);
   - unknown: "Quantity not established by the dataset." Never a guessed 1:1.
4. Rank the candidates by fixed, explainable rules (RANKING_RULE) and select the first one
   that provides the target's main role. Code does the choosing; the LLM only rewrites the
   steps that mention the target, and code checks that rewrite.
5. Check the moisture balance against recipes of the same dish, predict the texture from
   the roles, and label the adaptation: supported, experimental, or incomplete (quantity
   unknown). If no candidate qualifies, no adapted recipe is produced.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, Field, ValidationError

from recipebot.engines.search import SearchIndex, tokenize
from recipebot.engines.store import RecipeStore
from recipebot.llm.base import LLMClient, LLMUnavailable
from recipebot.nlp.ingredient_parser import parse_line, take_quantity
from recipebot.nlp.steps import instruction_lines, split_sentences
from recipebot.nlp.text import fold

NEIGHBOURS = 300  # similar recipes compared for indirect evidence
MIN_COMPARATIVE_SUPPORT = 3  # a candidate must appear in at least this many recipes
MIN_LIFT = 1.5
STRENGTH_ORDER = {"strong": 0, "moderate": 1, "weak": 2, "none": 3, "conflicting": 4,
                  "excluded": 5}
CLOSENESS_ORDER = {"direct": 0, "same dish": 1, "related": 2}
QUANTITY_ORDER = {"supported": 0, "estimated": 1, "unknown": 2}
MIN_NEIGHBOURS = 15  # below this, the similar-recipe set is broadened
UNKNOWN_QUANTITY = "Quantity not established by the dataset."
RANKING_RULE = (
    "1) candidates that may break a restriction rank last; 2) a candidate must provide the "
    "ingredient's main role to be selected; 3) evidence strength; 4) evidence type: direct, "
    "then same dish, then related recipes; 5) how many of the ingredient's roles it covers; "
    "6) number of supporting recipes; 7) quantity: from the dataset, estimated, unknown")
QUANTITY_TAG = {"supported": "quantity from the dataset", "estimated": "estimated quantity",
                "unknown": "quantity not established by the dataset"}
_ALTERNATIVE = re.compile(r"\s+(?:and/or|or)\s+")


@dataclass
class Quantity:
    """How much of the substitute to use, and how sure the dataset is about it."""

    status: str = "unknown"  # supported | estimated | unknown
    text: str = ""  # "1/2 cup"; empty when unknown
    amount: float | None = None  # in ml or g, for the whole recipe
    dimension: str | None = None
    basis: str = UNKNOWN_QUANTITY
    sources: list[tuple[str, str]] = field(default_factory=list)  # (recipe ID, line)
    same_as_original: bool = False  # offered by the dataset at the target's own amount


@dataclass
class Candidate:
    name: str
    direct: int = 0  # recipes where it is offered as an alternative to the target
    direct_examples: list[tuple[str, str]] = field(default_factory=list)  # (recipe ID, line)
    direct_lines: list[tuple[str, str]] = field(default_factory=list)  # all, for quantities
    comparative_support: int = 0  # similar recipes without the target that use it
    share_without: float = 0.0
    share_with: float = 0.0
    comparative_examples: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    strength: str = "weak"
    fit: str = "unknown"  # good | partial | unknown | poor: do its roles match the target's?
    comparative_scope: str = ""  # "same dish" or the wider dish type
    coverage: dict[str, str] = field(default_factory=dict)  # target role -> full|partial|none
    covers_main: bool = False  # provides the target's main role, at least partly
    quantity: Quantity = field(default_factory=Quantity)
    supporting: list[dict] = field(default_factory=list)  # {id, title, kind, line}

    @property
    def closeness(self) -> str:
        if self.direct:
            return "direct"
        return "same dish" if self.comparative_scope == "same dish" else "related"

    @property
    def support(self) -> int:
        return self.direct + self.comparative_support

    def evidence_type(self) -> str:
        if self.direct:
            return f"direct: {self.direct} recipe(s) offer it as an alternative"
        if self.comparative_support:
            where = ("same-dish" if self.comparative_scope == "same dish"
                     else self.comparative_scope.replace(" recipes", ""))
            return f"indirect: used by {self.comparative_support} {where} recipe(s) without it"
        return "no supporting recipes"

    def coverage_text(self) -> str:
        if not self.coverage:
            return "roles unknown (not in the role table)"
        parts = [f"{role} {'fully' if how == 'full' else 'partly'}"
                 for role, how in self.coverage.items() if how != "none"]
        missing = [role for role, how in self.coverage.items() if how == "none"]
        text = ", ".join(parts) or "none of its roles"
        return text + (f"; not {', '.join(missing)}" if missing else "")

    def coverage_score(self) -> float:
        return sum({"full": 1.0, "partial": 0.5}.get(how, 0.0) for how in self.coverage.values())

    def limitation(self) -> str:
        if self.strength == "conflicting":
            return "may contain a restricted ingredient, so it is never chosen automatically"
        if self.direct and self.direct < 2:
            return "offered as an alternative in a single recipe only"
        if self.direct:
            return "the recipes offer it as an option; none reports a tested result"
        if self.comparative_support:
            few = " (a single recipe)" if self.comparative_support == 1 else ""
            return (f"indirect{few}: those recipes use it and lack the target, but may differ "
                    "in other ways and do not call it a replacement")
        return "no supporting recipes in the dataset"


@dataclass
class Evidence:
    target: str
    target_lines: list[tuple[int, str]]  # (position in the ingredient list, text)
    target_names: list[str]  # canonical names being replaced
    restricted: list[str]  # categories / names the substitute must not contain
    roles: dict[str, list[str]]
    baked: bool
    neighbours: int = 0
    neighbours_without: int = 0
    comparison_scope: str = ""  # which recipes were compared, in words
    dish: str = ""  # the dish label used for same-dish comparisons ("banana bread")
    same_dish_ids: list[str] = field(default_factory=list)
    same_dish_without: list[tuple[str, str]] = field(default_factory=list)  # (ID, title)
    # What removing the target is likely to change, from its roles (roles.yaml). Always
    # given, so the trade-off question is answered even when no substitute is proposed.
    expected_effects: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)  # (recipe ID, sentence)
    ranking_notes: list[str] = field(default_factory=list)  # why #1 ranks above the others
    uncertainty: list[str] = field(default_factory=list)  # ties, equally weak evidence
    recipe_lines: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def best_strength(self) -> str:
        return self.candidates[0].strength if self.candidates else "none"

    @property
    def noun(self) -> str:
        """The ingredient's name for "the egg's role" (the user may have said "eggs")."""
        return next(iter(self.roles), self.target)

    @property
    def main_roles(self) -> list[str]:
        return list(dict.fromkeys(roles[0] for roles in self.roles.values() if roles))

    @property
    def all_roles(self) -> list[str]:
        return list(dict.fromkeys(r for roles in self.roles.values() for r in roles))


@dataclass
class MoistureCheck:
    """Wet ingredients in the recipe vs recipes of the same dish (by volume, per flour)."""

    existing: list[str] = field(default_factory=list)  # wet lines already in the recipe
    ratio: float | None = None  # wet volume / flour volume in this recipe
    baseline: float | None = None  # median of the same ratio in same-dish recipes
    baseline_n: int = 0
    after: float | None = None  # with the substitute's (estimated) amount added
    risk: str = "unknown"  # high | possible | low | unknown | none
    notes: list[str] = field(default_factory=list)


class StepEdit(BaseModel):  # Pydantic: the LLM's JSON is validated against it
    number: int = Field(description="the instruction step number being rewritten")
    text: str = Field(description="the rewritten step")


class AdaptationPlan(BaseModel):
    """What the LLM returns: rewritten steps only. Code has already chosen the substitute
    and its quantity, and applies these edits to the original steps."""

    step_edits: list[StepEdit] = Field(description="one edit per step that mentions the target")


@dataclass
class AdaptedRecipe:
    substitute: str
    ingredients: list[str]  # the full adapted list; only the target lines differ
    instructions: list[str]
    changes: list[str]  # each change, and the quantity's source


@dataclass
class SubstitutionResult:
    recipe_id: str
    title: str
    evidence: Evidence
    adapted: AdaptedRecipe | None = None
    method: str = "none"  # how the steps were rewritten: llm | fallback (rules) | none
    validation_errors: list[str] = field(default_factory=list)
    message: str = ""  # why no adaptation was made, if none was
    original_ingredients: list[str] = field(default_factory=list)
    # Other lines that still break a restriction (e.g. parmesan when replacing cream
    # "without dairy"); reported, never hidden.
    remaining_conflicts: list[str] = field(default_factory=list)
    status: str = "not_adapted"  # supported | experimental | incomplete | not_adapted
    chosen: Candidate | None = None
    requested: bool = False  # the user named the replacement
    moisture: MoistureCheck | None = None
    texture: list[tuple[str, str]] = field(default_factory=list)  # (property, prediction)
    baking: str = ""  # temperature and time from the original steps
    limitations: list[str] = field(default_factory=list)

    def evidence_ids(self) -> set[str]:
        ids = {self.recipe_id} | {rid for rid, _ in self.evidence.notes}
        ids |= {rid for rid, _ in self.evidence.same_dish_without}
        for c in self.evidence.candidates:
            ids |= {rid for rid, _ in c.direct_examples} | set(c.comparative_examples)
            ids |= {s["id"] for s in c.supporting} | {rid for rid, _ in c.quantity.sources}
        return ids


REWRITE_SYSTEM = """\
You rewrite recipe steps after one ingredient was replaced. Code has already chosen the
substitute and its amount from dataset evidence; do not change them.
Return `step_edits`: one per step in steps_mentioning_target. In each, put the substitute
where the target was and keep the rest of the wording. Do not add or change any number
(amounts, temperatures, times), do not add ingredients, and do not mention the target.
"""


def _fraction(x: float) -> str:
    """0.6667 -> "2/3", 1.25 -> "1 1/4": the nearest quarter or third."""
    whole = int(x)
    rest = x - whole
    options = {0: "", 0.25: "1/4", 1 / 3: "1/3", 0.5: "1/2", 2 / 3: "2/3", 0.75: "3/4", 1: ""}
    best = min(options, key=lambda v: abs(rest - v))
    whole += best == 1
    text = " ".join(p for p in (str(whole) if whole else "", options[best]) if p)
    return text or "0"


def format_amount(amount: float, dimension: str | None) -> str:
    """ml -> cups / tablespoons / teaspoons; grams; counts."""
    if dimension == "mass":
        return f"{round(amount):,} g" if amount >= 10 else f"{amount:.1f} g"
    if dimension == "volume":
        for unit, size, least in (("cup", 236.6, 0.24), ("tablespoon", 14.79, 0.9),
                                  ("teaspoon", 4.93, 0)):
            if amount >= size * least:
                n = _fraction(amount / size)
                plural = n != "1" and not ("/" in n and " " not in n)
                return f"{n} {unit}{'s' if plural else ''}"
    return _fraction(amount)


class SubstitutionEngine:
    def __init__(self, store: RecipeStore, index: SearchIndex, config_dir: Path):
        self.store = store
        self.index = index
        roles = yaml.safe_load((config_dir / "roles.yaml").read_text(encoding="utf-8"))
        self.role_table: dict = roles["ingredients"]
        self.role_effects: dict[str, str] = roles["role_effects"]
        self.role_property: dict[str, str] = roles.get("role_property", {})
        self.provides: dict[str, list[str]] = roles.get("provides", {})
        self.partly: dict[str, list[str]] = roles.get("partially_provides", {})
        self.flavor_only = set(roles.get("flavor_only", []))
        self.ignore = set(roles.get("ignore_candidates", []))
        self.surface_re = re.compile(r"\b(?:" + "|".join(
            re.escape(w) for w in roles.get("surface_uses", [])) + r")\b", re.I)
        self.anchors = list(roles.get("scale_anchors", []))
        self.wet = {name for name, provided in self.provides.items() if "moisture" in provided}
        self.baked_markers = [fold(m) for m in roles["baked_markers"]]
        marker_re = r"\b(?:" + "|".join(re.escape(m) for m in self.baked_markers) + r")\b"
        self.is_baked = store.recipes["instructions_raw"].str.contains(
            marker_re, case=False, regex=True).to_numpy(bool)
        processed = store.processed_dir
        self.pairs = pd.read_parquet(processed / "substitution_pairs.parquet")
        self.notes = pd.read_parquet(processed / "substitution_notes.parquet")
        base_of = store.lexicon.base_of
        self.pairs["primary_base"] = self.pairs["primary"].map(base_of)
        self.pairs["alternative_base"] = self.pairs["alternative"].map(base_of)
        # Names used by at least a few recipes; rarer names are mostly parsing noise.
        self.known = {name for name, rows in store.by_base.items()
                      if len(rows) >= 5 and name not in self.ignore}

    # ----- evidence ------------------------------------------------------------------

    def contains(self, recipe_id: str, target: str) -> bool:
        """Quick check, from the recipe's indexes, that it uses the target at all."""
        row = self.store.get(recipe_id)
        categories = self.store.allergens.categories_for(target)
        if categories:
            return bool(set(categories) & (set(row["allergens"]) | set(row["allergens_uncertain"])))
        resolved = self.store.resolve(target, "strict")
        return resolved.base in set(row["bases"]) or bool(
            set(resolved.matched_names) & set(row["canonicals"]))

    def evidence(self, recipe_id: str, target: str, restrictions: list[str]) -> Evidence:
        store = self.store
        row = store.get(recipe_id)
        lines = store.lines([recipe_id]).sort_values("line_no")
        categories = store.allergens.categories_for(target)
        if categories:
            hit = lines.apply(lambda r: bool(set(categories) & (
                set(r["allergens"]) | set(r["allergens_uncertain"]))), axis=1)
        else:
            resolved = store.resolve(target, "strict")
            names = set(resolved.matched_names) | {resolved.base}
            hit = lines["canonical"].isin(names) | lines["base"].isin(names)
        target_rows = lines[hit] if len(lines) else lines
        target_names = sorted(set(target_rows["canonical"]) | set(target_rows["base"])) \
            if len(target_rows) else []

        restricted = list(dict.fromkeys([target, *restrictions]))
        baked = bool(self.is_baked[store.position[recipe_id]])
        roles = {name: self._roles(name, baked) for name in dict.fromkeys(target_rows["canonical"])}
        ev = Evidence(target, [(int(r.line_no), r.text) for r in target_rows.itertuples()],
                      target_names, restricted, roles, baked)
        ev.recipe_lines = lines
        if not ev.target_lines:
            return ev

        ev.expected_effects = [
            f"without the {name}'s {role}, the {'bake' if baked else 'dish'} "
            f"{self.role_effects[role]}"
            for name, roles in ev.roles.items() for role in roles if role in self.role_effects
        ] or [f"the role table has no entry for {target}, so its effect cannot be predicted"]
        candidates: dict[str, Candidate] = {}
        self._direct(ev, candidates)
        self._comparative(ev, recipe_id, row, categories, candidates)
        for cand in candidates.values():
            self._judge(ev, cand, set(row["bases"]))
        ranked = [c for c in candidates.values() if c.strength != "excluded"]
        # Quantities need the supporting recipes' lines, so they are found for the leading
        # candidates only; the final order then also uses them.
        ranked.sort(key=self._rank_key)
        ranked = ranked[:8]
        self._describe(ev, ranked)
        ranked.sort(key=self._rank_key)
        ev.candidates = ranked[:6]
        self._notes(ev, row["title"])  # after the candidates: notes that mention one are kept
        self._explain_ranking(ev)
        return ev

    def _roles(self, name: str, baked: bool) -> list[str]:
        spec = self.role_table.get(name) or self.role_table.get(self.store.lexicon.base_of(name))
        if not spec:
            return []
        return spec.get("baked" if baked else "other") or spec.get("other") or []

    def _coverage(self, name: str, ev: Evidence) -> dict[str, str]:
        """For each of the target's roles: does the candidate provide it fully, partly or
        not at all? Empty when the candidate is not in the role table."""
        full = {"flavor"} if name in self.flavor_only else set(self.provides.get(name, []))
        part = set(self.partly.get(name, []))
        if not (full or part) or not ev.all_roles:
            return {}
        return {role: "full" if role in full else "partial" if role in part else "none"
                for role in ev.all_roles}

    def _fit(self, coverage: dict[str, str], ev: Evidence) -> str:
        """good: provides a main role fully (binding for egg); partial: a main role only
        partly, or only other roles; poor: no overlap; unknown: not in roles.yaml."""
        if not coverage:
            return "unknown"
        main = [coverage.get(m) for m in ev.main_roles]
        if "full" in main:
            return "good"
        return "partial" if any(how != "none" for how in coverage.values()) else "poor"

    @staticmethod
    def _main_covered(coverage: dict[str, str], ev: Evidence) -> bool:
        return any(coverage.get(m) in ("full", "partial") for m in ev.main_roles)

    def _direct(self, ev: Evidence, candidates: dict[str, Candidate]) -> None:
        """ "X or Y" lines, counted in recipes of the same kind (baked or not) as this one;
        "butter or olive oil" in a saute says little about cookies. Lines about a surface
        use ("egg or milk, for brushing") only count when the target line is one too."""
        names = set(ev.target_names)
        p = self.pairs
        p = p[p["primary"].isin(names) | p["primary_base"].isin(names)
              | p["alternative"].isin(names) | p["alternative_base"].isin(names)]
        if not any(self.surface_re.search(text) for _, text in ev.target_lines):
            p = p[~p["text"].str.contains(self.surface_re)]
        if p.empty:
            return
        positions = p["recipe_id"].map(self.store.position).to_numpy()
        same_kind = p[self.is_baked[positions] == ev.baked]
        if same_kind.empty:  # no line from the same kind of dish: use the others
            same_kind = p
        seen: dict[str, set[str]] = defaultdict(set)
        for r in same_kind.itertuples():
            forward = r.primary in names or r.primary_base in names
            name = r.alternative_base if forward else r.primary_base
            if name in names or name not in self.known:
                continue
            cand = candidates.setdefault(name, Candidate(name))
            if r.recipe_id not in seen[name]:
                seen[name].add(r.recipe_id)
                cand.direct += 1
                if len(cand.direct_examples) < 3:
                    cand.direct_examples.append((r.recipe_id, r.text))
                if len(cand.direct_lines) < 50:
                    cand.direct_lines.append((r.recipe_id, r.text))

    def _comparative(self, ev: Evidence, recipe_id: str, row, categories: list[str] | None,
                     candidates: dict[str, Candidate]) -> None:
        store = self.store
        if categories:
            contains, unsure = store.category_masks(categories)
            target_mask = contains | unsure
        else:
            target_mask = store.rows_mask(np.concatenate(
                [store.by_base.get(n, np.array([], dtype=int)) for n in ev.target_names]))
        kind = "baked" if ev.baked else "non-baked"
        # Same dish first. If too few of those lack the target, also compare the wider dish
        # type; same-dish candidates need less support because they are the most relevant.
        top, dish = self._similar_recipes(recipe_id, row["title"], ev.baked, broad=False)
        without = int((~target_mask[top]).sum())
        ev.neighbours, ev.neighbours_without, ev.dish = len(top), without, dish
        ev.same_dish_ids = [str(i) for i in store.recipes["recipe_id"].to_numpy()[top]]
        # The closest evidence of all: versions of this same dish made without the target.
        examples = top[~target_mask[top]][:3]
        ev.same_dish_without = [(str(store.recipes["recipe_id"].iat[i]),
                                 str(store.recipes["title"].iat[i])) for i in examples]
        ev.comparison_scope = f"{len(top)} {kind} '{dish}' recipes"
        self._compare(ev, top, target_mask, candidates, min_support=2, scope="same dish")
        if without < MIN_NEIGHBOURS:
            # Few versions of this dish lack the target (9 of 183 banana breads have no eggs),
            # and each may use something different. Then a single same-dish recipe counts,
            # but only for an ingredient that provides the target's main role, at least
            # partly (silken tofu or applesauce for egg), so one-offs like carrot do not.
            self._compare(ev, top, target_mask, candidates, min_support=1, scope="same dish",
                          main_role_only=True)
            wide, wide_dish = self._similar_recipes(recipe_id, row["title"], ev.baked, broad=True)
            if wide_dish != dish:
                wide_without = int((~target_mask[wide]).sum())
                ev.comparison_scope += (f"; only {without} lack {ev.target}, so also {len(wide)} "
                                        f"{kind} '{wide_dish}' recipes ({wide_without} without it)")
                self._compare(ev, wide, target_mask, candidates,
                              min_support=MIN_COMPARATIVE_SUPPORT, scope=f"{wide_dish} recipes")

    def _compare(self, ev: Evidence, top: np.ndarray, target_mask: np.ndarray,
                 candidates: dict[str, Candidate], min_support: int, scope: str,
                 main_role_only: bool = False) -> None:
        store = self.store
        has_target = target_mask[top]
        with_rows, without_rows = top[has_target], top[~has_target]
        if len(without_rows) < min_support or not len(with_rows):
            return
        bases = store.recipes["bases"].to_numpy()
        count_without = Counter(b for i in without_rows for b in set(bases[i]))
        count_with = Counter(b for i in with_rows for b in set(bases[i]))
        ids = store.recipes["recipe_id"].to_numpy()
        for name, n in count_without.items():
            if n < min_support or name in ev.target_names:
                continue
            if name in candidates and candidates[name].comparative_support:
                continue  # already found in the closer (same-dish) comparison
            share_without = n / len(without_rows)
            share_with = count_with.get(name, 0) / len(with_rows)
            if (share_without + 0.01) / (share_with + 0.01) < MIN_LIFT:
                continue
            if name in store.lexicon.staples or name not in self.known:
                continue
            # Recipes without cream also use more tomato; that does not make tomato a cream
            # substitute. Comparative evidence alone only counts for ingredients known to
            # fill one of the target's roles.
            coverage = self._coverage(name, ev)
            if main_role_only and not self._main_covered(coverage, ev):
                continue
            if name not in candidates and self._fit(coverage, ev) not in ("good", "partial"):
                continue
            cand = candidates.setdefault(name, Candidate(name))
            cand.comparative_support, cand.comparative_scope = n, scope
            cand.share_without, cand.share_with = share_without, share_with
            cand.comparative_examples = sorted(
                str(ids[i]) for i in without_rows if name in bases[i])[:3]

    def _similar_recipes(self, recipe_id: str, title: str, baked: bool,
                         broad: bool) -> tuple[np.ndarray, str]:
        """Recipes of the same kind (baked or not) whose title has the same last word
        (usually the dish type: bread, sauce, cookie) and, unless `broad`, at least one
        other word of this title. Ranked by BM25 similarity. Returns rows and a label."""
        store = self.store
        words = tokenize(title, store.lexicon)
        scores = self.index.scores(title)
        mask = store.complete & ~store.is_duplicate & (self.is_baked == baked)
        mask[store.position[recipe_id]] = False
        label = title.lower()
        if words:
            mask &= store.title_mask(words[-1])
            others = [w for w in dict.fromkeys(words[:-1]) if w != words[-1]]
            label = words[-1]
            if others and not broad:
                any_other = np.zeros(store.n, dtype=bool)
                for word in others:
                    any_other |= store.title_mask(word)
                mask &= any_other
                label = " ".join([*others, words[-1]])
        rows = np.flatnonzero(mask)
        return rows[np.argsort(-scores[rows], kind="stable")][:NEIGHBOURS], label

    def _notes(self, ev: Evidence, title: str) -> None:
        """Instruction sentences that talk about substituting the target itself, e.g.
        "1 whole egg may be substituted for the 2 egg yolks", not "sugar substitute".
        Notes from the same dish type and kind (baked or not) come first."""
        words = {w for name in ev.target_names for w in name.split()} | {fold(ev.target)}
        t = "(?:" + "|".join(re.escape(w) for w in words) + r")s?"
        about = re.compile(
            rf"(?:substitut\w*|instead of|in place of|replac\w*)\W+(?:\w+\W+){{0,5}}{t}\b"
            rf"|\b{t}\W+(?:\w+\W+){{0,4}}(?:may|can|could)\s+be\s+(?:substitut|replac)", re.I)
        # Drop product names first: "sugar substitute and butter" is not about butter.
        product = re.compile(r"\b(?!(?:may|can|could|to|you|or|and|will|please|also|easily|"
                             r"except|then|simply|not)\b)\w+\s+substitutes?\b"
                             r"(?!\s+(?:for|with)\b)", re.I)
        found = self.notes[self.notes["sentence"].map(
            lambda s: bool(about.search(product.sub(" ", s))))].drop_duplicates("sentence")
        words = tokenize(title, self.store.lexicon)
        dish = words[-1] if words else ""

        def closeness(recipe_id: str) -> tuple[int, int]:
            pos = self.store.position.get(recipe_id)
            if pos is None:
                return (2, 2)
            same_dish = bool(dish) and dish in tokenize(
                self.store.recipes["title"].iat[pos], self.store.lexicon)
            return (0 if same_dish else 1, 0 if self.is_baked[pos] == ev.baked else 1)

        # Keep a note only if it comes from the same dish or names one of the evidenced
        # candidates ("...applesauce for oil"); a royal-icing tip says little about bread.
        names = [c.name for c in ev.candidates]

        def relevant(note: tuple[str, str]) -> bool:
            text = fold(note[1])
            return closeness(note[0])[0] == 0 or any(
                re.search(rf"\b{re.escape(n)}", text) for n in names)

        ranked = sorted(found.itertuples(index=False, name=None), key=lambda n: closeness(n[0]))
        ev.notes = [n for n in ranked if relevant(n)][:3]

    def _judge(self, ev: Evidence, cand: Candidate, recipe_bases: set[str]) -> None:
        """Drop candidates that break a restriction; flag uncertain ones; rate the evidence.
        Strength depends on the evidence only; role fit is rated separately."""
        hits = {h.category: h.status for h in self.store.allergens.classify(cand.name)}
        for term in ev.restricted:
            cats = self.store.allergens.categories_for(term) or []
            if any(hits.get(c) == "contains" for c in cats):
                cand.strength = "excluded"
                return
            if any(hits.get(c) == "uncertain" for c in cats):
                cand.flags.append(f"may contain {term} (uncertain)")
            # A name restriction ("no cilantro") excludes anything containing the word, but the
            # target itself only excludes exact matches: coconut cream may replace cream.
            elif not cats and term != ev.target and fold(term) in cand.name:
                cand.strength = "excluded"
                return
        if cand.name in recipe_bases:
            cand.flags.append("already in this recipe (use more of it)")
        cand.coverage = self._coverage(cand.name, ev)
        cand.fit = self._fit(cand.coverage, ev)
        clear_contrast = (cand.comparative_support >= 5
                          and cand.share_without >= 2 * max(cand.share_with, 0.01))
        if cand.direct >= 5 or (cand.direct >= 2 and clear_contrast):
            cand.strength = "strong"
        elif cand.direct >= 2 or clear_contrast:
            cand.strength = "moderate"
        else:
            cand.strength = "weak"
        if any("uncertain" in f for f in cand.flags):
            cand.strength = "conflicting"
        # Without a role-table entry, only strong evidence shows that it does the same job.
        cand.covers_main = self._main_covered(cand.coverage, ev) or (
            cand.fit == "unknown" and cand.strength == "strong")

    # ----- quantities ----------------------------------------------------------------

    def _target_amount(self, ev: Evidence) -> tuple[float, str] | None:
        """Total amount of the target in this recipe, if all its lines share a unit kind."""
        lines = ev.recipe_lines
        if lines is None or not len(lines):
            return None
        rows = lines[lines["line_no"].isin([pos for pos, _ in ev.target_lines])]
        dims = set(rows["dimension"].dropna())
        if len(dims) != 1 or rows["amount_base"].isna().any():
            return None
        return float(rows["amount_base"].sum()), dims.pop()

    def _describe(self, ev: Evidence, candidates: list[Candidate]) -> None:
        """Quantity and supporting recipes (with titles and the line that uses the
        candidate) for each candidate, with one read of the supporting recipes' lines."""
        ids = {rid for c in candidates for rid in c.comparative_examples}
        lines = self.store.lines(sorted(ids))
        by_id = {rid: df for rid, df in lines.groupby("recipe_id")} if len(lines) else {}
        target = self._target_amount(ev)
        for cand in candidates:
            cand.quantity = (self._direct_quantity(cand, ev, target)
                             or self._note_quantity(cand, ev, target)
                             or self._estimated_quantity(cand, ev, by_id))
            cand.supporting = [
                {"id": rid, "title": self._title(rid), "kind": "direct", "line": text}
                for rid, text in cand.direct_examples]
            for rid in cand.comparative_examples:
                df = by_id.get(rid)
                used = df[df["base"] == cand.name]["text"].tolist() if df is not None else []
                cand.supporting.append({"id": rid, "title": self._title(rid), "kind": "indirect",
                                        "line": used[0] if used else ""})

    def _title(self, recipe_id: str) -> str:
        row = self.store.get(recipe_id)
        return "" if row is None else str(row["title"])

    def _is_target(self, parsed, ev: Evidence) -> bool:
        return parsed is not None and (parsed.base in ev.target_names
                                       or parsed.canonical in ev.target_names)

    def _direct_quantity(self, cand: Candidate, ev: Evidence,
                         target: tuple[float, str] | None) -> Quantity | None:
        """From "X or Y" lines. "2 large eggs or 1/2 cup egg substitute" gives a ratio
        (60 ml per egg); "1 cup butter or margarine" offers the same amount."""
        lexicon = self.store.lexicon
        ratios, same = [], []
        for rid, text in cand.direct_lines:
            parts = _ALTERNATIVE.split(text, maxsplit=1)
            if len(parts) != 2:
                continue
            left = parse_line(parts[0], lexicon)
            if left is None or left.quantity is None:
                continue
            q, _, _ = take_quantity(parts[1].strip())
            if q is None:
                same.append((rid, text))
                continue
            right = parse_line(parts[1], lexicon)
            tgt, sub = (left, right) if self._is_target(left, ev) else (right, left)
            if (tgt and sub and tgt.amount_base and sub.amount_base and target
                    and tgt.dimension == target[1] and sub.dimension):
                ratios.append((sub.amount_base / tgt.amount_base, sub.dimension, rid, text))
        if ratios:
            dim = Counter(d for _, d, _, _ in ratios).most_common(1)[0][0]
            values = [r for r, d, _, _ in ratios if d == dim]
            amount = statistics.median(values) * target[0]
            spread = (f"; the lines disagree (from {format_amount(min(values) * target[0], dim)} "
                      f"to {format_amount(max(values) * target[0], dim)}), the median is used"
                      if max(values) > 2 * min(values) else "")
            sources = [(rid, text) for _, d, rid, text in ratios if d == dim][:3]
            return Quantity("supported", format_amount(amount, dim), amount, dim,
                            f"from {len(values)} dataset line(s) that give an amount of "
                            f"{cand.name} for the {ev.target}, e.g. \"{sources[0][1]}\" "
                            f"[{sources[0][0]}]{spread}", sources)
        if same and target:
            return Quantity("supported", "same amount as the original", target[0], target[1],
                            f"{len(same)} dataset line(s) offer {cand.name} at the same amount, "
                            f"e.g. \"{same[0][1]}\" [{same[0][0]}]", same[:3],
                            same_as_original=True)
        return None

    def _note_quantity(self, cand: Candidate, ev: Evidence,
                       target: tuple[float, str] | None) -> Quantity | None:
        """From instruction notes: "substitute 1/4 cup applesauce for each egg"."""
        if not target or target[1] != "count":
            return None
        words = "|".join(re.escape(w) for n in ev.target_names for w in n.split())
        pattern = re.compile(
            rf"(\d+(?:\s+\d+/\d+|/\d+)?)\s+([a-z]+\.?)\s+(?:of\s+)?{re.escape(cand.name)}\w*\s+"
            rf"(?:for|per|in place of|instead of|to replace)\s+(?:each|every|one|1|a|an)\s+"
            rf"(?:{words})\b", re.I)
        notes = self.notes[self.notes["sentence"].str.contains(cand.name, case=False,
                                                                regex=False)]
        for rid, sentence in notes.itertuples(index=False, name=None):
            match = pattern.search(sentence)
            if not match:
                continue
            parsed = parse_line(f"{match.group(1)} {match.group(2)} {cand.name}",
                                self.store.lexicon)
            if parsed and parsed.amount_base and parsed.dimension in ("volume", "mass"):
                amount = parsed.amount_base * target[0]
                return Quantity("supported", format_amount(amount, parsed.dimension), amount,
                                parsed.dimension, f"from an instruction note: \"{sentence}\" "
                                f"[{rid}], for {target[0]:g} {ev.target}", [(rid, sentence)])
        return None

    def _estimated_quantity(self, cand: Candidate, ev: Evidence,
                            by_id: dict[str, pd.DataFrame]) -> Quantity:
        """From recipes of the same dish without the target that use the candidate, scaled
        to this recipe by a shared ingredient. Only same-dish recipes: how much olive oil
        a ciabatta uses says nothing about banana bread."""
        if cand.comparative_scope != "same dish" or ev.recipe_lines is None:
            return Quantity()
        estimates, unscalable = [], []
        for rid in cand.comparative_examples:
            theirs = by_id.get(rid)
            if theirs is None:
                continue
            used = theirs[(theirs["base"] == cand.name)
                          & theirs["dimension"].isin(["volume", "mass"])]
            line = (theirs[theirs["base"] == cand.name]["text"].tolist() or [""])[0]
            anchor = self._anchor(ev.recipe_lines, theirs, {cand.name, *ev.target_names})
            if used.empty or used["dimension"].nunique() > 1 or anchor is None:
                unscalable.append((rid, line))
                continue
            name, ours, theirs_amount, dim = anchor
            amount = float(used["amount_base"].sum())
            estimates.append((amount * ours / theirs_amount, used["dimension"].iat[0], rid, line,
                              f"{format_amount(theirs_amount, dim)} {name}",
                              f"{format_amount(ours, dim)} {name}"))
        if estimates:
            dim = Counter(e[1] for e in estimates).most_common(1)[0][0]
            used_estimates = [e for e in estimates if e[1] == dim]
            amount = statistics.median(e[0] for e in used_estimates)
            first = used_estimates[0]
            basis = (f"estimated from {self._title(first[2])} [{first[2]}], which uses "
                     f"\"{first[3]}\" with {first[4]}; scaled to this recipe's {first[5]}")
            if len(used_estimates) > 1:
                basis = f"median of {len(used_estimates)} same-dish recipes; " + basis
            return Quantity("estimated", format_amount(amount, dim), amount, dim, basis,
                            [(e[2], e[3]) for e in used_estimates])
        if unscalable:
            rid, line = unscalable[0]
            return Quantity(basis=f"{UNKNOWN_QUANTITY} {self._title(rid)} [{rid}] uses "
                                  f"\"{line}\", but its size cannot be compared with this "
                                  "recipe's, so the amount is not scaled.",
                            sources=unscalable[:1])
        return Quantity()

    def _anchor(self, ours: pd.DataFrame, theirs: pd.DataFrame,
                skip: set[str]) -> tuple[str, float, float, str] | None:
        """A measured ingredient both recipes use: (name, our amount, their amount, kind)."""
        def totals(df: pd.DataFrame) -> dict[tuple[str, str], float]:
            df = df[df["dimension"].isin(["volume", "mass"]) & df["amount_base"].notna()]
            return df.groupby(["base", "dimension"])["amount_base"].sum().to_dict()

        # Only the bulk of the dish (flour, pasta, rice) says how big a recipe is; scaling by
        # parmesan or mint would turn 1 1/2 tablespoons of oil into a cup.
        a, b = totals(ours), totals(theirs)
        shared = [key for key in a if key in b and key[0] not in skip and a[key] and b[key]
                  and key[0] in self.anchors]
        if not shared:
            return None
        key = sorted(shared, key=lambda k: self.anchors.index(k[0]))[0]
        return key[0], a[key], b[key], key[1]

    # ----- ranking -------------------------------------------------------------------

    def _rank_key(self, c: Candidate) -> tuple:
        """Sort key: lower sorts first. One entry per ranking rule (RANKING_RULE); to change
        the order, move an entry here AND its reason in `_why`, which uses the same order."""
        return (
            c.strength in ("conflicting", "excluded"),  # 1. may break a restriction: last
            not c.covers_main,                          # 2. must provide the main role
            STRENGTH_ORDER[c.strength],                 # 3. evidence strength
            CLOSENESS_ORDER[c.closeness],               # 4. direct, same dish, related
            -c.coverage_score(),                        # 5. more of the roles covered
            -c.support,                                 # 6. more supporting recipes
            QUANTITY_ORDER[c.quantity.status],          # 7. supported, estimated, unknown
            c.name,                                     # tie: alphabetical (reported)
        )

    def _why(self, a: Candidate, b: Candidate, ev: Evidence) -> str:
        """The first ranking rule that separates a (higher) from b."""
        ka, kb = self._rank_key(a), self._rank_key(b)
        main = " and ".join(ev.main_roles) or "main role"
        reasons = [  # same order as _rank_key
            f"{b.name} may contain a restricted ingredient",
            f"{b.name} does not provide the {ev.noun}'s main role ({main})",
            f"{a.name} has {a.strength} evidence, {b.name} {b.strength}",
            f"{a.name}'s evidence is {a.closeness}, {b.name}'s is {b.closeness} "
            "(direct ranks above same dish, which ranks above related recipes)",
            f"both have {a.strength} {a.closeness} evidence, but {a.name} covers more of the "
            f"{ev.noun}'s roles ({a.coverage_text()}) than {b.name} ({b.coverage_text()})",
            f"{a.name} has more supporting recipes ({a.support} vs {b.support})",
            f"{a.name}'s quantity is {a.quantity.status}, {b.name}'s is {b.quantity.status}",
        ]
        for i, reason in enumerate(reasons):
            if ka[i] != kb[i]:
                return f"{a.name} ranks above {b.name}: {reason}."
        return (f"{a.name} and {b.name} are tied on every rule; {a.name} is listed first only "
                "alphabetically, so the dataset does not establish which is better.")

    def select(self, ev: Evidence) -> Candidate | None:
        """The first ranked candidate that may be chosen automatically."""
        return next((c for c in ev.candidates if c.covers_main
                     and c.strength not in ("conflicting", "excluded")), None)

    def _explain_ranking(self, ev: Evidence) -> None:
        chosen = self.select(ev)
        if chosen is None:
            return
        others = [c for c in ev.candidates if c is not chosen]
        ev.ranking_notes = [self._why(chosen, other, ev) for other in others[:4]]
        tied = [c.name for c in others if self._rank_key(c)[:-1] == self._rank_key(chosen)[:-1]]
        if tied:
            ev.uncertainty.append(f"{chosen.name} is tied with {', '.join(tied)} on every "
                                  "ranking rule; the dataset does not establish which is better.")
        same = [c.name for c in others if c.covers_main and c.strength == chosen.strength
                and c.strength in ("weak", "none") and c.name not in tied]
        if chosen.strength == "weak" and same:
            ev.uncertainty.append(
                f"{', '.join([chosen.name, *same])} all have equally weak evidence; the order "
                "between them rests on role coverage and quantity, not on stronger data.")
        conflicting = [c.name for c in ev.candidates if c.strength == "conflicting"]
        if conflicting:
            one = len(conflicting) == 1
            ev.uncertainty.append(
                f"Conflicting evidence: {', '.join(conflicting)} {'is' if one else 'are'} "
                f"supported by the dataset but may contain a restricted ingredient, so "
                f"{'it ranks' if one else 'they rank'} last and {'is' if one else 'are'} "
                "never chosen automatically.")

    # ----- adaptation ----------------------------------------------------------------

    def adapt(self, recipe_id: str, target: str, restrictions: list[str],
              replacement: str | None = None, llm: LLMClient | None = None) -> SubstitutionResult:
        row = self.store.get(recipe_id)
        ev = self.evidence(recipe_id, target, restrictions)
        result = SubstitutionResult(recipe_id, row["title"], ev)
        if not ev.target_lines:
            result.message = f"This recipe does not contain {target}, so nothing needs replacing."
            return result
        if replacement:
            self._use_requested(ev, replacement)
            result.requested = True
        if not ev.candidates:
            result.message = ("The dataset gives no reliable evidence for a substitute here "
                              f"(compared {ev.neighbours} similar recipes, "
                              f"{ev.neighbours_without} without {target}). I would rather not "
                              "guess a replacement, so no adapted recipe is produced.")
            return result
        if ev.candidates[0].strength == "excluded":
            result.message = (f"Your requested replacement '{replacement}' breaks your "
                              "restrictions, so I did not use it.")
            return result

        original = self.store.display_ingredients(recipe_id)
        result.original_ingredients = original
        targets = {pos for pos, _ in ev.target_lines}
        restricted = [r for r in ev.restricted if r != target]
        if restricted:
            names = [fold(r) for r in restricted if not self.store.allergens.categories_for(r)]
            others = Evidence(target, [], names, restricted, {}, ev.baked)
            result.remaining_conflicts = [
                line for i, line in enumerate(original)
                if i not in targets and self._mentions_target(line, others, all_restrictions=True)]
        steps = self._steps(row)
        result.baking = self._baking(steps)
        chosen = ev.candidates[0] if replacement else self.select(ev)
        if chosen is None:
            result.message = self._no_choice(ev)
            return result
        result.chosen = chosen
        result.moisture = self._moisture(ev, chosen)
        result.texture = self._texture(ev, chosen, result.moisture)
        adapted = self.build(original, steps, ev, chosen)
        result.adapted, result.method = adapted, "fallback"
        errors = self.validate(adapted, original, steps, ev)
        if errors:  # a code-built line should never fail; if one does, say so and stop
            result.adapted, result.validation_errors = None, errors
            result.message = "The adapted recipe failed its checks: " + "; ".join(errors)
            return result
        mentions = self._steps_mentioning(steps, ev)
        if llm is not None and mentions:
            self._llm_steps(llm, row, steps, mentions, ev, result)
        result.status = self.status(chosen)
        result.limitations = self._limitations(ev, chosen, result)
        return result

    def _no_choice(self, ev: Evidence) -> str:
        main = " and ".join(ev.main_roles) or "main role"
        best = ev.candidates[0]
        why = ("it may contain a restricted ingredient" if best.strength == "conflicting"
               else f"it does not provide {main} (it covers: {best.coverage_text()})")
        return (f"No candidate can be selected: none of them provides the {ev.noun}'s main "
                f"role ({main}) without risking a restriction. The best evidence is for "
                f"{best.name} ({best.strength}, {best.evidence_type()}), but {why}. I am not "
                "producing an adapted recipe; the evidence above shows what the dataset offers.")

    def _use_requested(self, ev: Evidence, replacement: str) -> None:
        name = self.store.resolve(replacement, "strict").base
        existing = next((c for c in ev.candidates if c.name == name), None)
        cand = existing or Candidate(name, strength="none",
                                     flags=["requested by you; no supporting recipes found"])
        if existing is None:
            self._judge(ev, cand, set())
            if cand.strength not in ("excluded", "conflicting"):
                cand.strength = "none"
            self._describe(ev, [cand])
        ev.candidates = [cand] + [c for c in ev.candidates if c is not cand]
        ev.ranking_notes = [f"You asked for {name}, so the ranking rules were not used to "
                            "choose it; its evidence and role coverage are shown as for any "
                            "other candidate."]
        ev.uncertainty = []

    def _steps(self, row) -> list[str]:
        steps = instruction_lines(row["instructions_raw"], self.store.lexicon.boilerplate_res)
        if row["steps_method"] == "sentence" and steps:
            steps = split_sentences(steps[0])
        return steps

    @staticmethod
    def _baking(steps: list[str]) -> str:
        """Oven temperature and baking time as written in the original steps."""
        text = " ".join(steps)
        temp = re.search(r"\b(\d{3})\s*(?:°|degrees?)\s*F?\b(?:\s*\((\d{2,3})\s*(?:°|degrees?)"
                         r"\s*C\))?", text, re.I)
        sentences = [x for s in steps for x in split_sentences(s)]
        duration = re.compile(r"\b\d+(?:\s*(?:to|-|–)\s*\d+)?\s*(?:minutes|mins?|hours?)\b", re.I)
        times = [m.group(0) for s in sentences if re.search(r"\bbake|\boven\b", s, re.I)
                 for m in duration.finditer(s)]
        parts = []
        if temp:
            parts.append(f"{temp.group(1)} degrees F" + (f" ({temp.group(2)} degrees C)"
                                                         if temp.group(2) else ""))
        times = list(dict.fromkeys(times))  # "35 minutes" twice in the recipe is one time
        if times:
            parts.append(times[-1] if len(times) == 1 else ", then ".join(times))
        return "; ".join(parts)

    def _mentions_target(self, text: str, ev: Evidence, ignore: str = "",
                         all_restrictions: bool = False) -> bool:
        """Does `text` mention the target (or, with all_restrictions, anything restricted)?
        Steps are checked for the target only: when replacing cream "without dairy", a step
        that mentions the recipe's parmesan is reported separately, not a failed rewrite."""
        folded = fold(text).replace(fold(ignore), " ") if ignore else fold(text)
        allergens = self.store.allergens
        terms = ev.restricted if all_restrictions else [ev.target]
        cats = {c for t in terms for c in (allergens.categories_for(t) or [])}
        if cats & {h.category for h in allergens.classify(folded)}:
            return True
        return any(re.search(rf"\b{re.escape(n)}(e?s)?\b", folded) for n in ev.target_names)

    def _steps_mentioning(self, steps: list[str], ev: Evidence) -> list[int]:
        return [i for i, s in enumerate(steps) if self._mentions_target(s, ev)]

    def _target_pattern(self, ev: Evidence) -> re.Pattern[str]:
        words = sorted(set(ev.target_names), key=len, reverse=True)
        return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")(e?s)?\b", re.I)

    def build(self, original: list[str], steps: list[str], ev: Evidence,
              chosen: Candidate) -> AdaptedRecipe:
        """The adapted recipe, built by code. Only the target lines change; the quantity is
        the one the dataset supports, an estimate (labelled), or explicitly unknown."""
        sub, q = chosen.name, chosen.quantity
        targets = dict(ev.target_lines)
        pattern = self._target_pattern(ev)
        ingredients, changes = [], []
        first = min(targets) if targets else -1
        for i, line in enumerate(original):
            if i not in targets:
                ingredients.append(line)
                continue
            if q.same_as_original:
                new = f"{pattern.sub(sub, line)} ({QUANTITY_TAG['supported']})"
            elif i == first:
                new = (f"{q.text} {sub} ({QUANTITY_TAG[q.status]})" if q.text
                       else f"{sub} ({QUANTITY_TAG['unknown']})")
            else:
                changes.append(f"removed '{line}': the {sub} line above replaces all of the "
                               f"{ev.target}")
                continue
            ingredients.append(new)
            changes.append(f"replaced '{line}' with '{new}'")
        changes.append(f"quantity ({q.status}): {q.basis}")
        instructions = [pattern.sub(sub, s) for s in steps]
        changed = [n for n, (a, b) in enumerate(zip(steps, instructions, strict=True), 1)
                   if a != b]
        if changed:
            changes.append(f"step(s) {', '.join(map(str, changed))}: {ev.target} replaced with "
                           f"{sub}; everything else as in the original")
        return AdaptedRecipe(sub, ingredients, instructions, changes)

    def _llm_steps(self, llm: LLMClient, row, steps: list[str], mentions: list[int],
                   ev: Evidence, result: SubstitutionResult) -> None:
        """Let the LLM reword the steps that mention the target. Each edit is checked and
        used only if it passes; otherwise that step keeps the rule-based rewrite."""
        adapted = result.adapted
        payload = {
            "recipe": row["title"],
            "target": ev.target,
            "substitute": adapted.substitute,
            "substitute_line": next((x for x in adapted.ingredients
                                     if x not in result.original_ingredients), ""),
            "steps_mentioning_target": {i + 1: steps[i] for i in mentions},
        }
        prompt = json.dumps(payload, ensure_ascii=False) + "\nJSON:"
        try:
            plan = llm.generate_json(REWRITE_SYSTEM, prompt, AdaptationPlan)
        except ValidationError:
            result.validation_errors = ["the LLM returned invalid JSON"]
            return
        except (LLMUnavailable, Exception) as exc:  # timeout, server down: keep the rules
            result.validation_errors = [f"LLM error: {type(exc).__name__}"]
            return
        errors, used = self.apply_step_edits(plan, steps, mentions, ev, adapted)
        result.validation_errors = errors
        if used:
            result.method = "llm"

    def apply_step_edits(self, plan: AdaptationPlan, steps: list[str], mentions: list[int],
                         ev: Evidence, adapted: AdaptedRecipe) -> tuple[list[str], int]:
        """Apply the LLM's step edits that pass the checks: only steps that mention the
        target, no new numbers (amounts, times, temperatures), no mention of the target."""
        errors, used = [], 0
        for edit in plan.step_edits:
            i = edit.number - 1
            text = edit.text.strip()
            if i not in mentions or not text:
                continue
            new_numbers = set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", steps[i]))
            if new_numbers:
                errors.append(f"step {i + 1} rewrite adds numbers {sorted(new_numbers)}")
            elif self._mentions_target(text, ev, ignore=adapted.substitute):
                errors.append(f"step {i + 1} rewrite still mentions the target")
            else:
                adapted.instructions[i] = text
                used += 1
        return errors, used

    def validate(self, adapted: AdaptedRecipe, original: list[str], steps: list[str],
                 ev: Evidence) -> list[str]:
        """Safety net for the built recipe: other lines verbatim, nothing restricted, only
        ingredients that appear in the dataset, no step still naming the target."""
        errors = []
        target_positions = {pos for pos, _ in ev.target_lines}
        kept = {line.strip() for line in adapted.ingredients}
        for pos, line in enumerate(original):
            if pos not in target_positions and line.strip() not in kept:
                errors.append(f"unchanged line was altered or dropped: '{line}'")
        lexicon, allergens = self.store.lexicon, self.store.allergens
        restricted_cats = {c for t in ev.restricted for c in (allergens.categories_for(t) or [])}
        restricted_names = {fold(t) for t in ev.restricted if not allergens.categories_for(t)}
        unchanged = {o.strip() for i, o in enumerate(original) if i not in target_positions}
        for line in adapted.ingredients:
            if line.strip() in unchanged:
                continue
            parsed = parse_line(line, lexicon)
            if parsed is None or parsed.is_header:
                continue
            hits = {h.category for h in allergens.classify(line)}
            if hits & restricted_cats or parsed.canonical in ev.target_names \
                    or parsed.base in ev.target_names or parsed.canonical in restricted_names:
                errors.append(f"new line still contains a restricted ingredient: '{line}'")
            if parsed.canonical and parsed.canonical not in self.store.by_canonical \
                    and parsed.base not in self.store.by_base:
                errors.append(f"'{parsed.canonical}' does not appear in the dataset")
        for number, step in enumerate(adapted.instructions, 1):
            # "coconut cream" in a step is the substitute, not the target
            if self._mentions_target(step, ev, ignore=adapted.substitute):
                errors.append(f"step {number} still mentions the target: '{step[:60]}'")
        return errors

    # ----- moisture, texture, limitations --------------------------------------------

    def _wet_ratio(self, lines: pd.DataFrame, skip: set[str]) -> tuple[float | None, list[str]]:
        """Volume of wet ingredients (those that provide moisture) per volume of flour.
        None when a wet line has no volume ("3 bananas") or there is no measured flour."""
        if lines is None or not len(lines):
            return None, []
        wet = lines[lines["base"].isin(self.wet) & ~lines["base"].isin(skip)]
        flour = lines[lines["base"].str.contains("flour", na=False)
                      & (lines["dimension"] == "volume")]["amount_base"].sum()
        texts = wet["text"].tolist()
        if not len(wet) or (wet["dimension"] != "volume").any() or not flour:
            return None, texts
        return float(wet["amount_base"].sum() / flour), texts

    def _moisture(self, ev: Evidence, chosen: Candidate) -> MoistureCheck:
        skip = set(ev.target_names)
        ratio, existing = self._wet_ratio(ev.recipe_lines, skip)
        check = MoistureCheck(existing=existing, ratio=ratio)
        adds = chosen.coverage.get("moisture") in ("full", "partial") or chosen.name in self.wet
        if not adds:
            check.risk = "none"
            if "moisture" in ev.all_roles:
                check.notes.append(f"{chosen.name} adds little moisture, and removing the "
                                   f"{ev.target} removes some, so the result may be drier.")
            return check
        check.baseline, check.baseline_n = self._baseline(ev, skip)
        q, flour = chosen.quantity, self._flour(ev.recipe_lines)
        if ratio is not None and q.dimension == "volume" and q.amount and flour:
            check.after = ratio + q.amount / flour
        compare = check.after if check.after is not None else ratio
        wet_list = "; ".join(existing) if existing else "none"
        check.notes.append(f"Wet ingredients already in this recipe: {wet_list}.")
        if ratio is not None and check.baseline is not None:
            check.notes.append(
                f"By volume they are {ratio:.0%} of the flour; the median across "
                f"{check.baseline_n} '{ev.dish}' recipes in the dataset is {check.baseline:.0%} "
                f"(eggs are not counted: the dataset gives no volume for them).")
        if check.after is not None:
            check.notes.append(f"With {q.text} {chosen.name} ({q.status}) it would be about "
                               f"{check.after:.0%}.")
        elif q.status == "unknown":
            check.notes.append(f"The amount of {chosen.name} is not established, and it decides "
                               "how wet the batter gets.")
        if compare is None or check.baseline is None:
            check.risk = "unknown"
            if existing and ev.baked:
                check.notes.append(f"{chosen.name} adds moisture on top of these; too much can "
                                   "leave the centre gummy or underbaked.")
        elif compare >= 1.25 * check.baseline:
            check.risk = "high"
        elif compare >= check.baseline or (check.after is None and q.status == "unknown"):
            check.risk = "possible"
        else:
            check.risk = "low"
        if check.risk in ("high", "possible"):
            check.notes.append("Excess-moisture risk: a wetter batter can bake up gummy, dense "
                               "or underbaked in the centre. Check doneness with a toothpick; "
                               "the original baking time was not tested with this change.")
        return check

    def _baseline(self, ev: Evidence, skip: set[str]) -> tuple[float | None, int]:
        """Median wet-to-flour ratio of the same dish's recipes where it can be measured."""
        if not (ev.baked and ev.same_dish_ids):
            return None, 0
        lines = self.store.lines(ev.same_dish_ids)
        if not len(lines):
            return None, 0
        ratios = [r for _, df in lines.groupby("recipe_id")
                  if (r := self._wet_ratio(df, skip)[0]) is not None]
        return (statistics.median(ratios), len(ratios)) if len(ratios) >= 10 else (None, 0)

    @staticmethod
    def status(chosen: Candidate) -> str:
        """supported: strong or moderate evidence and a quantity from the dataset;
        incomplete: no quantity; experimental: everything in between."""
        if chosen.quantity.status == "unknown":
            return "incomplete"
        if chosen.strength in ("strong", "moderate") and chosen.quantity.status == "supported":
            return "supported"
        return "experimental"

    @staticmethod
    def _flour(lines: pd.DataFrame | None) -> float:
        if lines is None or not len(lines):
            return 0.0
        return float(lines[lines["base"].str.contains("flour", na=False)
                           & (lines["dimension"] == "volume")]["amount_base"].sum())

    def _texture(self, ev: Evidence, chosen: Candidate,
                 moisture: MoistureCheck | None) -> list[tuple[str, str]]:
        """Predicted changes, one per role of the target, from what the substitute provides
        (roles.yaml). Predictions from cooking knowledge, never dataset facts."""
        sub, roles, rows = chosen.name, ev.all_roles, []
        wet_risk = moisture is not None and moisture.risk in ("high", "possible", "unknown")
        for role in roles:
            prop = self.role_property.get(role, role.capitalize())
            how = chosen.coverage.get(role, "unknown")
            effect = self.role_effects.get(role, "may change")
            if role == "moisture" and how != "none" and wet_risk:
                text = (f"may stay moist or become wetter than the original, depending on the "
                        f"amount of {sub}")
            elif how == "full":
                text = f"{sub} provides {role}, so this may stay close to the original"
            elif how == "partial":
                text = f"potentially weaker than the original: {sub} provides only some {role}"
            elif how == "none":
                text = f"{sub} does not provide {role}, so the result {effect}"
            else:
                text = f"unknown: the role table has no entry for {sub}; without {role} it {effect}"
            rows.append((prop, text))
        if ev.baked and "leavening" in roles and chosen.coverage.get("leavening") != "full":
            rows.append(("Density", f"may become denser, since the {ev.noun}'s leavening is "
                                    "not fully replaced"))
        if ev.baked and wet_risk and chosen.coverage.get("leavening") != "full" and \
                chosen.coverage.get("moisture") in ("full", "partial"):
            rows.append(("Crumb", f"may become softer or gummy, more so with more {sub}"))
        return rows

    def _limitations(self, ev: Evidence, chosen: Candidate,
                     result: SubstitutionResult) -> list[str]:
        out = []
        if chosen.strength == "none":
            out.append(f"No recipe in the dataset supports {chosen.name} for {ev.target}; it is "
                       "used only because you asked for it.")
        elif not chosen.direct:
            out.append(f"No recipe in the dataset explicitly recommends {chosen.name} for "
                       f"{ev.target}. The evidence is indirect: recipes that use {chosen.name} "
                       f"and no {ev.target} may differ in other ways too.")
        if chosen.support == 1:
            out.append("The evidence rests on a single recipe.")
        if not chosen.covers_main:
            out.append(f"{chosen.name} does not provide the {ev.noun}'s main role "
                       f"({' and '.join(ev.main_roles)}).")
        q = chosen.quantity
        if q.status == "unknown":
            out.append(f"{UNKNOWN_QUANTITY} The ingredient list is incomplete: test a small "
                       "batch before relying on it.")
        elif q.status == "estimated":
            out.append("The quantity is an estimate scaled from another recipe, not an amount "
                       "the dataset gives for this substitution.")
        out.append("Baking temperature and time are those of the original recipe; they were "
                   "not re-tested with the substitute." if result.baking else
                   "The original recipe gives no baking temperature or time.")
        out.append("Texture predictions come from the ingredient's roles (general cooking "
                   "knowledge), not from results recorded in the dataset.")
        return out + ev.uncertainty
