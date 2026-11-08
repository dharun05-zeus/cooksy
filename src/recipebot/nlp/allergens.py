"""Decide which allergen / diet categories an ingredient line belongs to."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from recipebot.nlp.lexicon import phrase_regex
from recipebot.nlp.text import fold

Status = Literal["contains", "uncertain"]

# Restrictions named after a diet: shown as the diet ("vegetarian"), not as "no vegetarian".
DIETS = {"vegetarian", "vegan", "pescatarian"}


def constraint_label(term: str) -> str:
    """ "dairy" -> "no dairy"; "vegetarian" -> "vegetarian"."""
    return term if term.lower() in DIETS else f"no {term}"


@dataclass(frozen=True)
class AllergenHit:
    category: str
    status: Status
    evidence: str  # the words in the line that triggered the hit


@dataclass(frozen=True)
class _Category:
    terms: re.Pattern[str] | None
    exceptions: re.Pattern[str] | None
    uncertain: re.Pattern[str] | None


class AllergenLexicon:
    def __init__(self, config_dir: Path):
        data = yaml.safe_load((config_dir / "allergens.yaml").read_text(encoding="utf-8"))
        self.marker_re = phrase_regex(data.get("uncertain_markers", []), plural=False)
        self.categories: dict[str, _Category] = {
            name: _Category(
                terms=phrase_regex(spec.get("terms", [])),
                exceptions=phrase_regex(spec.get("exceptions", [])),
                uncertain=phrase_regex(spec.get("uncertain", [])),
            )
            for name, spec in data["categories"].items()
        }
        self.aliases: dict[str, list[str]] = {
            fold(k): v for k, v in (data.get("aliases") or {}).items()
        }

    def classify(self, line: str) -> list[AllergenHit]:
        """Check one full ingredient line (including any notes after the comma).

        The whole line is checked, not just the parsed name, so
        "2 tbsp oil, such as peanut oil" is still caught.
        """
        text = fold(line)
        has_marker = bool(self.marker_re and self.marker_re.search(text))
        hits: list[AllergenHit] = []
        for name, cat in self.categories.items():
            checked = cat.exceptions.sub(" ", text) if cat.exceptions else text
            match = cat.terms.search(checked) if cat.terms else None
            if match:
                status: Status = "uncertain" if has_marker else "contains"
                hits.append(AllergenHit(name, status, match.group(0)))
                continue
            match = cat.uncertain.search(checked) if cat.uncertain else None
            if match:
                hits.append(AllergenHit(name, "uncertain", match.group(0)))
        return hits

    def categories_for(self, term: str) -> list[str] | None:
        """Map a user's word ("vegan", "nuts", "dairy") to categories, or None if it is
        not a category word and should be treated as an ingredient name."""
        term = fold(term).strip()
        if term in self.categories:
            return [term]
        return self.aliases.get(term)
