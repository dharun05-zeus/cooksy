"""In-memory access to the processed recipes, with ingredient and allergen indexes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from rapidfuzz import process

from recipebot.nlp.allergens import AllergenLexicon
from recipebot.nlp.lexicon import Lexicon
from recipebot.nlp.text import clean_line, fold

MatchMode = Literal["strict", "broad"]


@dataclass
class ResolvedTerm:
    """How a user's ingredient word was interpreted. Shown to the user, so the rule is visible."""

    term: str
    base: str
    mode: MatchMode
    matched_names: list[str] = field(default_factory=list)  # canonical names counted
    note: str | None = None  # e.g. a spelling correction or "not in the dataset"

    def describe(self) -> str:
        names = ", ".join(self.matched_names[:6])
        more = f" and {len(self.matched_names) - 6} more" if len(self.matched_names) > 6 else ""
        if self.mode == "strict":
            rule = "same ingredient or its varieties"
        else:
            rule = "any name containing it"
        return f"'{self.base}' ({rule}: {names}{more})" if names else f"'{self.base}' (no match)"


def _index(column: pd.Series) -> dict[str, np.ndarray]:
    """Map each value of a list column to the row positions that contain it."""
    exploded = column.explode().dropna()
    exploded = exploded[exploded != ""]
    rows = exploded.index.to_numpy()
    return {key: rows[pos] for key, pos in exploded.groupby(exploded.values).indices.items()}


class RecipeStore:
    def __init__(self, recipes: pd.DataFrame, lexicon: Lexicon, allergens: AllergenLexicon,
                 build_report: dict | None = None, processed_dir: Path | None = None):
        self.processed_dir = processed_dir
        self.recipes = recipes.reset_index(drop=True)
        self.lexicon = lexicon
        self.allergens = allergens
        self.build_report = build_report or {}
        self.n = len(self.recipes)
        self.complete = self.recipes["is_complete"].to_numpy(bool)
        self.is_duplicate = self.recipes["duplicate_of"].notna().to_numpy()
        self.title_folded = self.recipes["title"].map(fold)
        self.position = {rid: i for i, rid in enumerate(self.recipes["recipe_id"])}

        self.by_base = _index(self.recipes["bases"])
        self.by_canonical = _index(self.recipes["canonicals"])
        self.with_allergen = _index(self.recipes["allergens"])
        self.with_uncertain = _index(self.recipes["allergens_uncertain"])
        self.canonical_names = sorted(self.by_canonical)
        self.base_names = sorted(self.by_base)

    @classmethod
    def load(cls, processed_dir: Path, config_dir: Path) -> RecipeStore:
        recipes = pd.read_parquet(processed_dir / "recipes.parquet")
        report_path = processed_dir / "build_report.json"
        report = json.loads(report_path.read_text()) if report_path.exists() else {}
        return cls(recipes, Lexicon(config_dir), AllergenLexicon(config_dir), report,
                   processed_dir)

    # ----- masks -------------------------------------------------------------------

    def rows_mask(self, rows: np.ndarray | None) -> np.ndarray:
        mask = np.zeros(self.n, dtype=bool)
        if rows is not None and len(rows):
            mask[rows] = True
        return mask

    def resolve(self, term: str, mode: MatchMode = "strict") -> ResolvedTerm:
        canonical = self.lexicon.canonicalize(term).canonical
        base = self.lexicon.base_of(canonical) if canonical else fold(term)
        note = None
        if base not in self.by_base:
            guess = process.extractOne(base, self.base_names, score_cutoff=88)
            if guess:
                note = f"'{term}' is not in the dataset; using the closest name '{guess[0]}'"
                base = guess[0]
            else:
                missing = f"'{term}' does not appear in the dataset"
                return ResolvedTerm(term, base, mode, [], missing)
        if mode == "strict":
            names = [base] + [m for m, b in self.lexicon.family_of.items()
                              if b == base and m in self.by_canonical]
        else:
            pattern = re.compile(rf"\b{re.escape(base)}(?:s|es)?\b")
            names = [c for c in self.canonical_names if pattern.search(c)]
            names.extend(m for m, b in self.lexicon.family_of.items()
                         if b == base and m in self.by_canonical and m not in names)
        names = [c for c in dict.fromkeys(names) if c in self.by_canonical]
        names.sort(key=lambda c: -len(self.by_canonical[c]))
        return ResolvedTerm(term, base, mode, names, note)

    def ingredient_mask(self, resolved: ResolvedTerm) -> np.ndarray:
        if resolved.mode == "strict":
            return self.rows_mask(self.by_base.get(resolved.base))
        mask = np.zeros(self.n, dtype=bool)
        for name in resolved.matched_names:
            mask[self.by_canonical.get(name, [])] = True
        return mask

    def category_masks(self, categories: list[str]) -> tuple[np.ndarray, np.ndarray]:
        """(definitely contains, possibly contains) for a list of allergen categories."""
        contains = np.zeros(self.n, dtype=bool)
        uncertain = np.zeros(self.n, dtype=bool)
        for cat in categories:
            contains |= self.rows_mask(self.with_allergen.get(cat))
            uncertain |= self.rows_mask(self.with_uncertain.get(cat))
        return contains, uncertain & ~contains

    def title_mask(self, words: str) -> np.ndarray:
        pattern = rf"\b{re.escape(fold(words))}"
        return self.title_folded.str.contains(pattern, regex=True).to_numpy(bool)

    # ----- records -----------------------------------------------------------------

    def get(self, recipe_id: str) -> pd.Series | None:
        pos = self.position.get(recipe_id)
        return None if pos is None else self.recipes.iloc[pos]

    def lines(self, recipe_ids: list[str]) -> pd.DataFrame:
        """Parsed ingredient lines for a few recipes, read from disk on demand
        (the full table has ~1.3M rows, so it is not kept in memory)."""
        if not recipe_ids or self.processed_dir is None:
            return pd.DataFrame()
        return pd.read_parquet(
            self.processed_dir / "ingredients.parquet",
            filters=[("recipe_id", "in", list(recipe_ids))],
        )

    def display_ingredients(self, recipe_id: str) -> list[str]:
        """Ingredient lines for display: the original text with only the scraping
        artefact ('ADVERTISEMENT') and extra spaces removed."""
        row = self.get(recipe_id)
        if row is None:
            return []
        return [t for t in (clean_line(x) for x in row["ingredients_raw"]) if t]

    def universe_note(self) -> str:
        r = self.build_report
        if not r:
            return f"{int(self.complete.sum()):,} complete recipes"
        excluded = r["total_records"] - r["complete_recipes"]
        return (
            f"{r['complete_recipes']:,} complete recipes (title, ingredients and instructions "
            f"present) out of {r['total_records']:,} records; {excluded:,} incomplete records "
            f"excluded ({r['empty_records']} empty)"
        )
