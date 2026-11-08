"""Evidence-based ingredient substitution.

1. Find the lines to replace in the recipe, and the ingredient's role there (roles.yaml).
2. Collect evidence from the dataset:
   - direct: ingredient lines that offer a choice ("1 cup butter or margarine") and
     instruction sentences that mention substituting;
   - comparative (indirect): among similar recipes, ingredients that are much more common
     in those WITHOUT the target than in those with it.
   Candidates that break a restriction are dropped; uncertain ones are flagged.
3. The LLM picks a substitute from the evidenced candidates only and rewrites the recipe.
4. Code validates the rewrite (restriction respected, unchanged lines kept verbatim, every
   new ingredient exists in the dataset). If it fails twice, or there is no LLM, a simple
   deterministic rewrite is used instead.
"""

from __future__ import annotations

import json
import re
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
from recipebot.nlp.ingredient_parser import parse_line
from recipebot.nlp.steps import instruction_lines, split_sentences
from recipebot.nlp.text import fold

NEIGHBOURS = 300  # similar recipes compared for indirect evidence
MIN_COMPARATIVE_SUPPORT = 3  # a candidate must appear in at least this many recipes
MIN_LIFT = 1.5
STRENGTH_ORDER = {"strong": 0, "moderate": 1, "weak": 2, "conflicting": 3, "none": 4}
FIT_ORDER = {"good": 0, "partial": 1, "unknown": 2, "poor": 3}
MIN_NEIGHBOURS = 15  # below this, the similar-recipe set is broadened


@dataclass
class Candidate:
    name: str
    direct: int = 0  # recipes where it is offered as an alternative to the target
    direct_examples: list[tuple[str, str]] = field(default_factory=list)  # (recipe ID, line)
    comparative_support: int = 0  # similar recipes without the target that use it
    share_without: float = 0.0
    share_with: float = 0.0
    comparative_examples: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    strength: str = "weak"
    fit: str = "unknown"  # good | partial | unknown | poor: do its roles match the target's?
    direct_scope: str = ""  # "baked" / "non-baked" recipes, or "other kinds of" dishes
    comparative_scope: str = ""  # "same dish" or the wider dish type

    def summary(self) -> str:
        parts = []
        if self.direct:
            parts.append(f"offered as an alternative to the target in {self.direct} "
                         f"{self.direct_scope} recipes".replace("  ", " "))
        if self.comparative_support:
            parts.append(f"used by {self.comparative_support} {self.comparative_scope} recipes "
                         f"without the target ({self.share_without:.0%} of them vs "
                         f"{self.share_with:.0%} of those with it)".replace("recipes recipes",
                                                                            "recipes"))
        if self.fit != "unknown":
            parts.append(f"{self.fit} fit for the target's role")
        return "; ".join(parts + self.flags) or "no supporting recipes found"


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
    same_dish_without: list[tuple[str, str]] = field(default_factory=list)  # (ID, title)
    # What removing the target is likely to change, from its roles (roles.yaml). Always
    # given, so the trade-off question is answered even when no substitute is proposed.
    expected_effects: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)  # (recipe ID, sentence)

    @property
    def best_strength(self) -> str:
        return self.candidates[0].strength if self.candidates else "none"


class LineEdit(BaseModel):
    number: int = Field(description="the target ingredient line number being replaced")
    text: str = Field(description="the new ingredient line for the substitute")


class StepEdit(BaseModel):
    number: int = Field(description="the instruction step number being rewritten")
    text: str = Field(description="the rewritten step")


class AdaptationPlan(BaseModel):
    """What the LLM returns: only the edits. Code applies them to the original recipe, so
    unchanged lines stay exactly as in the dataset and the output stays short."""

    substitute: str = Field(description="the chosen candidate name, or 'none'")
    ingredient_edits: list[LineEdit] = Field(description="one edit per target line")
    step_edits: list[StepEdit] = Field(description="one edit per step that mentions the target")
    changes: list[str] = Field(description="each change and which evidence supports it")
    predicted_effects: list[str] = Field(description="likely effects on taste, texture or "
                                                     "preparation (predictions)")


class AdaptedRecipe(BaseModel):
    substitute: str = Field(description="the chosen candidate name, or 'none'")
    ingredients: list[str] = Field(description="the full adapted ingredient list")
    instructions: list[str] = Field(description="the full adapted instruction steps")
    changes: list[str] = Field(description="each change and why, citing the evidence")
    predicted_effects: list[str] = Field(description="likely effects on taste, texture or "
                                                     "preparation (predictions)")


@dataclass
class SubstitutionResult:
    recipe_id: str
    title: str
    evidence: Evidence
    adapted: AdaptedRecipe | None = None
    method: str = "none"  # llm | fallback | none
    validation_errors: list[str] = field(default_factory=list)
    message: str = ""  # why no adaptation was made, if none was
    original_ingredients: list[str] = field(default_factory=list)
    # Other lines that still break a restriction (e.g. parmesan when replacing cream
    # "without dairy"); reported, never hidden.
    remaining_conflicts: list[str] = field(default_factory=list)

    def evidence_ids(self) -> set[str]:
        ids = {self.recipe_id} | {rid for rid, _ in self.evidence.notes}
        for c in self.evidence.candidates:
            ids |= {rid for rid, _ in c.direct_examples} | set(c.comparative_examples)
        return ids


REWRITE_SYSTEM = """\
You adapt a recipe by replacing one ingredient, using evidence from a recipe dataset.
Return only the edits:
- `substitute`: pick ONLY from the candidates list (exact name), preferring a good role fit
  and stronger evidence. Weak evidence is acceptable: the user is shown its strength and a
  caution. Use "none" only if no candidate has a good or partial fit.
- `ingredient_edits`: one per target line, with the new line for the substitute. If the
  amount is your own judgment rather than from the evidence, end the line with "(estimate)".
- `step_edits`: one per step listed in steps_mentioning_target, rewritten for the
  substitute. Keep the rest of each step's wording.
- `changes`: one short item per change, naming the evidence that supports it.
- `predicted_effects`: 1-3 likely effects on taste, texture or preparation. These are
  predictions, not tested results.
Never use an ingredient the restrictions forbid. Never claim the result is allergy-safe.
"""


class SubstitutionEngine:
    def __init__(self, store: RecipeStore, index: SearchIndex, config_dir: Path):
        self.store = store
        self.index = index
        roles = yaml.safe_load((config_dir / "roles.yaml").read_text(encoding="utf-8"))
        self.role_table: dict = roles["ingredients"]
        self.role_effects: dict[str, str] = roles["role_effects"]
        self.provides: dict[str, list[str]] = roles.get("provides", {})
        self.flavor_only = set(roles.get("flavor_only", []))
        self.ignore = set(roles.get("ignore_candidates", []))
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
        # Conflicting candidates (may break a restriction) last; then role fit (coconut milk,
        # not water, for cream); then evidence strength; then amount of evidence, where
        # same-dish (comparative) evidence counts three times.
        ranked.sort(key=lambda c: (c.strength == "conflicting", FIT_ORDER[c.fit],
                                   STRENGTH_ORDER[c.strength],
                                   -(c.direct + 3 * c.comparative_support), c.name))
        ev.candidates = ranked[:6]
        self._notes(ev, row["title"])  # after the candidates: notes that mention one are kept
        return ev

    def _target_roles(self, ev: Evidence) -> tuple[set[str], set[str]]:
        """(main roles, all roles): the first role listed for each target is its main one."""
        main = {roles[0] for roles in ev.roles.values() if roles}
        return main, {r for roles in ev.roles.values() for r in roles}

    def _fit(self, cand: Candidate, ev: Evidence) -> str:
        """good: covers a main role (binding for egg); partial: only a secondary role;
        poor: no overlap; unknown: not in roles.yaml."""
        main, roles = self._target_roles(ev)
        if not roles:
            return "unknown"
        provided = {"flavor"} if cand.name in self.flavor_only else \
            set(self.provides.get(cand.name, []))
        if not provided:
            return "unknown"
        if provided & main:
            return "good"
        return "partial" if provided & roles else "poor"

    def _roles(self, name: str, baked: bool) -> list[str]:
        spec = self.role_table.get(name) or self.role_table.get(self.store.lexicon.base_of(name))
        if not spec:
            return []
        return spec.get("baked" if baked else "other") or spec.get("other") or []

    def _direct(self, ev: Evidence, candidates: dict[str, Candidate]) -> None:
        """ "X or Y" lines, counted in recipes of the same kind (baked or not) as this one;
        "butter or olive oil" in a saute says little about cookies."""
        names = set(ev.target_names)
        p = self.pairs
        p = p[p["primary"].isin(names) | p["primary_base"].isin(names)
              | p["alternative"].isin(names) | p["alternative_base"].isin(names)]
        if p.empty:
            return
        positions = p["recipe_id"].map(self.store.position).to_numpy()
        same_kind = p[self.is_baked[positions] == ev.baked]
        scope = "baked" if ev.baked else "non-baked"
        if same_kind.empty:
            same_kind, scope = p, "other kinds of"
        seen: dict[str, set[str]] = defaultdict(set)
        for r in same_kind.itertuples():
            forward = r.primary in names or r.primary_base in names
            name = r.alternative_base if forward else r.primary_base
            if name in names or name not in self.known:
                continue
            cand = candidates.setdefault(name, Candidate(name))
            cand.direct_scope = scope
            if r.recipe_id not in seen[name]:
                seen[name].add(r.recipe_id)
                cand.direct += 1
                if len(cand.direct_examples) < 3:
                    cand.direct_examples.append((r.recipe_id, r.text))

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
        ev.neighbours, ev.neighbours_without = len(top), without
        # The closest evidence of all: versions of this same dish made without the target.
        examples = top[~target_mask[top]][:3]
        ev.same_dish_without = [(str(store.recipes["recipe_id"].iat[i]),
                                 str(store.recipes["title"].iat[i])) for i in examples]
        ev.comparison_scope = f"{len(top)} {kind} '{dish}' recipes"
        self._compare(ev, top, target_mask, candidates, min_support=2, scope="same dish")
        if without < MIN_NEIGHBOURS:
            # Few versions of this dish lack the target (9 of 183 banana breads have no eggs),
            # and each may use something different. Then a single same-dish recipe counts,
            # but only for an ingredient that covers the target's main role (silken tofu or
            # applesauce binding in place of egg), so one-off ingredients like carrot do not.
            self._compare(ev, top, target_mask, candidates, min_support=1, scope="same dish",
                          good_fit_only=True)
            wide, wide_dish = self._similar_recipes(recipe_id, row["title"], ev.baked, broad=True)
            if wide_dish != dish:
                wide_without = int((~target_mask[wide]).sum())
                ev.comparison_scope += (f"; only {without} lack {ev.target}, so also {len(wide)} "
                                        f"{kind} '{wide_dish}' recipes ({wide_without} without it)")
                self._compare(ev, wide, target_mask, candidates,
                              min_support=MIN_COMPARATIVE_SUPPORT, scope=f"{wide_dish} recipes")

    def _compare(self, ev: Evidence, top: np.ndarray, target_mask: np.ndarray,
                 candidates: dict[str, Candidate], min_support: int, scope: str,
                 good_fit_only: bool = False) -> None:
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
            fit = self._fit(Candidate(name), ev)
            if good_fit_only and fit != "good":
                continue
            if name not in candidates and fit not in ("good", "partial"):
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
        """Drop candidates that break a restriction; flag uncertain ones; rate the evidence."""
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
        cand.fit = self._fit(cand, ev)
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
        if not ev.candidates:
            result.message = ("The dataset gives no reliable evidence for a substitute here "
                              f"(compared {ev.neighbours} similar recipes, "
                              f"{ev.neighbours_without} without {target}). I would rather not "
                              "guess a replacement.")
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
        if llm is not None:
            mentions = self._steps_mentioning(steps, ev)
            prompt = self._prompt(row, original, steps, mentions, ev)
            for _ in range(2):
                try:
                    plan = llm.generate_json(REWRITE_SYSTEM, prompt, AdaptationPlan)
                except ValidationError:
                    result.validation_errors = ["the LLM returned invalid JSON"]
                    continue
                except (LLMUnavailable, Exception) as exc:  # timeout, server down: give up
                    result.validation_errors = [f"LLM error: {type(exc).__name__}"]
                    break
                if plan.substitute.lower() == "none" and self._has_good_fit(ev):
                    # The evidence is labelled for the user; declining outright would leave
                    # the question unanswered, so the rule-based adaptation is used instead.
                    result.validation_errors = ["the LLM declined although a candidate fits "
                                                "the ingredient's role"]
                    break
                adapted = self.apply_plan(plan, original, steps, ev)
                self._patch_steps(adapted, ev)
                errors = self.validate(adapted, original, steps, ev)
                if not errors:
                    result.adapted, result.method = adapted, "llm"
                    return result
                result.validation_errors = errors
                prompt += "\nYour previous answer was rejected: " + "; ".join(errors) + "\nJSON:"
        if not self.fallback_allowed(ev):
            best = ev.candidates[0]
            result.message = (f"The evidence is not clear enough to choose a substitute "
                              f"automatically (best candidate: {best.name}, {best.strength} "
                              f"evidence, {best.fit} fit for the role), so I am not guessing. "
                              "The evidence above shows what the dataset offers.")
            return result
        result.adapted, result.method = self._fallback(original, steps, ev), "fallback"
        return result

    def _use_requested(self, ev: Evidence, replacement: str) -> None:
        name = self.store.resolve(replacement, "strict").base
        existing = next((c for c in ev.candidates if c.name == name), None)
        cand = existing or Candidate(name, strength="none",
                                     flags=["requested by you; no supporting recipes found"])
        if existing is None:
            self._judge(ev, cand, set())
            if cand.strength != "excluded":
                cand.strength = "none"
        ev.candidates = [cand] + [c for c in ev.candidates if c is not cand]

    def _steps(self, row) -> list[str]:
        steps = instruction_lines(row["instructions_raw"], self.store.lexicon.boilerplate_res)
        if row["steps_method"] == "sentence" and steps:
            steps = split_sentences(steps[0])
        return steps

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

    def _prompt(self, row, original: list[str], steps: list[str], mentions: list[int],
                ev: Evidence) -> str:
        payload = {
            "recipe": row["title"],
            "dish_type": "baked" if ev.baked else "other",
            "all_ingredients": original,
            "target_lines": {pos + 1: text for pos, text in ev.target_lines},
            "target": ev.target,
            "roles_of_target": ev.roles,
            "steps_mentioning_target": {i + 1: steps[i] for i in mentions},
            "restrictions": ev.restricted,
            "candidates": [{"name": c.name, "evidence": c.strength, "role_fit": c.fit,
                            "detail": c.summary()} for c in ev.candidates],
        }
        return json.dumps(payload, ensure_ascii=False) + "\nJSON:"

    def apply_plan(self, plan: AdaptationPlan, original: list[str], steps: list[str],
                   ev: Evidence) -> AdaptedRecipe:
        """Apply the LLM's edits to the original recipe. Edits to non-target lines are
        ignored, so the rest of the recipe is always exactly as in the dataset."""
        targets = {pos for pos, _ in ev.target_lines}
        ingredients, edited = list(original), set()
        for edit in plan.ingredient_edits:
            pos = edit.number - 1
            if pos in targets and edit.text.strip():
                ingredients[pos] = edit.text.strip()
                edited.add(pos)
        # A target line the LLM did not edit is dropped rather than silently kept.
        ingredients = [line for i, line in enumerate(ingredients)
                       if i not in targets or i in edited]
        new_steps = list(steps)
        for edit in plan.step_edits:
            if 1 <= edit.number <= len(steps) and edit.text.strip():
                new_steps[edit.number - 1] = edit.text.strip()
        return AdaptedRecipe(substitute=plan.substitute, ingredients=ingredients,
                             instructions=new_steps, changes=plan.changes,
                             predicted_effects=plan.predicted_effects)

    def validate(self, adapted: AdaptedRecipe, original: list[str], steps: list[str],
                 ev: Evidence) -> list[str]:
        errors = []
        names = {c.name for c in ev.candidates}
        if adapted.substitute.lower() == "none":
            return []
        if adapted.substitute not in names:
            errors.append(f"substitute '{adapted.substitute}' is not one of the candidates")
        target_positions = {pos for pos, _ in ev.target_lines}
        kept = {line.strip() for line in adapted.ingredients}
        for pos, line in enumerate(original):
            if pos not in target_positions and line.strip() not in kept:
                errors.append(f"unchanged line was altered or dropped: '{line}'")
        lexicon, allergens = self.store.lexicon, self.store.allergens
        restricted_cats = {c for t in ev.restricted for c in (allergens.categories_for(t) or [])}
        restricted_names = {fold(t) for t in ev.restricted if not allergens.categories_for(t)}
        for line in adapted.ingredients:
            if line.strip() in {o.strip() for i, o in enumerate(original)
                                if i not in target_positions}:
                continue
            parsed = parse_line(line.replace("(estimate)", ""), lexicon)
            if parsed is None or parsed.is_header:
                continue
            hits = {h.category for h in allergens.classify(line)}
            if hits & restricted_cats or parsed.canonical in ev.target_names \
                    or parsed.base in ev.target_names or parsed.canonical in restricted_names:
                errors.append(f"new line still contains a restricted ingredient: '{line}'")
            if parsed.canonical and parsed.canonical not in self.store.by_canonical \
                    and parsed.base not in self.store.by_base:
                errors.append(f"'{parsed.canonical}' does not appear in the dataset")
            # A replacement line holds the substitute only; it must not slip in more of
            # something else ("2 cups mashed bananas, 1/4 cup applesauce").
            substitute = self.store.resolve(adapted.substitute, "strict").base
            if parsed.base != substitute and parsed.canonical != fold(adapted.substitute):
                errors.append(f"replacement line '{line}' must contain only the substitute "
                              f"({adapted.substitute}), one ingredient per line")
        for number, step in enumerate(adapted.instructions, 1):
            # "coconut cream" in a step is the substitute, not the target
            if self._mentions_target(step, ev, ignore=adapted.substitute):
                errors.append(f"step {number} still mentions the target: '{step[:60]}'")
        return errors

    def _target_pattern(self, ev: Evidence) -> re.Pattern[str]:
        words = sorted(set(ev.target_names), key=len, reverse=True)
        return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")(e?s)?\b", re.I)

    def _patch_steps(self, adapted: AdaptedRecipe, ev: Evidence) -> None:
        """A step the LLM forgot to rewrite gets the target's name swapped for the
        substitute, and the change is listed, instead of discarding the whole rewrite."""
        if adapted.substitute.lower() == "none" or not ev.target_names:
            return
        pattern = self._target_pattern(ev)
        for i, step in enumerate(adapted.instructions):
            if self._mentions_target(step, ev, ignore=adapted.substitute):
                patched = pattern.sub(adapted.substitute, step)
                if patched != step:
                    adapted.instructions[i] = patched
                    adapted.changes.append(f"step {i + 1}: the target's name was replaced with "
                                           f"{adapted.substitute} automatically")

    @staticmethod
    def _has_good_fit(ev: Evidence) -> bool:
        return any(c.fit == "good" and c.strength != "conflicting" for c in ev.candidates)

    def fallback_allowed(self, ev: Evidence) -> bool:
        """Without the LLM's judgment, only adapt when the choice is clear: a good role fit
        or strong evidence. Otherwise decline rather than guess."""
        best = ev.candidates[0]
        return best.strength != "conflicting" and (best.fit == "good" or best.strength == "strong")

    def _fallback(self, original: list[str], steps: list[str], ev: Evidence) -> AdaptedRecipe:
        """Deterministic rewrite: swap the target's name in its lines and steps. A measured
        amount is kept ("1/2 cup butter" -> "1/2 cup shortening"); a count is not
        ("2 eggs" -> "olive oil (amount not given by the dataset)")."""
        sub = ev.candidates[0].name
        targets = {pos: text for pos, text in ev.target_lines}
        pattern = self._target_pattern(ev)
        ingredients = []
        for i, line in enumerate(original):
            if i not in targets:
                ingredients.append(line)
                continue
            parsed = parse_line(line, self.store.lexicon)
            measured = parsed is not None and parsed.dimension in ("volume", "mass")
            swapped = pattern.sub(sub, line)
            ingredients.append(f"{swapped} (estimate: same amount as the original)"
                               if measured and swapped != line
                               else f"{sub} (amount not given by the dataset)")
        instructions = [pattern.sub(sub, s) for s in steps]
        # Which of the target's roles the substitute covers (roles.yaml), and what is likely
        # to change for the roles it does not: specific to the substitute, unlike the general
        # "expected trade-offs of removing the target".
        roles = list(dict.fromkeys(r for rs in ev.roles.values() for r in rs))
        provided = set(self.provides.get(sub, []))
        covered = [r for r in roles if r in provided]
        effects = []
        if provided:
            if covered:
                effects.append(f"{sub} can take over the {' and '.join(covered)} role(s)")
            effects += [f"{sub} does not provide {r}, so the result {self.role_effects[r]}"
                        for r in roles if r not in provided and r in self.role_effects]
        else:
            effects.append(f"the roles {sub} plays are not in the role table, so its effect "
                           "cannot be predicted beyond the trade-offs above")
        changes = [f"replaced '{t}' with {sub} ({ev.candidates[0].strength} evidence: "
                   f"{ev.candidates[0].summary()})" for t in targets.values()]
        return AdaptedRecipe(substitute=sub, ingredients=ingredients, instructions=instructions,
                             changes=changes, predicted_effects=effects)
