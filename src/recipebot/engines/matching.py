"""Rank existing recipes by how well they use the ingredients a user has.

Ranking is lexicographic so every position can be explained in one sentence. Default order:
  1. most of the user's ingredients used
  2. fewest extra ingredients to buy (staples such as salt and water are not counted)
  3. fewest instruction steps
  4. recipe ID (a stable tie-break)
A user preference ("fewest steps first") moves its key to the front.
Hard constraints (exclusions, step limit) are applied before ranking and never relaxed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from pydantic import BaseModel

from recipebot.engines.stats import RecipeFilter, apply_filter
from recipebot.engines.store import RecipeStore
from recipebot.nlp.text import fold

SortKey = Literal["most_matched", "fewest_extra", "fewest_steps"]
DEFAULT_ORDER: list[SortKey] = ["most_matched", "fewest_extra", "fewest_steps"]
SORT_LABELS = {
    "most_matched": "most of your ingredients used",
    "fewest_extra": "fewest extra ingredients needed",
    "fewest_steps": "fewest instruction steps",
}


class PantryItem(BaseModel):
    name: str
    quantity: float | None = None
    unit: str | None = None


class MatchRequest(BaseModel):
    pantry: list[PantryItem]
    exclude: list[str] = []
    max_steps: int | None = None
    preferences: list[SortKey] = []
    limit: int = 5


@dataclass
class MatchedRecipe:
    recipe_id: str
    title: str
    steps: int
    steps_method: str
    matched: list[str]
    extra_required: list[str]
    unused: list[str]
    staples_used: list[str]
    reason: str = ""
    quantity_notes: list[str] = field(default_factory=list)
    form_notes: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)  # only for closest alternatives


@dataclass
class MatchResult:
    pantry: list[str]  # the user's ingredients as interpreted
    results: list[MatchedRecipe]
    eligible: int  # recipes that use at least one pantry item and pass every hard constraint
    candidates: int  # recipes that use at least one pantry item
    ranking_rule: str
    filters: list[str]
    notes: list[str]
    alternatives: list[MatchedRecipe] = field(default_factory=list)  # break a constraint

    @property
    def no_match(self) -> bool:
        return not self.results


def match(store: RecipeStore, request: MatchRequest) -> MatchResult:
    notes: list[str] = []
    pantry: list[str] = []
    for item in request.pantry:
        resolved = store.resolve(item.name, "strict")
        if resolved.note:
            notes.append(resolved.note)
        if not resolved.matched_names or resolved.base in pantry:
            continue
        if _is_excluded(store, resolved.base, request.exclude):
            notes.append(f"'{item.name}' is excluded by your constraints, so it is not counted "
                         "as one of your ingredients.")
            continue
        pantry.append(resolved.base)
    order = list(dict.fromkeys([*request.preferences, *DEFAULT_ORDER]))
    ranking_rule = " → ".join(SORT_LABELS[k] for k in order) + " → recipe ID"
    if not pantry:
        reason = ("All the ingredients you listed are excluded by your constraints."
                  if any("excluded" in n for n in notes)
                  else "None of the ingredients you listed appear in the dataset.")
        return MatchResult([], [], 0, 0, ranking_rule, [], notes + [reason])

    uses_pantry = np.zeros(store.n, dtype=bool)
    for base in pantry:
        uses_pantry |= store.rows_mask(store.by_base.get(base))
    base_filter = RecipeFilter(exclude_duplicates=True)
    usable = apply_filter(store, base_filter).mask & uses_pantry
    hard = apply_filter(store, base_filter.model_copy(
        update={"exclude": request.exclude, "max_steps": request.max_steps}))
    eligible = usable & hard.mask

    results = _rank(store, np.flatnonzero(eligible), pantry, order, request.limit)
    alternatives: list[MatchedRecipe] = []
    if not results:
        alternatives = _rank(store, np.flatnonzero(usable), pantry, order, 3)
        for alt in alternatives:
            alt.violations = _violations(store, alt, request)
    _add_line_details(store, results + alternatives, request, pantry)
    if not any(item.quantity is not None for item in request.pantry):
        notes.append("No quantities were given, so this is a name-level match; whether you "
                     "have enough of each ingredient was not verified.")
    notes.extend(n for n in hard.notes[1:] if not n.startswith("Excluding"))
    return MatchResult(pantry, results, int(eligible.sum()), int(usable.sum()), ranking_rule,
                       hard.filters, notes, alternatives)


def _rank(store: RecipeStore, rows: np.ndarray, pantry: list[str], order: list[SortKey],
          limit: int) -> list[MatchedRecipe]:
    pantry_set = set(pantry)
    staples = store.lexicon.staples
    bases_col = store.recipes["bases"].to_numpy()
    steps_col = store.recipes["steps"].to_numpy()
    ids = store.recipes["recipe_id"].to_numpy()
    scored = []
    for i in rows:
        bases = set(bases_col[i])
        matched = len(bases & pantry_set)
        extra = len(bases - pantry_set - staples)
        keys = {"most_matched": -matched, "fewest_extra": extra, "fewest_steps": int(steps_col[i])}
        scored.append((tuple(keys[k] for k in order) + (ids[i],), i))
    scored.sort()
    out = []
    for _, i in scored[:limit]:
        row = store.recipes.iloc[i]
        bases = list(row["bases"])
        matched = [b for b in pantry if b in bases]
        extra = [b for b in bases if b not in pantry_set and b not in staples]
        out.append(MatchedRecipe(
            recipe_id=row["recipe_id"], title=row["title"], steps=int(row["steps"]),
            steps_method=row["steps_method"], matched=matched, extra_required=extra,
            unused=[b for b in pantry if b not in bases],
            staples_used=[b for b in bases if b in staples],
            reason=(f"uses {len(matched)} of your {len(pantry)} ingredients, needs "
                    f"{len(extra)} more, {int(row['steps'])} steps"),
        ))
    return out


def _is_excluded(store: RecipeStore, base: str, exclude: list[str]) -> bool:
    hit_categories = {h.category for h in store.allergens.classify(base)}
    for term in exclude:
        categories = store.allergens.categories_for(term)
        if categories and hit_categories & set(categories):
            return True
        if not categories and base in store.resolve(term, "broad").matched_names:
            return True
    return False


def _violations(store: RecipeStore, recipe: MatchedRecipe, request: MatchRequest) -> list[str]:
    row = store.get(recipe.recipe_id)
    problems = []
    for term in request.exclude:
        categories = store.allergens.categories_for(term)
        if categories:
            found = [c for c in categories if c in row["allergens"]]
            unsure = [c for c in categories if c in row["allergens_uncertain"]]
            if found:
                problems.append(f"contains {term} ({', '.join(found)})")
            elif unsure:
                problems.append(f"may contain {term} ({', '.join(unsure)}, uncertain)")
        else:
            resolved = store.resolve(term, "broad")
            hit = [c for c in row["canonicals"] if c in resolved.matched_names]
            if hit:
                problems.append(f"contains {', '.join(hit)} (you excluded {term})")
    if request.max_steps is not None and recipe.steps > request.max_steps:
        problems.append(f"{recipe.steps} steps (limit {request.max_steps})")
    return problems


def _add_line_details(store: RecipeStore, recipes: list[MatchedRecipe], request: MatchRequest,
                      pantry: list[str]) -> None:
    """Quantity and form checks need the parsed lines, read only for the recipes shown."""
    lines = store.lines([r.recipe_id for r in recipes])
    if lines.empty:
        return
    wanted = {}
    for item in request.pantry:
        base = store.resolve(item.name, "strict").base
        if base in pantry:
            wanted[base] = item
    for recipe in recipes:
        own = lines[lines["recipe_id"] == recipe.recipe_id]
        for base in recipe.matched:
            used = own[own["base"] == base]
            forms = sorted({f for f in used["form"].dropna() if f in ("canned", "frozen", "dried")})
            if forms:
                recipe.form_notes.append(f"uses {'/'.join(forms)} {base}")
            item = wanted.get(base)
            if item is not None and item.quantity is not None:
                recipe.quantity_notes.append(_quantity_note(store, base, item, used))


def _quantity_note(store: RecipeStore, base: str, item: PantryItem, used) -> str:
    have_dim, have_amount = _pantry_amount(store, item)
    needed = used[used["dimension"] == have_dim]["amount_base"].dropna()
    if have_dim is None or needed.empty or len(needed) != len(used):
        return f"{base}: quantity not verified (units not comparable with the recipe's)"
    need = float(needed.sum())
    unit = {"volume": "ml", "mass": "g", "count": ""}[have_dim]
    verdict = "enough" if have_amount >= need else "NOT enough"
    return f"{base}: needs {need:.0f}{unit}, you have {have_amount:.0f}{unit} → {verdict}"


def _pantry_amount(store: RecipeStore, item: PantryItem) -> tuple[str | None, float]:
    if item.quantity is None:
        return None, 0.0
    if not item.unit:
        return "count", item.quantity
    alias = fold(item.unit).rstrip(".")
    unit = store.lexicon.units.get(alias)
    if unit is None or unit.factor is None:
        return None, 0.0
    return unit.dimension, item.quantity * unit.factor
