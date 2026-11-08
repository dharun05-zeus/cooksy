"""Project paths and settings, read from environment variables and an optional .env file."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    config_dir: Path
    llm_provider: str = "auto"  # auto | ollama | groq | gemini | none
    ollama_model: str = "qwen3:4b"
    ollama_host: str | None = None  # default http://localhost:11434
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    # LLM-written opening for each reply: auto = on for API models, off for local models
    # (on a laptop CPU it adds ~30-50 s per turn); on | off force it.
    summaries: str = "auto"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


def get_settings() -> Settings:
    data_dir = Path(os.environ.get("RECIPEBOT_DATA_DIR", "data"))
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir
    config_dir = Path(os.environ.get("RECIPEBOT_CONFIG_DIR", PROJECT_ROOT / "config"))
    return Settings(
        data_dir=data_dir,
        config_dir=config_dir,
        llm_provider=os.environ.get("LLM_PROVIDER", "auto").lower(),
        ollama_model=os.environ.get("OLLAMA_MODEL", "qwen3:4b"),
        ollama_host=os.environ.get("OLLAMA_HOST") or None,
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        groq_model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
        summaries=os.environ.get("LLM_SUMMARIES", "auto").lower(),
    )


def use_utf8_console() -> None:
    """Windows consoles default to cp1252, which cannot print recipe text such as '½'."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
