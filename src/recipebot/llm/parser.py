"""Turn a user message into a StatePatch with an LLM.

Three layers, so one bad model response never breaks a turn:
1. The LLM produces the patch, constrained to the StatePatch JSON schema and validated.
2. Guards: high-precision patterns (e.g. "at most six steps", "no peanuts",
   "how many recipes contain A and B") fill in slots the LLM dropped. Small local models
   lose details in long requests; every correction is recorded in `last_corrections`.
3. If the LLM is unavailable or its output is invalid twice, the rule parser is used.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from recipebot.dialogue.state import SessionState, StatePatch
from recipebot.llm.base import LLMClient, LLMUnavailable
from recipebot.llm.rules import RuleParser

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You convert one message from a user of a recipe assistant into a JSON StatePatch.
You never answer the user and never invent recipes: the program searches a recipe dataset.

Intents:
- search: find recipes by dish name, ingredients or description. `query` = dish words.
  new_topic=true for a different search; omit it when refining the current one.
- detail: show one recipe from the last results ("the second one" -> result_number 2).
- stats: counts, percentages, most common ingredients, average/median ingredient counts,
  ranking recipes by number of instruction steps. Fill `stats` completely.
- match: the user lists ingredients they HAVE and wants recipes using them -> `pantry`.
- substitute: replace or remove an ingredient in a recipe -> `substitute`.
- clarify: ambiguous or not about recipes -> short question in `message`.
- reset: start over.

Rules:
- Restrictions go in add_exclude, using these words when they apply: dairy, egg, peanut,
  nuts, gluten, shellfish, fish, seafood, soy, meat, vegetarian, vegan; otherwise the
  ingredient name. "lactose intolerant" -> dairy. "vegetarian" -> vegetarian (not dairy).
- A restriction with no new request refines the active task: keep its intent.
- Only set what the user said. Do not invent limits ("quick" is not a step limit).
- "how many ... and what percentage" -> stats operation "percentage".

Examples (state is shown only when it matters):
"Find a penne pasta recipe." -> {"intent":"search","new_topic":true,"query":"penne pasta"}
[active task: search] "I cannot have dairy." -> {"intent":"search","add_exclude":["dairy"]}
[active task: search] "my kid is lactose intolerant and we hate cilantro" -> {"intent":"search","add_exclude":["dairy","cilantro"]}
"something vegetarian with chickpeas" -> {"intent":"search","new_topic":true,"query":"chickpeas","add_exclude":["vegetarian"]}
"Find a pasta recipe with heavy cream." -> {"intent":"search","new_topic":true,"query":"pasta heavy cream","add_include":["heavy cream"]}
"How many recipes contain both garlic and onion? What percentage is that?" -> {"intent":"stats","stats":{"operation":"percentage","include_all":["garlic","onion"]}}
"Among recipes containing tomato, which five have the fewest instruction steps?" -> {"intent":"stats","stats":{"operation":"rank_by_steps","include_all":["tomato"],"k":5,"order":"fewest"}}
"What are the 10 most common ingredients in vegan recipes?" -> {"intent":"stats","stats":{"operation":"top_ingredients","exclude":["vegan"],"k":10}}
"Average number of ingredients in cookie recipes?" -> {"intent":"stats","stats":{"operation":"ingredient_count_stats","title_contains":["cookie"]}}
"I have eggs, onions and rice. Suggest 3 recipes with no peanuts and at most six steps." -> {"intent":"match","pantry":[{"name":"eggs"},{"name":"onions"},{"name":"rice"}],"replace_pantry":true,"add_exclude":["peanut"],"max_steps":6,"limit":3}
[active task: match] "Exclude eggs too." -> {"intent":"match","add_exclude":["egg"]}
"show me the second one" -> {"intent":"detail","result_number":2}
"Take this banana bread recipe and remove eggs." -> {"intent":"substitute","substitute":{"target":"eggs","recipe_query":"banana bread"}}
[last results shown] "Replace the cream in the first one without dairy" -> {"intent":"substitute","result_number":1,"substitute":{"target":"cream"},"add_exclude":["dairy"]}
"what's the weather?" -> {"intent":"clarify","message":"I can only help with recipes from the dataset. What would you like to cook?"}
"""


def build_prompt(text: str, state: SessionState, history: list[tuple[str, str]]) -> str:
    context = {
        "active_task": state.task,
        "active_search_query": state.query or None,
        "excluded": state.exclude,
        "max_steps": state.max_steps,
        "pantry": [p.name for p in state.pantry],
        "last_results": [f"{i + 1}. {t}" for i, t in enumerate(state.last_result_titles)],
        "selected_recipe": state.focus_recipe_id,
        "last_stats_request": state.last_stats.model_dump(exclude_defaults=True)
        if state.last_stats else None,
    }
    context = {k: v for k, v in context.items() if v}
    recent = [f"{role}: {msg[:200]}" for role, msg in history[-4:]]
    return (
        "State: " + json.dumps(context) +
        ("\nRecent turns:\n" + "\n".join(recent) if recent else "") +
        f"\nUser message: {text}\nJSON:"
    )


def _same(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    return a == b or a.rstrip("s") == b.rstrip("s")


_NEGATION = re.compile(
    r"\b(no|not|without|free|cannot|can't|cant|allergic|allergy|avoid|exclude|excluding|"
    r"intolerant|hate|don't|dont|never|except|skip|remove|replace|vegan|vegetarian|"
    r"pescatarian|nothing|none|hold)\b|-free\b", re.I)
_SEARCH_STOP = {
    "i", "can", "make", "in", "under", "steps", "step", "find", "me", "some", "recipes",
    "recipe", "with", "a", "an", "the", "that", "which", "what", "for", "to", "less", "than",
    "fewer", "at", "most", "or", "and", "quick", "easy",
}


def apply_guards(llm: StatePatch, rules: StatePatch, text: str = "",
                 state: SessionState | None = None) -> tuple[StatePatch, list[str]]:
    """Fill slots the LLM dropped, using the rule parser's high-precision matches, and drop
    exclusions the message gives no reason for ("pasta WITH heavy cream" is not "no dairy")."""
    fixed = llm.model_copy(deep=True)
    notes: list[str] = []
    if fixed.add_exclude and text and not _NEGATION.search(text):
        notes.append(f"add_exclude {fixed.add_exclude} removed (no restriction in the message)")
        fixed.add_exclude = []
    # "soups I can make in under 5 steps": a match request needs ingredients; without any,
    # it is a search.
    if fixed.intent == "match" and not fixed.pantry and not (state and state.pantry):
        words = [w for w in re.findall(r"[a-z]+", text.lower())
                 if w not in _SEARCH_STOP and not w.isdigit()]
        query = fixed.query or rules.query or " ".join(words)
        notes.append(f"intent match -> search '{query}' (no ingredients given)")
        fixed.intent, fixed.new_topic, fixed.query = "search", True, query
    # "Exclude eggs too" while matching ingredients refines the match, not a new search.
    if (state and state.task == "match" and fixed.intent == "search" and rules.intent == "match"
            and not rules.query and not rules.pantry):
        notes.append("intent search -> match (refines the active ingredient match)")
        fixed.intent, fixed.new_topic, fixed.query = "match", False, None
    if rules.remove_exclude and not fixed.remove_exclude:
        notes.append(f"remove_exclude <- {rules.remove_exclude}")
        fixed.remove_exclude = rules.remove_exclude
    if rules.intent == "stats" and rules.stats and llm.intent != "stats":
        notes.append(f"intent {llm.intent} -> stats")
        fixed.intent, fixed.stats = "stats", rules.stats
    elif rules.intent == "stats" and rules.stats and fixed.stats:
        if rules.stats.operation == "rank_by_steps" and fixed.stats.operation != "rank_by_steps":
            notes.append(f"stats operation {fixed.stats.operation} -> rank_by_steps")
            fixed.stats = rules.stats
        # "how many recipes use X" is a count, not an average number of ingredients
        counting = ("count", "percentage")
        if rules.stats.operation in counting and fixed.stats.operation not in counting:
            notes.append(f"stats operation {fixed.stats.operation} -> {rules.stats.operation}")
            fixed.stats.operation = rules.stats.operation
        if rules.stats.include_all and not fixed.stats.include_all:
            notes.append(f"stats include_all <- {rules.stats.include_all}")
            fixed.stats.include_all = rules.stats.include_all
    if rules.intent == "match" and fixed.intent != "match" and rules.pantry:
        notes.append(f"intent {fixed.intent} -> match")
        fixed.intent, fixed.pantry, fixed.replace_pantry = "match", rules.pantry, True
    if fixed.intent in ("search", "match", "substitute"):
        missing = [e for e in rules.add_exclude
                   if not any(_same(e, x) for x in fixed.add_exclude)]
        if missing:
            notes.append(f"add_exclude += {missing}")
            fixed.add_exclude += missing
        if rules.max_steps is not None and fixed.max_steps != rules.max_steps:
            notes.append(f"max_steps {fixed.max_steps} -> {rules.max_steps}")
            fixed.max_steps = rules.max_steps
        if fixed.max_steps is not None and rules.max_steps is None:
            notes.append(f"max_steps {fixed.max_steps} removed (not stated)")
            fixed.max_steps = None
        if rules.limit and not fixed.limit:
            fixed.limit = rules.limit
    return fixed, notes


class MessageParser:
    def __init__(self, client: LLMClient | None):
        self.client = client
        self.rules = RuleParser()
        self.last_source = "rules"
        self.last_error: str | None = None
        self.last_corrections: list[str] = []
        # Set when the LLM fails in a way retrying will not fix (bad key, no credits,
        # server down); the rest of the session then uses the rule parser without waiting.
        self.disabled_reason: str | None = None

    @property
    def name(self) -> str:
        return self.client.name if self.client else "rules"

    def parse(self, text: str, state: SessionState,
              history: list[tuple[str, str]] | None = None) -> StatePatch:
        self.last_error = None
        self.last_corrections = []
        rule_patch = self.rules.parse(text, state)
        if self.client is not None and self.disabled_reason is None:
            prompt = build_prompt(text, state, history or [])
            for _ in range(2):  # one retry on an invalid response
                try:
                    patch = self.client.generate_json(SYSTEM_PROMPT, prompt, StatePatch)
                    patch, self.last_corrections = apply_guards(patch, rule_patch, text, state)
                    self.last_source = self.client.name
                    return patch
                except ValidationError as exc:
                    self.last_error = f"invalid response: {exc.error_count()} errors"
                except LLMUnavailable as exc:
                    self.last_error = self.disabled_reason = str(exc)[:300]
                    break
                except Exception as exc:  # timeout, rate limit, safety block: this turn only
                    self.last_error = f"{type(exc).__name__}: {exc}"[:300]
                    break
            log.warning("LLM parse failed (%s); using rule parser", self.last_error)
        self.last_source = "rules"
        return rule_patch
