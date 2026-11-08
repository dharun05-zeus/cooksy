"""Conversation state, and the StatePatch the parser produces for each user message.

The LLM never edits the state directly. It returns a StatePatch (a small, schema-validated
change), and `apply_patch` applies it with fixed rules:
- Exclusions and the step limit are hard constraints. They persist across topics until the
  user removes them or resets, so "I cannot have dairy" keeps applying.
- A new search topic replaces the query and required ingredients, not the constraints.
- References such as "the second one" are resolved by code from `last_results`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from recipebot.engines.matching import PantryItem, SortKey

Intent = Literal["search", "detail", "stats", "match", "substitute", "clarify", "reset", "help"]
StatsOperation = Literal[
    "count", "percentage", "top_ingredients", "ingredient_count_stats", "rank_by_steps"
]


class StatsRequest(BaseModel):
    operation: StatsOperation
    include_all: list[str] = Field(default=[], description="ingredients every recipe must contain")
    include_any: list[str] = Field(default=[], description="recipes must contain at least one")
    exclude: list[str] = Field(default=[], description="ingredients or categories to leave out")
    title_contains: list[str] = Field(default=[], description="words the title must contain")
    match_mode: Literal["strict", "broad"] = Field(
        default="strict",
        description="strict: the ingredient and its varieties; broad: also products "
                    "containing the name (garlic powder, green onion)")
    k: int = Field(default=5, ge=1, le=50, description="how many rows to return for rankings")
    order: Literal["fewest", "most"] = "fewest"
    exclude_staples: bool = Field(default=False, description="leave out salt, pepper, water")


class SubstituteRequest(BaseModel):
    target: str = Field(description="ingredient or category to replace or remove: 'eggs', "
                                    "'cream', 'dairy'")
    replacement: str | None = Field(
        default=None, description="a substitute the user explicitly asks for, if any")
    recipe_query: str | None = Field(
        default=None, description="dish name, if the user names a recipe that is not one of "
                                  "the last results ('this banana bread recipe')")


class StatePatch(BaseModel):
    intent: Intent
    new_topic: bool = Field(
        default=False, description="true when the user starts a different search, not a refinement")
    query: str | None = Field(default=None, description="dish or keywords to search for")
    add_include: list[str] = Field(default=[], description="ingredients results must contain")
    remove_include: list[str] = []
    add_exclude: list[str] = Field(
        default=[], description="ingredients or categories (dairy, egg, nuts, gluten, vegan...) "
                                "the user cannot or will not have")
    remove_exclude: list[str] = []
    max_steps: int | None = Field(default=None, ge=1, description="maximum instruction steps")
    clear_max_steps: bool = False
    pantry: list[PantryItem] = Field(default=[], description="ingredients the user says they have")
    replace_pantry: bool = Field(
        default=False, description="true when the user gives a new list instead of adding")
    remove_pantry: list[str] = []
    preferences: list[SortKey] = Field(
        default=[], description="ranking preferences, most important first")
    result_number: int | None = Field(
        default=None, ge=1,
        description="1-based position in the last results ('the second one' = 2)")
    recipe_id: str | None = None
    show: list[Literal["ingredients", "instructions"]] = []
    stats: StatsRequest | None = None
    substitute: SubstituteRequest | None = None
    limit: int | None = Field(default=None, description="how many results the user asked for")
    message: str | None = Field(
        default=None, description="for clarify: the question to ask the user")


class SessionState(BaseModel):
    task: Literal["search", "match"] | None = None  # the active search the constraints refine
    query: str = ""
    include: list[str] = []
    exclude: list[str] = []
    max_steps: int | None = None
    pantry: list[PantryItem] = []
    preferences: list[SortKey] = []
    limit: int = 5
    focus_recipe_id: str | None = None
    last_results: list[str] = []
    last_result_titles: list[str] = []
    last_stats: StatsRequest | None = None

    def constraints_text(self) -> str:
        parts = [f"no {term}" for term in self.exclude]
        if self.max_steps is not None:
            parts.append(f"at most {self.max_steps} steps")
        return ", ".join(parts)


def _add(items: list[str], new: list[str]) -> list[str]:
    result = list(items)
    for item in new:
        if item.lower() not in {r.lower() for r in result}:
            result.append(item)
    return result


def _remove(items: list[str], gone: list[str]) -> list[str]:
    gone_lower = {g.lower() for g in gone}
    return [i for i in items if i.lower() not in gone_lower]


def resolve_intent(state: SessionState, patch: StatePatch) -> StatePatch:
    """A bare restriction refines the active task: "exclude eggs too" while matching
    ingredients stays a match, even if the parser labelled it a search."""
    refines_match = (patch.intent == "search" and state.task == "match" and not patch.new_topic
                     and not patch.query and not patch.add_include)
    return patch.model_copy(update={"intent": "match"}) if refines_match else patch


def apply_patch(state: SessionState, patch: StatePatch) -> SessionState:
    if patch.intent == "reset":
        return SessionState()
    s = state.model_copy(deep=True)

    # Hard constraints: session-wide until removed.
    s.exclude = _remove(_add(s.exclude, patch.add_exclude), patch.remove_exclude)
    if patch.clear_max_steps:
        s.max_steps = None
    if patch.max_steps is not None:
        s.max_steps = patch.max_steps
    if patch.preferences:
        s.preferences = list(patch.preferences)
    if patch.limit:
        s.limit = max(1, min(patch.limit, 20))

    if patch.intent == "search":
        if patch.new_topic or s.task != "search":
            s.query = patch.query or ""
            s.include = list(patch.add_include)
        else:
            if patch.query:
                s.query = patch.query
            s.include = _add(s.include, patch.add_include)
        s.include = _remove(s.include, patch.remove_include)
        s.task = "search"
    elif patch.intent == "match":
        if patch.pantry and (patch.replace_pantry or s.task != "match"):
            s.pantry = list(patch.pantry)
        else:
            names = {p.name.lower() for p in s.pantry}
            s.pantry += [p for p in patch.pantry if p.name.lower() not in names]
        removed = {r.lower() for r in patch.remove_pantry}
        s.pantry = [p for p in s.pantry if p.name.lower() not in removed]
        s.task = "match"
    elif patch.intent in ("detail", "substitute"):
        if patch.recipe_id:
            s.focus_recipe_id = patch.recipe_id
        elif patch.result_number and 1 <= patch.result_number <= len(s.last_results):
            s.focus_recipe_id = s.last_results[patch.result_number - 1]
    elif patch.intent == "stats" and patch.stats is not None:
        s.last_stats = patch.stats
    return s
