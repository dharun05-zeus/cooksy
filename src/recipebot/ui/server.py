"""Web UI: a small JSON API around the orchestrator, plus the single-page front end.

    uv run recipebot web            # http://localhost:8000

One conversation (and its constraints) per browser session id. Chat messages go through
the parser (LLM); the UI's buttons and forms send a structured StatePatch to /api/action,
which runs instantly and updates the same conversation state.
"""

from __future__ import annotations

import logging
import statistics as pystats
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from recipebot.app import Components, load_components
from recipebot.data.models import SOURCE_NAMES
from recipebot.dialogue.orchestrator import Orchestrator, Turn
from recipebot.dialogue.state import StatePatch
from recipebot.engines import stats
from recipebot.engines.stats import RecipeFilter
from recipebot.render import payloads

WEB_DIR = Path(__file__).parent / "web"
MAX_SESSIONS = 200


class ChatIn(BaseModel):
    session_id: str
    message: str


class ActionIn(BaseModel):
    session_id: str
    label: str  # what the user did, shown in the chat ("Vegetarian filter")
    patch: StatePatch


class SessionIn(BaseModel):
    session_id: str


class _Sessions:
    """Conversations by session id; each has a lock so one turn runs at a time."""

    def __init__(self) -> None:
        self.components: Components | None = None
        self.bots: dict[str, tuple[Orchestrator, threading.Lock]] = {}
        self.guard = threading.Lock()

    def get(self, session_id: str) -> tuple[Orchestrator, threading.Lock]:
        with self.guard:
            if session_id not in self.bots:
                if len(self.bots) >= MAX_SESSIONS:
                    self.bots.pop(next(iter(self.bots)))
                self.bots[session_id] = (self.components.new_conversation(), threading.Lock())
            return self.bots[session_id]


sessions = _Sessions()


@asynccontextmanager
async def lifespan(_: FastAPI):
    sessions.components = load_components()
    yield


app = FastAPI(title="Cooksy", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
log = logging.getLogger("recipebot.web")


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log the full error in the terminal and tell the page what happened."""
    log.exception("Error while handling %s", request.url.path)
    return JSONResponse(status_code=500, content={
        "detail": f"The server hit an error ({type(exc).__name__}: {str(exc)[:200]}). "
                  "Details are in the terminal running `recipebot web`."})


def _state(bot: Orchestrator) -> dict:
    s = bot.state
    return {
        "task": s.task, "query": s.query, "exclude": s.exclude, "max_steps": s.max_steps,
        "pantry": [p.name for p in s.pantry], "focus_recipe_id": s.focus_recipe_id,
        "constraints": s.constraints_text(),
    }


def _turn(bot: Orchestrator, turn: Turn) -> dict:
    return {
        "user": turn.user,
        "reply": turn.reply,
        "summary": turn.summary,
        "data": turn.data,
        "intent": turn.patch.intent,
        "parser": turn.parser,
        "seconds": turn.seconds,
        "corrections": turn.corrections,
        "grounding_removed": [{"sentence": s, "reason": r}
                              for s, r in (turn.grounding.removed if turn.grounding else [])],
        "llm_disabled": bot.parser.disabled_reason,
        "state": _state(bot),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/status")
def status() -> dict:
    c = sessions.components
    return {"llm": c.llm.name if c.llm else None, "description": c.description,
            "summaries": c.summaries}


@app.get("/api/overview")
def overview() -> dict:
    return _overview()


@lru_cache(maxsize=1)
def _overview() -> dict:
    """Real numbers for the home page, computed once from the dataset."""
    store = sessions.components.store
    report = store.build_report
    complete = store.recipes[store.complete]
    counts = complete["ingredient_count"].tolist()
    top = stats.top_ingredients(store, RecipeFilter(), k=10, exclude_staples=True)
    return {
        "records": report.get("total_records"),
        "complete": int(store.complete.sum()),
        "sources": {SOURCE_NAMES.get(name, name): int(n)
                    for name, n in complete["source"].value_counts().items()},
        "mean_ingredients": round(pystats.mean(counts), 2),
        "median_ingredients": pystats.median(counts),
        "median_steps": pystats.median(complete["steps"].tolist()),
        "substitution_pairs": report.get("substitution_pairs"),
        "top_ingredients": top.rows,
    }


@app.post("/api/chat")
def chat(body: ChatIn) -> dict:
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "empty message")
    bot, lock = sessions.get(body.session_id)
    with lock:
        return _turn(bot, bot.handle(message[:1000]))


@app.post("/api/action")
def action(body: ActionIn) -> dict:
    bot, lock = sessions.get(body.session_id)
    with lock:
        return _turn(bot, bot.run(body.label, body.patch))


@app.post("/api/reset")
def reset(body: SessionIn) -> dict:
    bot, lock = sessions.get(body.session_id)
    with lock:
        bot.reset()
        return {"state": _state(bot)}


@app.get("/api/state/{session_id}")
def state(session_id: str) -> dict:
    bot, _ = sessions.get(session_id)
    return _state(bot)


@app.get("/api/recipe/{recipe_id:path}")
def recipe(recipe_id: str) -> dict:
    detail = payloads.recipe(sessions.components.store, recipe_id)
    if detail is None:
        raise HTTPException(404, f"There is no recipe with ID {recipe_id} in the dataset.")
    return detail
