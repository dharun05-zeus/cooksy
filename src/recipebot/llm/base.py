"""What every LLM client provides, and helpers shared by the clients."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    """The LLM cannot be used for the rest of this session (bad key, no credits, server
    not running, model not installed). Retrying will not help, so callers stop trying."""


class LLMClient(Protocol):
    name: str  # shown to the user, e.g. "ollama (qwen3:4b)"

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        """Return an instance of `schema`; raise pydantic.ValidationError if the model's
        output does not fit, or LLMUnavailable for permanent failures."""
        ...

    def generate_text(self, system: str, prompt: str, max_tokens: int = 160) -> str: ...


def inline_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic's JSON schema with every $ref replaced by its definition, because not every
    provider resolves references in a response schema."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)
