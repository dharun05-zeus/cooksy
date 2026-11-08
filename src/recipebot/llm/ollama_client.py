"""Local LLM through Ollama: free, no API key, no quota, works offline."""

from __future__ import annotations

from typing import TypeVar

import httpx
import ollama
from pydantic import BaseModel

from recipebot.llm.base import LLMUnavailable, inline_schema

T = TypeVar("T", bound=BaseModel)


class OllamaClient:
    def __init__(self, model: str, host: str | None = None, timeout: float = 180.0):
        self.client = ollama.Client(host=host, timeout=timeout)
        self.model = model
        self.name = f"ollama ({model})"

    @staticmethod
    def installed_models(host: str | None = None) -> list[str] | None:
        """Names of the installed models, or None if the Ollama server is not running."""
        try:
            response = ollama.Client(host=host, timeout=3).list()
        except (httpx.HTTPError, ConnectionError, ollama.ResponseError):
            return None
        return [m.model for m in response.models]

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        # num_predict caps the answer length, so a rambling response cannot stall a turn.
        content = self._chat(system, prompt, format=inline_schema(schema),
                             options={"temperature": 0, "num_predict": 700})
        return schema.model_validate_json(content)

    def generate_text(self, system: str, prompt: str, max_tokens: int = 160) -> str:
        return self._chat(system, prompt, format=None,
                          options={"temperature": 0.3, "num_predict": max_tokens})

    def _chat(self, system: str, prompt: str, format, options: dict) -> str:
        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompt}],
                format=format,
                think=False,  # Qwen3's step-by-step thinking is slow on a CPU and not needed here
                options={"num_ctx": 8192, **options},
                keep_alive="30m",  # keep the model loaded between turns
            )
        except ollama.ResponseError as exc:
            if exc.status_code == 404:
                raise LLMUnavailable(f"model '{self.model}' is not installed; run: "
                                     f"ollama pull {self.model}") from exc
            raise
        except (httpx.ConnectError, ConnectionError) as exc:
            raise LLMUnavailable("the Ollama server is not running") from exc
        return response.message.content or ""
