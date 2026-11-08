"""One conversation turn: parse → update state → run an engine → render → LLM summary."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from recipebot.dialogue.state import (
    SessionState,
    StatePatch,
    StatsRequest,
    SubstituteRequest,
    apply_patch,
    resolve_intent,
)
from recipebot.engines import stats
from recipebot.engines.matching import MatchRequest, match
from recipebot.engines.search import SearchIndex, search
from recipebot.engines.stats import RecipeFilter
from recipebot.engines.store import RecipeStore
from recipebot.engines.substitution import SubstitutionEngine
from recipebot.llm.base import LLMClient, LLMUnavailable
from recipebot.llm.parser import MessageParser
from recipebot.llm.writer import write_summary
from recipebot.render import templates
from recipebot.render.grounding import Grounder, GroundingReport

HELP = """I answer questions from the Recipe Box dataset (about 123,000 recipes). Try:
- "Find a penne pasta recipe", then "I cannot have dairy"
- "How many recipes contain both garlic and onion? What percentage is that?"
- "I have eggs, onions, tomatoes and rice. Suggest five recipes with at most six steps."
- "Take the first one and replace the eggs"
Commands: /state shows active constraints, /reset starts over, /quit exits."""

SUMMARIZED = {"search", "match", "stats", "substitute"}

# Attributes the dataset does not record. Questions about them get a fixed, honest answer
# instead of whatever the parser decided, so nothing is ever estimated silently.
UNSUPPORTED = {
    "nutrition (calories, fat, protein, carbohydrates)":
        r"\b(calories?|kcal|nutrition\w*|protein|carbs?|carbohydrates?|fat content|"
        r"sodium content|healthy|macros)\b",
    "cooking or preparation times": r"\b(how long|cook(?:ing)? time|prep(?:aration)? time|"
                                    r"minutes|hours)\b",
    "servings or yield": r"\b(servings?|serves|how many people|portions?|yield)\b",
    "ratings, reviews or prices": r"\b(ratings?|reviews?|stars|price|cost)\b",
}
_QUESTION = re.compile(r"\?|^(how|what|which|is|are|does|do|can)\b", re.I)


@dataclass
class Turn:
    user: str
    reply: str
    patch: StatePatch
    parser: str  # which parser produced the patch
    corrections: list[str] = field(default_factory=list)  # guard fixes to the LLM's patch
    grounding: GroundingReport | None = None  # sentences removed from the LLM summary
    seconds: float = 0.0


class Orchestrator:
    def __init__(self, store: RecipeStore, index: SearchIndex, parser: MessageParser,
                 llm: LLMClient | None = None, summaries: bool = True):
        self.store = store
        self.index = index
        self.parser = parser
        self.llm = llm
        self.summaries = summaries
        self.state = SessionState()
        self.history: list[tuple[str, str]] = []
        self.substitution = SubstitutionEngine(store, index, store.lexicon.config_dir)
        common = {name for name, rows in store.by_base.items() if len(rows) >= 50}
        self.grounder = Grounder(common)

    def reset(self) -> None:
        self.state = SessionState()
        self.history = []

    @property
    def active_llm(self) -> LLMClient | None:
        return None if self.parser.disabled_reason else self.llm

    def handle(self, text: str) -> Turn:
        started = time.perf_counter()
        patch = resolve_intent(self.state, self.parser.parse(text, self.state, self.history))
        unknown_id = None
        if patch.recipe_id and self.store.get(patch.recipe_id) is None:
            unknown_id = patch.recipe_id
        missing = self._unsupported(text, patch)
        if unknown_id:  # e.g. an ID the LLM made up: say so, never fall back to another recipe
            patch = patch.model_copy(update={"recipe_id": None})
            facts, allowed_ids = f"There is no recipe with ID {unknown_id} in the dataset.", set()
        elif missing:
            self.state = apply_patch(self.state, patch)
            facts, allowed_ids = missing, set()
        else:
            self.state = apply_patch(self.state, patch)
            facts, allowed_ids = self._route(patch)
        reply, grounding = facts, None
        if self.summaries and self.active_llm and patch.intent in SUMMARIZED:
            summary, grounding = self._summary(text, facts, allowed_ids)
            if summary:
                reply = f"{summary}\n\n{facts}"
        self.history += [("user", text), ("assistant", reply.split("\n", 1)[0])]
        return Turn(text, reply, patch, self.parser.last_source, self.parser.last_corrections,
                    grounding, round(time.perf_counter() - started, 1))

    def _unsupported(self, text: str, patch: StatePatch) -> str | None:
        """A question about something the dataset does not record (calories, cooking time)."""
        if patch.intent in ("search", "match", "substitute", "reset") \
                or not _QUESTION.search(text.strip()):
            return None
        for attribute, pattern in UNSUPPORTED.items():
            if re.search(pattern, text, re.I):
                return (f"The dataset does not record {attribute}, so I cannot answer that "
                        "without guessing. Each recipe has only a title, an ingredient list and "
                        "instructions; I can show those, or answer questions about them.")
        return None

    def _summary(self, text: str, facts: str, ids: set[str]) -> tuple[str, GroundingReport | None]:
        try:
            draft = write_summary(self.active_llm, text, facts)
        except LLMUnavailable as exc:
            self.parser.disabled_reason = str(exc)
            return "", None
        except Exception:  # a failed summary never blocks the factual answer
            return "", None
        return self.grounder.check(draft, facts, ids)

    def _route(self, patch: StatePatch) -> tuple[str, set[str]]:
        s = self.state
        if patch.intent == "reset":
            return "Started a new session. All constraints were cleared.", set()
        if patch.intent == "help":
            return HELP, set()
        if patch.intent == "clarify":
            return patch.message or HELP, set()
        if patch.intent == "detail":
            return self._detail(patch), {s.focus_recipe_id} if s.focus_recipe_id else set()
        if patch.intent == "substitute":
            return self._substitute(patch)
        if patch.intent == "stats":
            return self._stats(patch.stats or s.last_stats)
        if patch.intent == "match":
            return self._match()
        return self._search()

    def _search(self) -> tuple[str, set[str]]:
        s = self.state
        if not s.query and not s.include:
            return "What dish or ingredient should I search for?", set()
        f = RecipeFilter(include_all=s.include, exclude=s.exclude, max_steps=s.max_steps)
        result = search(self.store, self.index, s.query, f, k=s.limit)
        self._remember([h.recipe_id for h in result.hits], [h.title for h in result.hits])
        text = templates.render_search(result, self.store, s.constraints_text())
        return text, set(s.last_results)

    def _match(self) -> tuple[str, set[str]]:
        s = self.state
        if not s.pantry:
            return "Which ingredients do you have?", set()
        request = MatchRequest(pantry=s.pantry, exclude=s.exclude, max_steps=s.max_steps,
                               preferences=s.preferences, limit=s.limit)
        result = match(self.store, request)
        shown = result.results or result.alternatives
        self._remember([m.recipe_id for m in shown], [m.title for m in shown])
        return templates.render_match(result, s.constraints_text()), set(s.last_results)

    def _detail(self, patch: StatePatch) -> str:
        s = self.state
        if patch.result_number and not patch.recipe_id and not (
                1 <= patch.result_number <= len(s.last_results)):
            return (f"There is no result number {patch.result_number}; the last list had "
                    f"{len(s.last_results)} recipes.")
        if not s.focus_recipe_id:
            return "Which recipe? Search first, then ask for it by its number."
        return templates.render_recipe(self.store, s.focus_recipe_id, patch.show)

    def _stats(self, request: StatsRequest | None) -> tuple[str, set[str]]:
        if request is None:
            return "Which statistic would you like?", set()
        f = RecipeFilter(include_all=request.include_all, include_any=request.include_any,
                         exclude=request.exclude, title_contains=request.title_contains,
                         match_mode=request.match_mode)
        op = request.operation
        if op == "count":
            result = stats.count(self.store, f)
        elif op == "percentage":
            result = stats.percentage(self.store, f)
        elif op == "top_ingredients":
            result = stats.top_ingredients(self.store, f, k=request.k,
                                           exclude_staples=request.exclude_staples)
        elif op == "ingredient_count_stats":
            result = stats.ingredient_count_stats(self.store, f)
        else:
            result = stats.rank_by_steps(self.store, f, k=request.k, order=request.order)
            self._remember([r["recipe_id"] for r in result.rows], [r["title"] for r in result.rows])
        ids = set(result.sample_ids) | {r["recipe_id"] for r in result.rows if "recipe_id" in r}
        return templates.render_stats(result, self.state.constraints_text()), ids

    def _substitute(self, patch: StatePatch) -> tuple[str, set[str]]:
        request = patch.substitute
        if request is None:
            return "What should I replace, and in which recipe?", set()
        recipe_id, how = self._recipe_to_adapt(patch, request)
        if recipe_id is None:
            return how, set()
        self.state.focus_recipe_id = recipe_id
        llm = self.active_llm
        result = self.substitution.adapt(recipe_id, request.target, self.state.exclude,
                                         request.replacement, llm)
        chosen_by = (f"the LLM ({llm.name}), from the evidenced candidates only, then checked "
                     "by code" if result.method == "llm"
                     else "the strongest evidence (rule-based rewrite)")
        text = templates.render_substitution(result, chosen_by)
        return (f"{how}\n{text}" if how else text), result.evidence_ids()

    def _recipe_to_adapt(self, patch: StatePatch,
                         request: SubstituteRequest) -> tuple[str | None, str]:
        s = self.state
        if patch.recipe_id:
            return patch.recipe_id, ""
        if patch.result_number:
            if 1 <= patch.result_number <= len(s.last_results):
                return s.last_results[patch.result_number - 1], ""
            return None, (f"There is no result number {patch.result_number}; the last list had "
                          f"{len(s.last_results)} recipes.")
        if request.recipe_query:
            focus = self.store.get(s.focus_recipe_id) if s.focus_recipe_id else None
            words = request.recipe_query.lower().split()
            if focus is not None and all(w in focus["title"].lower() for w in words):
                return s.focus_recipe_id, ""
            hits = search(self.store, self.index, request.recipe_query, RecipeFilter(), k=25).hits
            for hit in hits:
                if self.substitution.contains(hit.recipe_id, request.target):
                    return hit.recipe_id, (f"Using '{hit.title}' [{hit.recipe_id}], the top match "
                                           f"for '{request.recipe_query}' that contains "
                                           f"{request.target}.")
            return None, f"I found no '{request.recipe_query}' recipe containing {request.target}."
        if s.focus_recipe_id:
            return s.focus_recipe_id, ""
        return None, "Which recipe should I adapt? Search for it first or name the dish."

    def _remember(self, ids: list[str], titles: list[str]) -> None:
        self.state.last_results = ids
        self.state.last_result_titles = titles
