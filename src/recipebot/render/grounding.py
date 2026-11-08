"""Check LLM-written text against the facts it was given, sentence by sentence.

A sentence is removed if it cites a recipe ID, a number or an ingredient that does not
appear in the facts, or claims something the dataset does not record (cooking times,
servings, nutrition). The engine's own facts are always shown in full below the summary,
so removing a sentence never hides information.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from recipebot.nlp.text import fold

_ID = re.compile(r"\b(?:ar|epi|fn):[A-Za-z0-9./]+")
_NUMBER = re.compile(r"(?<![\w.:/])\d[\d,]*(?:\.\d+)?%?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")
_NOT_IN_DATASET = re.compile(
    r"\b(\d+\s*(?:minutes?|mins?|hours?|hrs?)|calories|kcal|servings?|serves|protein|"
    r"carbs?|nutrition|grams of fat)\b", re.I)


@dataclass
class GroundingReport:
    removed: list[tuple[str, str]] = field(default_factory=list)  # (sentence, reason)

    @property
    def ok(self) -> bool:
        return not self.removed


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip("%").rstrip(".") for n in _NUMBER.findall(text)}


class Grounder:
    def __init__(self, ingredient_names: set[str]):
        # Only reasonably common names, longest first, so "olive oil" wins over "oil".
        names = sorted((n for n in ingredient_names if len(n) > 2), key=len, reverse=True)
        self._ingredient = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")s?\b")

    def check(self, text: str, facts: str, allowed_ids: set[str]) -> tuple[str, GroundingReport]:
        report = GroundingReport()
        facts_folded = fold(facts)
        fact_numbers = _numbers(facts)
        kept = []
        for sentence in _SENTENCE.split(text.strip()):
            reason = self._problem(sentence, facts_folded, fact_numbers, allowed_ids)
            if reason:
                report.removed.append((sentence, reason))
            else:
                kept.append(sentence)
        return " ".join(kept), report

    def _problem(self, sentence: str, facts: str, numbers: set[str], ids: set[str]) -> str | None:
        claim = _NOT_IN_DATASET.search(sentence)
        if claim and fold(claim.group(0)) not in facts:
            return f"'{claim.group(0)}' is not recorded in the dataset"
        for rid in _ID.findall(sentence):
            # IDs may end in dots, so compare without trailing dots
            if rid.rstrip(".") not in {i.rstrip(".") for i in ids}:
                return f"recipe ID {rid.rstrip('.')} is not in the results"
        for number in _numbers(_ID.sub(" ", sentence)):
            if number not in numbers:
                return f"number {number} is not in the facts"
        for match in self._ingredient.finditer(fold(sentence)):
            if match.group(1) not in facts:
                return f"ingredient '{match.group(1)}' is not in the facts"
        return None
