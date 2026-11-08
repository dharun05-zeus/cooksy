"""Offline build: raw JSON → cleaned, normalized Parquet tables.

Outputs (in data/processed):
    recipes.parquet      one row per record, originals kept untouched
    ingredients.parquet  one row per ingredient line, with the parse result
    build_report.json    counts of every exclusion, for the README and the stats answers
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from recipebot.data.loader import iter_raw_recipes
from recipebot.data.models import RawRecipe
from recipebot.nlp.allergens import AllergenHit, AllergenLexicon
from recipebot.nlp.ingredient_parser import ParsedIngredient, parse_line
from recipebot.nlp.lexicon import Lexicon
from recipebot.nlp.steps import count_steps, split_sentences
from recipebot.nlp.text import clean_line, fold

_SUBSTITUTE = re.compile(r"\bsubstitut|\bin place of\b|\binstead of\b", re.IGNORECASE)


@dataclass
class BuildReport:
    total_records: int = 0
    empty_records: int = 0
    no_title: int = 0
    no_ingredients: int = 0
    no_instructions: int = 0
    complete_recipes: int = 0
    exact_duplicates: int = 0
    ingredient_lines: int = 0
    header_lines: int = 0
    steps_by_sentence: int = 0
    substitution_pairs: int = 0
    substitution_notes: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0


class _Builder:
    def __init__(self, lexicon: Lexicon, allergens: AllergenLexicon):
        self.lexicon = lexicon
        self.allergens = allergens
        self.recipes: dict[str, list] = defaultdict(list)
        self.lines: dict[str, list] = defaultdict(list)
        self.pairs: dict[str, list] = defaultdict(list)  # "butter or margarine" lines
        self.notes: dict[str, list] = defaultdict(list)  # "you can substitute ..." sentences
        self._parse_cache: dict[str, ParsedIngredient | None] = {}
        self._allergen_cache: dict[str, list[AllergenHit]] = {}
        self.seen: dict[tuple, str] = {}
        self.report = BuildReport()

    def parse(self, raw: str) -> ParsedIngredient | None:
        if raw not in self._parse_cache:
            self._parse_cache[raw] = parse_line(raw, self.lexicon)
        return self._parse_cache[raw]

    def classify(self, text: str) -> list[AllergenHit]:
        if text not in self._allergen_cache:
            self._allergen_cache[text] = self.allergens.classify(text)
        return self._allergen_cache[text]

    def add_empty(self, source: str, key: str) -> None:
        self.report.empty_records += 1
        self._add_recipe(
            recipe_id=f"{source}:{key}", source=source, source_key=key, title="",
            ingredients_raw=[], instructions_raw="", is_empty=True,
        )

    def add(self, recipe: RawRecipe) -> None:
        r = self.report
        # line_no is the position in the ingredient list as displayed (non-empty lines,
        # headings included), so substitution replaces exactly the line the user sees.
        numbered: list[tuple[int, ParsedIngredient]] = []
        position = 0
        for line in recipe.ingredients:
            p = self.parse(line)
            if p is None:
                continue
            if not p.is_header:
                numbered.append((position, p))
            position += 1
        ingredients = [p for _, p in numbered]
        r.ingredient_lines += len(ingredients)
        r.header_lines += position - len(ingredients)

        canonicals: list[str] = []
        bases: list[str] = []
        contains: set[str] = set()
        uncertain: set[str] = set()
        for line_no, p in numbered:
            hits = self.classify(p.text)
            for hit in hits:
                (contains if hit.status == "contains" else uncertain).add(hit.category)
            for name in (p.canonical, *p.extra):
                if name and name not in canonicals:
                    canonicals.append(name)
                base = self.lexicon.base_of(name) if name else ""
                if base and base not in bases:
                    bases.append(base)
            self._add_line(recipe.recipe_id, line_no, p, hits)
            for alternative in p.alternatives:
                self.pairs["recipe_id"].append(recipe.recipe_id)
                self.pairs["line_no"].append(line_no)
                self.pairs["primary"].append(p.canonical)
                self.pairs["alternative"].append(alternative)
                self.pairs["text"].append(p.text)

        for sentence in split_sentences(recipe.instructions.replace("\n", " ")):
            if _SUBSTITUTE.search(sentence):
                self.notes["recipe_id"].append(recipe.recipe_id)
                self.notes["sentence"].append(sentence.strip())

        steps = count_steps(recipe.instructions, self.lexicon.boilerplate_res)
        title = clean_line(recipe.title)
        placeholder = any(p.search(fold(title)) for p in self.lexicon.placeholder_title_res)
        has_title = bool(title) and not placeholder
        has_ing, has_ins = bool(ingredients), steps.steps > 0
        complete = has_title and has_ing and has_ins
        r.no_title += not has_title
        r.no_ingredients += not has_ing
        r.no_instructions += not has_ins
        r.steps_by_sentence += complete and steps.method == "sentence"

        duplicate_of = None
        if complete:
            key = (fold(title), tuple(sorted(canonicals)))
            duplicate_of = self.seen.get(key)
            if duplicate_of is None:
                self.seen[key] = recipe.recipe_id
            else:
                r.exact_duplicates += 1

        self._add_recipe(
            recipe_id=recipe.recipe_id, source=recipe.source, source_key=recipe.source_key,
            title=title, ingredients_raw=recipe.ingredients,
            instructions_raw=recipe.instructions, is_empty=False,
            has_title=has_title, has_ingredients=has_ing, has_instructions=has_ins,
            is_complete=complete, ingredient_count=len(ingredients),
            canonicals=canonicals, bases=bases,
            allergens=sorted(contains), allergens_uncertain=sorted(uncertain - contains),
            steps=steps.steps, steps_method=steps.method, sentence_count=steps.sentences,
            duplicate_of=duplicate_of,
        )

    def _add_recipe(self, **values) -> None:
        defaults = dict(
            has_title=False, has_ingredients=False, has_instructions=False, is_complete=False,
            ingredient_count=0, canonicals=[], bases=[], allergens=[], allergens_uncertain=[],
            steps=0, steps_method="none", sentence_count=0, duplicate_of=None,
        )
        defaults.update(values)
        for key, value in defaults.items():
            self.recipes[key].append(value)
        self.report.total_records += 1
        source = defaults["source"]
        self.report.by_source[source] = self.report.by_source.get(source, 0) + 1

    def _add_line(self, recipe_id: str, line_no: int, p: ParsedIngredient, hits) -> None:
        row = self.lines
        row["recipe_id"].append(recipe_id)
        row["line_no"].append(line_no)
        row["raw"].append(p.raw)
        row["text"].append(p.text)
        row["quantity"].append(p.quantity)
        row["quantity_max"].append(p.quantity_max)
        row["unit"].append(p.unit)
        row["dimension"].append(p.dimension)
        row["amount_base"].append(p.amount_base)
        row["name"].append(p.name)
        row["canonical"].append(p.canonical)
        row["base"].append(p.base)
        row["extra"].append(list(p.extra))
        row["form"].append(p.form)
        row["alternatives"].append(list(p.alternatives))
        row["prep"].append(p.prep)
        row["optional"].append(p.optional)
        row["allergens"].append([h.category for h in hits if h.status == "contains"])
        row["allergens_uncertain"].append([h.category for h in hits if h.status == "uncertain"])
        row["allergen_evidence"].append([f"{h.category}:{h.evidence}" for h in hits])


def build(raw_dir: Path, out_dir: Path, config_dir: Path) -> BuildReport:
    started = time.perf_counter()
    builder = _Builder(Lexicon(config_dir), AllergenLexicon(config_dir))
    for item in iter_raw_recipes(raw_dir):
        if isinstance(item, tuple):
            builder.add_empty(*item)
        else:
            builder.add(item)

    report = builder.report
    report.complete_recipes = sum(builder.recipes["is_complete"])
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(builder.recipes).to_parquet(out_dir / "recipes.parquet", index=False)
    pd.DataFrame(builder.lines).to_parquet(out_dir / "ingredients.parquet", index=False)
    pair_columns = ["recipe_id", "line_no", "primary", "alternative", "text"]
    pairs = pd.DataFrame(builder.pairs, columns=pair_columns)
    pairs.to_parquet(out_dir / "substitution_pairs.parquet", index=False)
    notes = pd.DataFrame(builder.notes, columns=["recipe_id", "sentence"])
    notes.to_parquet(out_dir / "substitution_notes.parquet", index=False)
    report.substitution_pairs, report.substitution_notes = len(pairs), len(notes)
    report.seconds = round(time.perf_counter() - started, 1)
    (out_dir / "build_report.json").write_text(json.dumps(asdict(report), indent=2))
    return report
