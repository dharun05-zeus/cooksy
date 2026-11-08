"""Wire the pieces together; shared by the CLI and the web UI."""

from __future__ import annotations

from dataclasses import dataclass

from recipebot.config import Settings, get_settings
from recipebot.dialogue.orchestrator import Orchestrator
from recipebot.engines.search import SearchIndex
from recipebot.engines.store import RecipeStore
from recipebot.llm.base import LLMClient
from recipebot.llm.parser import MessageParser


def make_llm(settings: Settings, provider: str | None = None) -> tuple[LLMClient | None, str]:
    """Pick the LLM: a local Ollama model if it is running, else Groq or Gemini if a key is
    set, else none (the assistant still works, with the offline fallback parser).
    Returns the client and a one-line description for the user."""
    provider = (provider or settings.llm_provider).lower()
    notes = []
    if provider in ("auto", "ollama"):
        from recipebot.llm.ollama_client import OllamaClient

        installed = OllamaClient.installed_models(settings.ollama_host)
        if installed is None:
            notes.append("Ollama is not running")
        elif settings.ollama_model not in installed:
            notes.append(f"Ollama is running but '{settings.ollama_model}' is not installed "
                         f"(run: ollama pull {settings.ollama_model})")
        else:
            client = OllamaClient(settings.ollama_model, settings.ollama_host)
            return client, f"{client.name}, local"
    if provider in ("auto", "groq"):
        if settings.groq_api_key:
            from recipebot.llm.groq_client import GroqClient

            client = GroqClient(settings.groq_api_key, settings.groq_model)
            return client, client.name
        notes.append("no GROQ_API_KEY in .env")
    if provider in ("auto", "gemini"):
        if settings.gemini_api_key:
            from recipebot.llm.gemini import GeminiClient

            client = GeminiClient(settings.gemini_api_key, settings.gemini_model)
            return client, client.name
        notes.append("no GEMINI_API_KEY in .env")
    reason = "; ".join(notes) or f"LLM_PROVIDER={provider}"
    return None, f"no LLM ({reason}); using the offline fallback parser"


@dataclass
class Components:
    """Everything that is loaded once and shared by all conversations."""

    store: RecipeStore
    index: SearchIndex
    llm: LLMClient | None
    summaries: bool
    description: str

    def new_conversation(self) -> Orchestrator:
        return Orchestrator(self.store, self.index, MessageParser(self.llm), self.llm,
                            self.summaries)


def load_components(provider: str | None = None) -> Components:
    settings = get_settings()
    if not (settings.processed_dir / "recipes.parquet").exists():
        raise SystemExit("Processed data not found. Run:\n"
                         "  uv run python scripts/download_data.py\n"
                         "  uv run python scripts/build_index.py")
    store = RecipeStore.load(settings.processed_dir, settings.config_dir)
    index = SearchIndex.load_or_build(store, settings.processed_dir / "bm25")
    llm, description = make_llm(settings, provider)
    local = llm is not None and llm.name.startswith("ollama")
    summaries = settings.summaries == "on" or (settings.summaries == "auto" and not local)
    if llm is not None:
        description += f"; LLM-written summaries {'on' if summaries else 'off'}"
    return Components(store, index, llm, summaries, description)


def build_orchestrator(provider: str | None = None) -> tuple[Orchestrator, str]:
    components = load_components(provider)
    return components.new_conversation(), components.description
