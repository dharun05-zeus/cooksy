"""Gemini client (Google AI Studio) returning schema-validated objects."""

from __future__ import annotations

from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from recipebot.llm.base import LLMUnavailable, inline_schema

T = TypeVar("T", bound=BaseModel)
RETRYABLE_CODES = {429, 500, 502, 503, 504}
# Errors that will not fix themselves during a chat: bad key, no credits, unknown model.
PERMANENT_CODES = {400, 401, 402, 403, 404}


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, errors.APIError) and exc.code in RETRYABLE_CODES


# Short waits: in a live chat it is better to fall back quickly than to stall.
_RETRY = dict(retry=retry_if_exception(_retryable), wait=wait_exponential(min=1, max=8),
              stop=stop_after_attempt(3), reraise=True)


class GeminiClient:
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.name = f"gemini ({model})"

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=inline_schema(schema),
        )
        return schema.model_validate_json(self._call(prompt, config))

    def generate_text(self, system: str, prompt: str, max_tokens: int = 160) -> str:
        return self._call(prompt, types.GenerateContentConfig(
            system_instruction=system, max_output_tokens=max_tokens))

    def _call(self, prompt: str, config: types.GenerateContentConfig) -> str:
        try:
            return self._generate(prompt, config)
        except errors.APIError as exc:
            if exc.code in PERMANENT_CODES:
                message = getattr(exc, "message", None) or str(exc)
                raise LLMUnavailable(f"Gemini error {exc.code}: {message}") from exc
            raise

    @retry(**_RETRY)
    def _generate(self, prompt: str, config: types.GenerateContentConfig) -> str:
        response = self.client.models.generate_content(
            model=self.model, contents=prompt, config=config)
        return response.text or ""
