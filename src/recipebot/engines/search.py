"""Keyword search (BM25) over titles and ingredient names, with hard filters.

Every recipe in the dataset is scored, then the filters are applied to all of them, so a
constraint such as "no dairy" is never limited to the top few hits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import bm25s
import numpy as np

from recipebot.engines.stats import RecipeFilter, apply_filter
from recipebot.engines.store import RecipeStore
from recipebot.nlp.lexicon import Lexicon
from recipebot.nlp.text import fold

TITLE_WEIGHT = 3  # title words are repeated so a dish name in the title outranks one in a list
STOPWORDS = {
    "a", "an", "and", "the", "of", "with", "for", "to", "in", "on", "recipe", "recipes", "my",
    "me", "some", "any", "find", "show", "give", "want", "make", "i", "please", "dish", "s",
    "something", "anything", "good", "nice", "easy", "simple", "quick", "best",
}
_WORD = re.compile(r"[a-z]+")


def tokenize(text: str, lexicon: Lexicon) -> list[str]:
    return [lexicon.singular(w) for w in _WORD.findall(fold(text)) if w not in STOPWORDS]


class SearchIndex:
    def __init__(self, retriever: bm25s.BM25, lexicon: Lexicon):
        self.retriever = retriever
        self.lexicon = lexicon

    @classmethod
    def build(cls, store: RecipeStore) -> SearchIndex:
        corpus = []
        for title, names in zip(store.recipes["title"], store.recipes["canonicals"], strict=True):
            tokens = tokenize(title, store.lexicon) * TITLE_WEIGHT
            for name in names:
                tokens.extend(tokenize(name, store.lexicon))
            corpus.append(tokens)
        retriever = bm25s.BM25()
        retriever.index(corpus, show_progress=False)
        return cls(retriever, store.lexicon)

    @classmethod
    def load_or_build(cls, store: RecipeStore, index_dir: Path | None) -> SearchIndex:
        if index_dir and (index_dir / "params.index.json").exists():
            retriever = bm25s.BM25.load(index_dir, show_progress=False)
            # Rows are matched to documents by position, so a stale index must be rebuilt.
            if retriever.scores["num_docs"] == store.n:
                return cls(retriever, store.lexicon)
        index = cls.build(store)
        if index_dir:
            index.retriever.save(index_dir, show_progress=False)
        return index

    def scores(self, query: str) -> np.ndarray:
        tokens = [t for t in tokenize(query, self.lexicon) if t in self.retriever.vocab_dict]
        if not tokens:
            return np.zeros(self.retriever.scores["num_docs"], dtype=np.float32)
        return self.retriever.get_scores(tokens)


@dataclass
class SearchHit:
    recipe_id: str
    title: str
    score: float
    steps: int
    ingredient_count: int
    matched_terms: list[str]
    evidence: list[str] = field(default_factory=list)  # why it fits the request


@dataclass
class SearchResult:
    query: str
    hits: list[SearchHit]
    total_matches: int  # recipes that match a search term and pass every filter
    filters: list[str]
    notes: list[str]
    unknown_terms: list[str] = field(default_factory=list)


def search(store: RecipeStore, index: SearchIndex, query: str, f: RecipeFilter,
           k: int = 5) -> SearchResult:
    # Required ingredients also count as search words, so "chicken and rice" ranks well.
    full_query = " ".join([query, *f.include_all, *f.include_any]).strip()
    out = apply_filter(store, f.model_copy(update={"exclude_duplicates": True}))
    scores = index.scores(full_query)
    eligible = out.mask & (scores > 0)
    candidates = np.flatnonzero(eligible)
    ids = store.recipes["recipe_id"].to_numpy()
    # Highest score first; ties broken by recipe ID so results are reproducible.
    top = candidates[np.lexsort((ids[candidates], -scores[candidates]))][:k]

    tokens = tokenize(full_query, store.lexicon)
    unknown = [t for t in tokens if t not in index.retriever.vocab_dict]
    hits = []
    for i in top:
        row = store.recipes.iloc[i]
        doc_words = set(tokenize(row["title"] + " " + " ".join(row["canonicals"]), store.lexicon))
        hits.append(SearchHit(
            recipe_id=row["recipe_id"], title=row["title"], score=round(float(scores[i]), 2),
            steps=int(row["steps"]), ingredient_count=int(row["ingredient_count"]),
            matched_terms=[t for t in dict.fromkeys(tokens) if t in doc_words],
            evidence=_constraint_evidence(store, row, f),
        ))
    notes = [n for n in out.notes[1:] if not n.startswith("Excluding")]
    unfiltered = apply_filter(store, RecipeFilter(exclude_duplicates=True)).mask & (scores > 0)
    removed = int((unfiltered & ~out.mask).sum())
    if removed and (f.exclude or f.max_steps is not None):
        notes.append(f"Your constraints removed {removed:,} of the {int(unfiltered.sum()):,} "
                     "recipes matching the search words (uncertain cases are removed too).")
    if unknown:
        notes.append("Not found anywhere in the dataset: " + ", ".join(unknown))
    return SearchResult(full_query, hits, int(eligible.sum()), out.filters, notes, unknown)


def _constraint_evidence(store: RecipeStore, row, f: RecipeFilter) -> list[str]:
    """Explain, from the recipe's own ingredient list, why it satisfies each exclusion."""
    evidence = []
    n = int(row["ingredient_count"])
    for term in f.exclude:
        categories = store.allergens.categories_for(term)
        if categories:
            detail = "" if categories == [term] else f" ({', '.join(categories)})"
            evidence.append(f"no {term}{detail} found in its {n} ingredient lines, including "
                            "uncertain items")
        else:
            evidence.append(f"none of its {n} ingredients contains '{term}'")
    if f.max_steps is not None:
        evidence.append(f"{int(row['steps'])} steps (limit {f.max_steps})")
    return evidence
