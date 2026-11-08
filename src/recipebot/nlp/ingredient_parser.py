"""Parse one raw ingredient line into quantity, unit, canonical name and notes.

Example:
    "2 (14.5 ounce) cans diced tomatoes, drained ADVERTISEMENT"
    → quantity 2, unit "can", amount 822 g, canonical "tomato", form "canned",
      prep "drained"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from recipebot.nlp.lexicon import Lexicon
from recipebot.nlp.text import clean_line, fold

_NUM = r"(?:\d+\s*-\s*\d+/\d+|\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\.\d+|\d+)"
_QTY = re.compile(rf"^(?P<q1>{_NUM})(?:\s*(?:-|to)\s*(?P<q2>{_NUM}))?\s*")
_WORD_NUMBERS = {
    "a": 1.0, "an": 1.0, "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0,
    "six": 6.0, "seven": 7.0, "eight": 8.0, "nine": 9.0, "ten": 10.0, "twelve": 12.0,
    "dozen": 12.0, "half": 0.5,
}
_WORD_QTY = re.compile(rf"^(?P<w>{'|'.join(_WORD_NUMBERS)})\s+")
_PAREN = re.compile(r"\(([^)]*)\)")
_ALTERNATIVE = re.compile(r"\s+(?:and/or|or)\s+")


@dataclass(slots=True)
class ParsedIngredient:
    raw: str  # the line exactly as in the dataset
    text: str  # cleaned for display (artefacts removed)
    is_header: bool = False  # "For the sauce:"
    quantity: float | None = None
    quantity_max: float | None = None  # upper end of a range ("2 to 3 cups")
    unit: str | None = None
    dimension: str | None = None  # volume / mass / count
    amount_base: float | None = None  # in ml (volume) or g (mass) when convertible
    name: str = ""  # the name part as written ("large ripe tomatoes")
    canonical: str = ""  # normalized ("tomato")
    base: str = ""  # family ("cherry tomato" → "tomato")
    extra: tuple[str, ...] = ()  # more ingredients named on the line ("salt and pepper")
    form: str | None = None
    alternatives: tuple[str, ...] = field(default_factory=tuple)  # "butter or margarine"
    prep: str = ""
    optional: bool = False


def _to_number(token: str) -> float:
    token = token.strip()
    mixed = re.match(r"^(\d+)\s*(?:-|\s)\s*(\d+)/(\d+)$", token)
    if mixed:
        whole, num, den = mixed.groups()
        return int(whole) + int(num) / int(den)
    if "/" in token:
        num, den = token.split("/")
        return int(num) / int(den) if int(den) else 0.0
    return float(token)


def take_quantity(text: str) -> tuple[float | None, float | None, str]:
    match = _QTY.match(text)
    if match:
        q1 = _to_number(match.group("q1"))
        q2 = _to_number(match.group("q2")) if match.group("q2") else None
        return q1, q2, text[match.end():]
    match = _WORD_QTY.match(text)
    if match:
        return _WORD_NUMBERS[match.group("w")], None, text[match.end():]
    return None, None, text


def take_unit(text: str, lexicon: Lexicon) -> tuple[str | None, str]:
    text = text.lstrip("-")
    match = lexicon.unit_re.match(text)
    if not match:
        return None, text
    unit = lexicon.unit_for(match.group("unit")).key
    rest = text[match.end():].lstrip(" .")
    # A second container word after the unit is not part of the name:
    #   "1 (12 ounce) can or bottle beer"  -> "beer"
    #   "1 lb. bag of medium-wide noodles" -> "medium-wide noodles"
    alternative = re.match(r"^(?:or|and)\s+(\S+?)\.?\s+", rest)
    container = re.match(r"^(\S+?)\.?\s+of\s+", rest)
    for match in (alternative, container):
        if match and match.group(1) in lexicon.all_unit_aliases:
            rest = rest[match.end():]
            break
    rest = re.sub(r"^of\s+", "", rest)
    return unit, rest


def parse_line(raw: str, lexicon: Lexicon) -> ParsedIngredient | None:
    """Parse one line; returns None for lines that are empty after clean-up."""
    text = clean_line(raw)
    if not text:
        return None
    result = ParsedIngredient(raw=raw, text=text)
    work = fold(text)
    if any(p.search(work) for p in lexicon.header_res):
        result.is_header = True
        return result

    result.optional = "optional" in work
    # A label before a colon ("Suggested garnishes: sliced almonds") is not the ingredient.
    label = re.match(r"^([a-z][a-z \-]{0,30}):\s+(?=\S)", work)
    if label and not re.search(r"\d", label.group(1)):
        work = work[label.end():]

    # Package size in brackets: "2 (14.5 ounce) cans".
    size: tuple[float, str] | None = None
    for inner in _PAREN.findall(work):
        q, _, rest = take_quantity(inner.strip())
        unit, _ = take_unit(rest, lexicon)
        if q is not None and unit and lexicon.units_by_key(unit).dimension != "count":
            size = (q, unit)
            break
    work = re.sub(r"\s+", " ", _PAREN.sub(" ", work)).strip()

    q1, q2, work = take_quantity(work)
    work = _skip_size_words(work, lexicon)
    # "1 15-ounce can tomatoes": a second number is the package size.
    if q1 is not None and size is None:
        size_q, _, after = take_quantity(work)
        size_unit, after_unit = take_unit(after.lstrip("-"), lexicon)
        is_measure = size_unit and lexicon.units_by_key(size_unit).dimension != "count"
        if size_q is not None and is_measure:
            size, work = (size_q, size_unit), after_unit
    unit, work = take_unit(work, lexicon)
    result.quantity, result.quantity_max, result.unit = q1, q2, unit
    _set_amount(result, size, lexicon)
    # "3 cloves": the unit word is the ingredient.
    if unit and not work.strip(" ,"):
        work = unit

    # The name is the first comma-separated part that still has a name after clean-up
    # ("skinless, boneless chicken breasts" → "boneless chicken breasts").
    parts = [p.strip() for p in work.split(",") if p.strip()]
    name_index = 0
    for i, part in enumerate(parts):
        if lexicon.canonicalize(_cut(part, lexicon)).canonical:
            name_index = i
            break
    name = _cut(parts[name_index], lexicon) if parts else ""
    result.prep = ", ".join(p for i, p in enumerate(parts) if i != name_index)

    primary, alternatives = _split_alternatives(name, lexicon)
    result.name = primary
    canon = lexicon.canonicalize(primary)
    result.canonical, result.extra, result.form = canon.canonical, canon.extra, canon.form
    if unit == "can" and result.form is None:
        result.form = "canned"
    result.base = lexicon.base_of(result.canonical)
    alts: list[str] = []
    for alt in alternatives:
        alt_canonical = lexicon.canonicalize(alt).canonical
        if alt_canonical and alt_canonical != result.canonical and alt_canonical not in alts:
            alts.append(alt_canonical)
    result.alternatives = tuple(alts)
    return result


_SIZE_WORDS = {
    "small", "medium", "large", "extra-large", "big", "heaping", "heaped", "level", "scant",
    "generous", "rounded", "good", "thin", "thick", "whole",
}


def _skip_size_words(text: str, lexicon: Lexicon) -> str:
    """ "small clove garlic" → "clove garlic", so the unit can be found."""
    words = text.split(" ")
    i = 0
    while i < len(words) and words[i] in _SIZE_WORDS:
        i += 1
    rest = " ".join(words[i:])
    return rest if i and lexicon.unit_re.match(rest) else text


def _cut(name: str, lexicon: Lexicon) -> str:
    if lexicon.cut_re:
        name = lexicon.cut_re.split(name, maxsplit=1)[0]
    return name.strip(" -")


def _split_alternatives(name: str, lexicon: Lexicon) -> tuple[str, list[str]]:
    """ "chicken or vegetable stock" → ("chicken stock", ["vegetable stock"])."""
    parts = [p.strip() for p in _ALTERNATIVE.split(name) if p.strip()]
    if len(parts) <= 1:
        return name, []
    primary, alternatives = parts[0], []
    for alt in parts[1:]:
        q, _, rest = take_quantity(alt)
        _, rest = take_unit(rest, lexicon)
        alternatives.append(rest)
        # A one-word primary borrows the noun of a short alternative with no quantity:
        # "white or black pepper" → "white pepper".
        # Also covers a primary that is only a descriptor: "fresh or frozen berries".
        alt_words = rest.split()
        primary_words = lexicon.canonicalize(primary).canonical.split()
        shares_head = bool(primary_words) and alt_words and alt_words[-1] == primary.split()[-1]
        if q is None and len(primary_words) <= 1 and 1 < len(alt_words) <= 4 and not shares_head:
            primary = " ".join([primary, *alt_words[1:]])
    return primary, alternatives


def _set_amount(result: ParsedIngredient, size: tuple[float, str] | None, lexicon: Lexicon) -> None:
    qty = result.quantity
    if result.unit:
        unit = lexicon.units_by_key(result.unit)
        if unit.dimension != "count" and qty is not None:
            result.dimension, result.amount_base = unit.dimension, qty * unit.factor
            return
        if size is not None:
            size_unit = lexicon.units_by_key(size[1])
            result.dimension = size_unit.dimension
            result.amount_base = (qty if qty is not None else 1.0) * size[0] * size_unit.factor
            return
        result.dimension = "count"
        result.amount_base = qty
        return
    if qty is not None:
        result.dimension, result.amount_base = "count", qty
