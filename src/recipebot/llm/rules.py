"""Keyword-based parser: the offline fallback when no LLM is available.

It covers the common phrasings used in the demo conversations and the tests. It is not a
general language parser; with an LLM configured it is only used if the LLM call fails.
"""

from __future__ import annotations

import re

from recipebot.dialogue.state import SessionState, StatePatch, StatsRequest, SubstituteRequest
from recipebot.engines.matching import PantryItem

NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "last": -1,
}
_NUM = r"(\d+|" + "|".join(NUMBERS) + r")"
_EXCLUDE = re.compile(
    r"\b(?:exclude|without|no|cannot have|can't have|cant have|can not have|avoid|allergic to|"
    r"don't eat|do not eat|free of|nothing with|hold the)\s+"
    r"([a-z ,\-]+?)(?:\s+too|\s+as well|\s+either|\s+please|[.?!]|$)"
)
_FREE = re.compile(r"\b([a-z]+)[- ]free\b")  # "gluten-free", "gluten free"
_DIETS = re.compile(r"\b(vegan|vegetarian|pescatarian)\b")
_INTOLERANT = re.compile(r"\b(lactose|gluten)[- ]intolerant\b")
_ALLOWED_AGAIN = re.compile(
    r"\b([a-z]+) is (?:fine|ok|okay|allowed)(?: now| again)?\b"
    r"|\bi can (?:have|eat) ([a-z]+) (?:now|again)\b")
_SPLIT = re.compile(r",\s*(?:and\s+)?|\s+and\s+|\s+or\s+")


def _number(token: str) -> int:
    return int(token) if token.isdigit() else NUMBERS.get(token, 0)


_CLAUSE_STARTS = {
    "at", "more", "fewer", "less", "prefer", "with", "than", "using", "suggest", "no",
    "without", "but", "what", "can", "give", "find", "show",
}


def _items(text: str) -> list[str]:
    return [i.strip(" .") for i in _SPLIT.split(text) if i.strip(" .")]


# "no idea", "no time": "no" followed by these words is not a restriction.
_NOT_FOOD = {"idea", "time", "clue", "problem", "matter", "way", "one", "longer", "need",
             "worries", "thanks", "preference", "restrictions", "allergies"}
_POLITE = re.compile(r"\s+(?:please|thanks|thank you)$")


def _clause_items(text: str) -> list[str]:
    """ "peanuts and at most six steps" → ["peanuts"]: stop at the next clause."""
    items = []
    for item in _items(text):
        item = _POLITE.sub("", item)
        if item.split()[0] in _CLAUSE_STARTS | _NOT_FOOD or len(item.split()) > 3:
            break
        items.append(item)
    return items


def restrictions_in(t: str) -> list[str]:
    """All restrictions stated in a (lower-cased) message, in any of the forms above."""
    found = [e for m in _EXCLUDE.finditer(t) for e in _clause_items(m.group(1))]
    found += [w for w in _FREE.findall(t) if w not in ("sugar", "fat", "stress", "hands")]
    found += _DIETS.findall(t)
    found += ["dairy" if w == "lactose" else w for w in _INTOLERANT.findall(t)]
    return list(dict.fromkeys(found))


def _pantry_item(text: str) -> PantryItem:
    """ "4 eggs" → quantity 4; "2 cups rice" → quantity 2, unit cups."""
    match = re.match(r"^(\d+(?:\.\d+)?)\s+(?:(cups?|grams?|g|kg|ounces?|oz|pounds?|lbs?|ml|"
                     r"liters?|tablespoons?|tbsp|teaspoons?|tsp)\s+(?:of\s+)?)?(.+)$", text)
    if not match:
        return PantryItem(name=text)
    return PantryItem(name=match.group(3), quantity=float(match.group(1)), unit=match.group(2))


class RuleParser:
    name = "rules"

    def parse(self, text: str, state: SessionState) -> StatePatch:
        t = text.lower().strip()
        if re.match(r"^(reset|start over|new session|clear)\b", t):
            return StatePatch(intent="reset")

        excludes = restrictions_in(t)
        allowed = [a or b for a, b in _ALLOWED_AGAIN.findall(t)]
        if allowed:
            return StatePatch(intent=state.task or "search", remove_exclude=allowed)
        steps = (re.search(r"(?:at most|max(?:imum)?|no more than|up to|under|fewer than|"
                           r"less than)\s+"
                           + _NUM + r"\s+(?:instruction\s+)?steps?", t)
                 or re.search(_NUM + r"\s+(?:instruction\s+)?steps?\s+or\s+(?:fewer|less)", t))
        max_steps = _number(steps.group(1)) if steps else None
        if steps and re.search(r"under|fewer than|less than", steps.group(0)):
            max_steps -= 1
        if max_steps is not None and max_steps < 1:
            max_steps = None
        count = re.search(_NUM + r"\s+recipes", t)
        limit = _number(count.group(1)) if count else None

        stats = self._stats(t)
        if stats:
            return StatePatch(intent="stats", stats=stats)

        swap = re.search(r"\b(?:remove|replace|substitute|swap|without using)\s+(?:the\s+)?"
                         r"([a-z ]+?)(?:\s+(?:in|from|with|for)\b|[.,?!]|$)", t)
        if swap and swap.group(1).strip() not in ("it", "this", "that"):
            dish = re.search(r"(?:this|the|a)\s+([a-z ]+?)\s+recipe", t)
            number = re.search(r"\bthe\s+" + _NUM + r"\s+one\b", t)
            position = _number(number.group(1)) if number else 0
            if position == -1:
                position = len(state.last_results)
            return StatePatch(
                intent="substitute", add_exclude=excludes,
                result_number=position if position >= 1 else None,
                substitute=SubstituteRequest(target=swap.group(1).strip(),
                                             recipe_query=dish.group(1) if dish else None))

        have = re.search(r"\bi (?:have|got|only have)\s+(.+?)(?:[.?!]|$)", t)
        if have:
            pantry = [_pantry_item(i) for i in _clause_items(have.group(1))]
            # "use as many as possible ... prefer fewest additional" is the default order;
            # only a bare "fewest additional" moves that key to the front.
            preferences = []
            if "as many" not in t and re.search(r"fewest (additional|extra)", t):
                preferences = ["fewest_extra"]
            elif re.search(r"fewest steps|quickest", t):
                preferences = ["fewest_steps"]
            return StatePatch(intent="match", pantry=pantry, replace_pantry=True,
                              add_exclude=excludes, max_steps=max_steps, limit=limit,
                              preferences=preferences)

        detail = re.search(r"(?:show|see|give|what are)\b.*?\b(?:the\s+)?" + _NUM
                           + r"(?:\s+one|\s+recipe)?\b", t)
        if detail and re.search(r"\b(one|ingredients|instructions|details)\b", t):
            number = _number(detail.group(1))
            if number == -1:
                number = len(state.last_results)
            show = [s for s in ("ingredients", "instructions") if s in t]
            return StatePatch(intent="detail", result_number=number if number >= 1 else None,
                              show=show)

        search = re.search(
            r"(?:find|search for|look for|looking for|show me|recipe for|recipes for|want)\s+"
            r"(?:an?\s+|some\s+)?(.+?)(?:\s+recipes?)?(?:[.?!]|$)", t)
        if search:
            # "find tacos, but nothing with pork" -> query "tacos" (the rest is a restriction)
            query = re.split(r",|\s+(?:but|without|with no|no|that|under|in under|at most)\s+",
                             search.group(1))[0]
            query = re.sub(r"\b(?:vegan|vegetarian|pescatarian|\w+[- ]free|some|easy|quick)\b",
                           " ", query)
            query = re.sub(r"\s+recipes?\b", " ", query).strip()
            if query:
                return StatePatch(intent="search", new_topic=True, query=query, limit=limit,
                                  max_steps=max_steps, add_exclude=excludes)

        if excludes or max_steps is not None:
            return StatePatch(intent=state.task or "search", add_exclude=excludes,
                              max_steps=max_steps, limit=limit)
        return StatePatch(intent="clarify", message=(
            "I can search recipes, answer statistics questions, or match recipes to "
            "ingredients you have. What would you like to do?"))

    def _stats(self, t: str) -> StatsRequest | None:
        contains = re.search(r"(?:contain(?:s|ing)?|use|uses|using|with)\s+(?:both\s+)?"
                             r"(.+?)(?:[?.,]|$)", t)
        ingredients = _items(contains.group(1)) if contains else []
        if "how many" in t or "percentage" in t or "what percent" in t:
            op = "percentage" if "percent" in t else "count"
            return StatsRequest(operation=op, include_all=ingredients)
        ranked = re.search(r"which\s+" + _NUM + r".*\b(fewest|most)\s+(?:instruction\s+)?steps", t)
        if ranked:
            return StatsRequest(operation="rank_by_steps", include_all=ingredients,
                                k=_number(ranked.group(1)) or 5, order=ranked.group(2))
        if "most common ingredient" in t:
            return StatsRequest(operation="top_ingredients", include_all=ingredients, k=10,
                                exclude_staples="staple" in t or "excluding salt" in t)
        if re.search(r"(average|mean|median) (number of )?ingredients", t):
            return StatsRequest(operation="ingredient_count_stats", include_all=ingredients)
        return None
