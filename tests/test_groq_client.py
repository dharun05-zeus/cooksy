"""The Groq client against a fake Groq server (no network, no key needed)."""

import json

import httpx
import pytest
from tenacity import wait_none

from recipebot.app import make_llm
from recipebot.config import get_settings
from recipebot.dialogue.state import StatePatch
from recipebot.llm.base import LLMUnavailable
from recipebot.llm.groq_client import API_URL, GroqClient


def client_with(handler) -> GroqClient:
    client = GroqClient("test-key", "llama-3.3-70b-versatile")
    client.http = httpx.Client(transport=httpx.MockTransport(handler),
                               headers={"Authorization": "Bearer test-key"})
    return client


def reply(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})


def test_generate_json_sends_json_mode_and_validates_the_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return reply('{"intent": "search", "query": "penne", "new_topic": true}')

    patch = client_with(handler).generate_json("Parse the message.", "Find penne. JSON:",
                                               StatePatch)
    assert patch.intent == "search" and patch.query == "penne"
    body = seen["body"]
    assert seen["url"] == API_URL and seen["auth"] == "Bearer test-key"
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["response_format"] == {"type": "json_object"} and body["temperature"] == 0
    assert "JSON schema" in body["messages"][0]["content"]  # the schema is in the prompt


def test_bad_key_turns_the_llm_off_for_the_session():
    client = client_with(lambda request: httpx.Response(401, json={"error": "invalid key"}))
    with pytest.raises(LLMUnavailable, match="Groq error 401"):
        client.generate_text("system", "hello")


def test_rate_limit_is_retried(monkeypatch):
    monkeypatch.setattr(GroqClient._post.retry, "wait", wait_none())
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429) if len(calls) < 3 else reply("Hello!")

    assert client_with(handler).generate_text("system", "hello") == "Hello!"
    assert len(calls) == 3


def test_groq_is_chosen_when_its_key_is_set(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    llm, description = make_llm(get_settings(), "groq")
    assert isinstance(llm, GroqClient) and description == "groq (llama-3.3-70b-versatile)"
    monkeypatch.setenv("GROQ_API_KEY", "")
    llm, description = make_llm(get_settings(), "groq")
    assert llm is None and "no GROQ_API_KEY" in description
