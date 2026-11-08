"""Statistics computed with pandas over the complete filtered set, never by the LLM.

Every result states the filters, the number of recipes analyzed and the method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from pydantic import BaseModel

from recipebot.data.models import Source
from recipebot.engines.store import MatchMode, RecipeStore
from recipebot.nlp.allergens import DIETS, constraint_label


class RecipeFilter(BaseModel):
    include_all: list[str] = []  # must contain every one of these ingredients
    include_any: list[str] = []  # must contain at least one
    exclude: list[str] = []  # ingredients or categories ("dairy", "vegan", "peanuts")
    title_contains: list[str] = []
    sources: list[Source] = []
    min_steps: int | None = None
    max_steps: int | None = None
    match_mode: MatchMode = "strict"
    exclude_duplicates: bool = False


@dataclass
class FilterOutcome:
    mask: np.ndarray
    universe: int
    filters: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class StatsResult(BaseModel):
    operation: str
    answer: str
    value: float | int | None = None
    numerator: int | None = None
    denominator: int
    filters: list[str]
    method: str
    notes: list[str] = []
    rows: list[dict] = []
    sample_ids: list[str] = []

    def explain(self) -> str:
        lines = [f"Answer: {self.answer}"]
        lines.append("Filters: " + ("; ".join(self.filters) if self.filters else "none"))
        lines.append(f"Recipes analyzed: {self.denominator:,}")
        lines.append(f"Method: {self.method}")
        for row in self.rows:
            lines.append("  " + " | ".join(f"{k}: {v}" for k, v in row.items()))
        if self.sample_ids:
            lines.append("Example recipe IDs: " + ", ".join(self.sample_ids))
        lines.extend(f"Note: {n}" for n in self.notes)
        return "\n".join(lines)


def apply_filter(store: RecipeStore, f: RecipeFilter) -> FilterOutcome:
    universe = store.complete.copy()
    notes = [f"Dataset: {store.universe_note()}."]
    filters: list[str] = []
    if f.exclude_duplicates:
        universe &= ~store.is_duplicate
        filters.append("exact duplicates removed (same title and ingredient set)")
    if f.sources:
        universe &= store.recipes["source"].isin(f.sources).to_numpy()
        filters.append("source in " + ", ".join(f.sources))
    mask = universe.copy()

    for term in f.include_all:
        resolved = store.resolve(term, f.match_mode)
        mask &= store.ingredient_mask(resolved)
        filters.append(f"contains {resolved.describe()}")
        if resolved.note:
            notes.append(resolved.note)
    if f.include_any:
        any_mask = np.zeros(store.n, dtype=bool)
        described = []
        for term in f.include_any:
            resolved = store.resolve(term, f.match_mode)
            any_mask |= store.ingredient_mask(resolved)
            described.append(resolved.describe())
            if resolved.note:
                notes.append(resolved.note)
        mask &= any_mask
        filters.append("contains any of " + ", ".join(described))
    for words in f.title_contains:
        mask &= store.title_mask(words)
        filters.append(f"title contains '{words}'")

    for term in f.exclude:
        categories = store.allergens.categories_for(term)
        if categories:
            contains, uncertain = store.category_masks(categories)
            removed, removed_unsure = int((mask & contains).sum()), int((mask & uncertain).sum())
            mask &= ~(contains | uncertain)
            if term.lower() in DIETS:  # "vegetarian (excludes meat, fish, shellfish)"
                filters.append(f"{term} (excludes {', '.join(categories)})")
                what = ", ".join(categories)
            else:
                detail = "" if categories == [term] else f" ({', '.join(categories)})"
                filters.append(f"excludes {term}{detail}")
                what = "it"
            notes.append(
                f"{constraint_label(term).capitalize()}: removed {removed:,} recipes that "
                f"contain {what} and {removed_unsure:,} where it is uncertain (e.g. margarine, "
                "chocolate); hard constraints remove uncertain cases too."
            )
        else:
            # Exclusions are always broad: "no peanuts" also removes peanut oil and peanut butter.
            resolved = store.resolve(term, "broad")
            mask &= ~store.ingredient_mask(resolved)
            filters.append(f"excludes {resolved.describe()}")
            if not resolved.matched_names:
                notes.append(f"'{term}' does not appear in the dataset, so excluding it "
                             "removed nothing.")
            elif resolved.note:
                notes.append(resolved.note)

    steps = store.recipes["steps"].to_numpy()
    if f.min_steps is not None:
        mask &= steps >= f.min_steps
        filters.append(f"at least {f.min_steps} steps")
    if f.max_steps is not None:
        mask &= steps <= f.max_steps
        filters.append(f"at most {f.max_steps} steps")
    return FilterOutcome(mask, int(universe.sum()), filters, notes)


def _sample_ids(store: RecipeStore, mask: np.ndarray, k: int = 5) -> list[str]:
    return [str(rid) for rid in np.sort(store.recipes["recipe_id"].to_numpy()[mask])[:k]]


def count(store: RecipeStore, f: RecipeFilter) -> StatsResult:
    out = apply_filter(store, f)
    n = int(out.mask.sum())
    return StatsResult(
        operation="count", answer=f"{n:,} recipes match.", value=n, numerator=n,
        denominator=out.universe, filters=out.filters, notes=out.notes,
        method="Count of complete recipes whose normalized ingredient set satisfies every filter.",
        sample_ids=_sample_ids(store, out.mask),
    )


def percentage(store: RecipeStore, f: RecipeFilter, of: RecipeFilter | None = None) -> StatsResult:
    """Share of the recipes matching `of` (default: the whole dataset) that also match `f`."""
    default_of = RecipeFilter(sources=f.sources, exclude_duplicates=f.exclude_duplicates)
    denominator_out = apply_filter(store, of or default_of)
    out = apply_filter(store, f)
    numerator_mask = out.mask & denominator_out.mask
    n, d = int(numerator_mask.sum()), int(denominator_out.mask.sum())
    pct = round(100 * n / d, 2) if d else 0.0
    denominator_desc = "; ".join(denominator_out.filters) or "all complete recipes"
    return StatsResult(
        operation="percentage", answer=f"{n:,} of {d:,} recipes ({pct}%).", value=pct,
        numerator=n, denominator=d, filters=out.filters, notes=out.notes,
        method=f"numerator / denominator × 100, where the denominator is {denominator_desc}.",
        sample_ids=_sample_ids(store, numerator_mask),
    )


def top_ingredients(store: RecipeStore, f: RecipeFilter, k: int = 10,
                    exclude_staples: bool = False) -> StatsResult:
    out = apply_filter(store, f)
    n = int(out.mask.sum())
    exploded = store.recipes.loc[out.mask, "bases"].explode().dropna()
    if exclude_staples:
        exploded = exploded[~exploded.isin(store.lexicon.staples)]
    counts = exploded.value_counts()
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    rows = [
        {"rank": i + 1, "ingredient": name, "recipes": int(c), "share": f"{100 * c / n:.1f}%"}
        for i, (name, c) in enumerate(ranked)
    ] if n else []
    notes = out.notes + (["Staples (salt, pepper, water...) left out."] if exclude_staples else [])
    return StatsResult(
        operation="top_ingredients",
        answer=f"Most common ingredients in {n:,} recipes: "
        + ", ".join(r["ingredient"] for r in rows),
        value=None, denominator=n, filters=out.filters, notes=notes, rows=rows,
        method="Each recipe counts once per base ingredient (varieties merged, e.g. cherry "
               "tomato → tomato); ties broken alphabetically.",
    )


def ingredient_count_stats(store: RecipeStore, f: RecipeFilter) -> StatsResult:
    out = apply_filter(store, f)
    values = store.recipes.loc[out.mask, "ingredient_count"].to_numpy()
    if not len(values):
        return StatsResult(operation="ingredient_count_stats", answer="No recipes match.",
                           denominator=0, filters=out.filters, notes=out.notes, method="n/a")
    mean, median = float(np.mean(values)), float(np.median(values))
    rows = [{"mean": round(mean, 2), "median": median, "min": int(values.min()),
             "max": int(values.max()), "std": round(float(np.std(values)), 2)}]
    return StatsResult(
        operation="ingredient_count_stats",
        answer=f"Mean {mean:.2f} ingredients, median {median:g}, over {len(values):,} recipes.",
        value=round(mean, 2), denominator=len(values), filters=out.filters, notes=out.notes,
        rows=rows,
        method="Ingredient count = number of ingredient lines, excluding section headings "
               "('For the sauce:') and Allrecipes 'ADVERTISEMENT' artefacts.",
    )


def rank_by_steps(store: RecipeStore, f: RecipeFilter, k: int = 5,
                  order: Literal["fewest", "most"] = "fewest") -> StatsResult:
    out = apply_filter(store, f)
    subset = store.recipes.loc[out.mask, ["recipe_id", "title", "steps", "steps_method"]]
    ascending = order == "fewest"
    subset = subset.sort_values(["steps", "recipe_id"], ascending=[ascending, True])
    top = subset.head(k)
    rows = [
        {"rank": i + 1, "recipe_id": r.recipe_id, "title": r.title, "steps": int(r.steps),
         "counted_by": r.steps_method}
        for i, r in enumerate(top.itertuples())
    ]
    notes = list(out.notes)
    if len(top):
        cutoff = int(top["steps"].iloc[-1])
        tied = int((subset["steps"] == cutoff).sum())
        shown = int((top["steps"] == cutoff).sum())
        if tied > shown:
            notes.append(f"{tied:,} recipes have {cutoff} step(s); the {shown} shown are the "
                         "first by recipe ID (deterministic tie-break).")
    if any(r["counted_by"] == "sentence" for r in rows):
        notes.append("Recipes marked 'sentence' store their instructions as one paragraph, "
                     "so steps were counted as sentences (approximate).")
    return StatsResult(
        operation="rank_by_steps",
        answer=f"{order.capitalize()} instruction steps among {len(subset):,} matching recipes.",
        value=None, denominator=len(subset), filters=out.filters, notes=notes, rows=rows,
        method="Step = one non-empty instruction line, excluding site boilerplate; a recipe "
               "stored as one paragraph is split into sentences. Sorted by steps, then ID.",
    )
