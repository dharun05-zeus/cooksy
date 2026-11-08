"""The web API on the 9-record fixture dataset, with the offline parser (no LLM)."""

import pytest
from fastapi.testclient import TestClient

from recipebot.app import Components
from recipebot.ui import server


@pytest.fixture
def client(monkeypatch, store, index):
    # The app's startup loads its components; give it the fixture data instead of the dataset.
    monkeypatch.setattr(server, "load_components",
                        lambda: Components(store, index, None, False, "no LLM (test)"))
    server.sessions.bots.clear()
    server._overview.cache_clear()
    with TestClient(server.app) as c:
        yield c


def test_page_and_status(client):
    assert "Recipe Intelligence" in client.get("/").text
    assert client.get("/api/status").json()["llm"] is None


def test_overview_uses_real_counts(client):
    o = client.get("/api/overview").json()
    assert o["complete"] == 7 and o["records"] == 9
    assert o["sources"]["Food Network"] == 3


def test_chat_returns_structured_search_and_keeps_state(client):
    first = client.post("/api/chat", json={"session_id": "s1", "message": "Find a penne pasta recipe."}).json()
    assert first["data"]["type"] == "search"
    assert {r["id"] for r in first["data"]["results"]} == {"epi:e1", "ar:a3"}
    second = client.post("/api/chat", json={"session_id": "s1", "message": "I cannot have dairy."}).json()
    assert [r["id"] for r in second["data"]["results"]] == ["epi:e1"]
    assert second["state"]["exclude"] == ["dairy"]


def test_sessions_are_separate(client):
    client.post("/api/chat", json={"session_id": "a", "message": "I cannot have dairy."})
    assert client.get("/api/state/b").json()["exclude"] == []


def test_action_runs_a_structured_request_without_parsing(client):
    patch = {"intent": "match", "pantry": [{"name": "eggs"}, {"name": "flour"}], "replace_pantry": True}
    turn = client.post("/api/action", json={"session_id": "s2", "label": "I have eggs, flour", "patch": patch}).json()
    assert turn["parser"] == "form"
    assert turn["data"]["type"] == "match" and turn["data"]["results"][0]["id"] == "fn:f3"


def test_invalid_action_is_rejected(client):
    bad = {"session_id": "s3", "label": "x", "patch": {"intent": "not-an-intent"}}
    assert client.post("/api/action", json=bad).status_code == 422


def test_recipe_detail_and_unknown_id(client):
    r = client.get("/api/recipe/fn:f1").json()
    assert r["ingredients"][0] == "For the dressing:" and r["steps_method"] == "sentence"
    assert client.get("/api/recipe/ar:nope").status_code == 404
