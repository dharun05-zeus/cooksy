"""Load the YAML rule files and turn ingredient names into canonical names."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import inflect
import yaml

from recipebot.nlp.text import fold


@dataclass(frozen=True)
class Unit:
    key: str
    dimension: str  # "volume" (ml), "mass" (g) or "count"
    factor: float | None  # to ml or g; None for count units


@dataclass(frozen=True)
class CanonicalName:
    canonical: str
    extra: tuple[str, ...] = ()  # further ingredients named on the same line ("salt and pepper")
    form: str | None = None  # fresh / frozen / canned / dried


_INCH = re.compile(r"\d+(?:\s*-?\s*\d+/\d+)?\s*-?\s*(?:inch(?:es)?|in\.|\")")
_NON_NAME_CHARS = re.compile(r"[^a-z0-9%&'\s\-]")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def phrase_regex(phrases: list[str], plural: bool = True) -> re.Pattern[str] | None:
    """Whole-word regex for a list of phrases; spaces in a phrase also match hyphens."""
    if not phrases:
        return None
    parts = [
        re.escape(fold(p)).replace(r"\ ", r"[\s\-]+")
        for p in sorted(set(phrases), key=len, reverse=True)
    ]
    suffix = r"(?:s|es)?" if plural else ""
    return re.compile(rf"\b(?:{'|'.join(parts)}){suffix}\b")


class Lexicon:
    """All normalization rules, loaded once from the config directory."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        norm = _load(config_dir / "normalization.yaml")
        syn = _load(config_dir / "synonyms.yaml")
        units = _load(config_dir / "units.yaml")

        self.header_res = [re.compile(p) for p in norm.get("header_patterns", [])]
        self.boilerplate_res = [re.compile(p) for p in norm.get("instruction_boilerplate", [])]
        self.placeholder_title_res = [re.compile(p) for p in norm.get("placeholder_titles", [])]
        self.cut_re = phrase_regex(norm.get("cut_phrases", []), plural=False)
        self.form_words: dict[str, str] = norm.get("form_words", {})
        self.descriptors = set(norm.get("descriptors", []))
        self.edge_stopwords = set(norm.get("edge_stopwords", []))
        self.ground_keep = set(norm.get("ground_keep", []))
        self.no_singularize = set(norm.get("no_singularize", []))

        self.synonyms: dict[str, list[str]] = {}
        for key, value in (syn.get("synonyms") or {}).items():
            self.synonyms[fold(key)] = value if isinstance(value, list) else [value]
        self.family_of: dict[str, str] = {}
        for base, members in (syn.get("families") or {}).items():
            for member in members:
                self.family_of[fold(member)] = base

        self.units: dict[str, Unit] = {}
        for dimension in ("volume", "mass"):
            for key, spec in (units.get(dimension) or {}).items():
                for alias in spec["aliases"]:
                    self.units[alias] = Unit(key, dimension, float(spec["factor"]))
        for key, aliases in (units.get("count") or {}).items():
            for alias in aliases:
                self.units[alias] = Unit(key, "count", None)
        alias_alt = "|".join(
            re.escape(a).replace(r"\ ", r"\s+") for a in sorted(self.units, key=len, reverse=True)
        )
        self.unit_re = re.compile(rf"^(?P<unit>{alias_alt})\.?(?=[\s,)]|$)")

        staples = _load(config_dir / "staples.yaml")
        self.staples = {fold(s) for s in staples.get("staples", [])}

        self._inflect = inflect.engine()
        self._cache: dict[str, CanonicalName] = {}
        self._singular_cache: dict[str, str] = {}  # inflect is slow; words repeat a lot

    @cached_property
    def all_unit_aliases(self) -> set[str]:
        return set(self.units)

    def unit_for(self, alias: str) -> Unit:
        return self.units[re.sub(r"\s+", " ", alias)]

    def units_by_key(self, key: str) -> Unit:
        return self._unit_keys[key]

    @cached_property
    def _unit_keys(self) -> dict[str, Unit]:
        return {unit.key: unit for unit in self.units.values()}

    def base_of(self, canonical: str) -> str:
        """The family an ingredient belongs to ("cherry tomato" → "tomato")."""
        return self.family_of.get(canonical, canonical)

    def singular(self, word: str) -> str:
        cached = self._singular_cache.get(word)
        if cached is not None:
            return cached
        result = word
        protected = word in self.no_singularize or word.endswith(("ss", "us", "is"))
        if not protected and len(word) > 3:
            result = self._inflect.singular_noun(word) or word
        self._singular_cache[word] = result
        return result

    def canonicalize(self, name: str) -> CanonicalName:
        """Turn a free-text ingredient name into its canonical form.

        "2 large ripe Tomatoes, diced" has already lost its quantity and prep by the
        time it gets here; this step handles "large ripe Tomatoes" → "tomato".
        """
        key = name
        if key in self._cache:
            return self._cache[key]

        text = _INCH.sub(" ", fold(name))
        text = _NON_NAME_CHARS.sub(" ", text)
        text = re.sub(r"\s+", " ", text).strip(" -'")

        # 1. Synonym on the name as written, before descriptors are removed.
        result = self._from_synonym(text) or self._from_synonym(self._singular_last(text))
        if result is None:
            words = text.split()
            kept: list[str] = []
            form: str | None = None
            for i, word in enumerate(words):
                if word in self.form_words:
                    form = form or self.form_words[word]
                    continue
                if word == "ground":
                    following = words[i + 1] if i + 1 < len(words) else ""
                    if self.singular(following) not in self.ground_keep:
                        continue
                if word in self.descriptors or word.replace(".", "").isdigit():
                    continue
                kept.append(word)
            while kept and kept[0] in self.edge_stopwords:
                kept.pop(0)
            while kept and kept[-1] in self.edge_stopwords:
                kept.pop()
            phrase = self._singular_last(" ".join(kept))
            # 2. Synonym again, after clean-up ("fresh scallions" → "scallion" → "green onion").
            result = (
                self._from_synonym(phrase, form)
                or self._zest_or_juice(phrase, form)
                or self._staple_pair(phrase, form)
                or CanonicalName(phrase, (), form)
            )
        self._cache[key] = result
        return result

    def _zest_or_juice(self, phrase: str, form: str | None) -> CanonicalName | None:
        """ "zest of lemon" → "lemon zest"; "zest and juice of lime" → lime zest + lime juice."""
        match = re.match(r"^(zest|juice|zest and juice|juice and zest) of (\w+)$", phrase)
        if not match:
            return None
        fruit = self.singular(match.group(2))
        parts = [f"{fruit} {part}" for part in match.group(1).split(" and ")]
        return CanonicalName(parts[0], tuple(parts[1:]), form)

    def _staple_pair(self, phrase: str, form: str | None) -> CanonicalName | None:
        """ "kosher salt and black pepper" → salt + black pepper (both staples)."""
        if " and " not in phrase and " & " not in phrase:
            return None
        left, right = re.split(r" and | & ", phrase, maxsplit=1)
        names = [self.canonicalize(left).canonical, self.canonicalize(right).canonical]
        allowed = self.staples | {"white pepper"}
        if all(names) and all(n in allowed for n in names):
            return CanonicalName(names[0], (names[1],), form)
        return None

    def _singular_last(self, phrase: str) -> str:
        if not phrase:
            return phrase
        words = phrase.split()
        words[-1] = self.singular(words[-1])
        return " ".join(words)

    def _from_synonym(self, phrase: str, form: str | None = None) -> CanonicalName | None:
        names = self.synonyms.get(phrase)
        if not names:
            return None
        return CanonicalName(names[0], tuple(names[1:]), form)
