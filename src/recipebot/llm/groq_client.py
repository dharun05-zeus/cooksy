"""Groq client (free tier, fast hosted open models) returning schema-validated objects.

Groq's API is OpenAI-compatible, so this is a plain HTTP call with httpx. JSON mode makes
the model return a JSON object; the schema is given in the prompt and the result is
validated with Pydantic, which works for every model Groq hosts.
"""

from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from recipebot.llm.base import LLMUnavailable, inline_schema

T = TypeVar("T", bound=BaseModel)
API_URL = "https://api.groq.com/openai/v1/chat/completions"
RETRYABLE_CODES = {429, 500, 502, 503, 504}
# Errors that will not fix themselves during a chat: bad key, no access, unknown model.
PERMANENT_CODES = {401, 403, 404}


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in RETRYABLE_CODES


# Short waits: in a live chat it is better to fall back quickly than to stall.
_RETRY = dict(retry=retry_if_exception(_retryable), wait=wait_exponential(min=1, max=8),
              stop=stop_after_attempt(3), reraise=True)


class GroqClient:
    def __init__(self, api_key: str, model: str, timeout: float = 60.0):
        self.http = httpx.Client(timeout=timeout,
                                 headers={"Authorization": f"Bearer {api_key}"})
        self.model = model
        self.name = f"groq ({model})"

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        system += ("\nReply with one JSON object that follows this JSON schema:\n"
                   + json.dumps(inline_schema(schema)))
        content = self._call(system, prompt, temperature=0, max_tokens=700,
                             response_format={"type": "json_object"})
        return schema.model_validate_json(content)

    def generate_text(self, system: str, prompt: str, max_tokens: int = 160) -> str:
        return self._call(system, prompt, temperature=0.3, max_tokens=max_tokens)

    def _call(self, system: str, prompt: str, **options) -> str:
        try:
            return self._post(system, prompt, options)
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code in PERMANENT_CODES:
                raise LLMUnavailable(f"Groq error {code}: {exc.response.text[:200]}") from exc
            raise

    @retry(**_RETRY)
    def _post(self, system: str, prompt: str, options: dict) -> str:
        response = self.http.post(API_URL, json={
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            **options,
        })
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"] or ""
