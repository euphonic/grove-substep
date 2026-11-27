import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapters.llm import CANNED_REPLIES
from app.auth import current_user_id
from app.config import Settings, get_settings
from app.main import create_app
from app.safety.resources import CRISIS_RESPONSE


class Users:
    current = "user-a"


@pytest.fixture
def api(settings: Settings) -> Iterator[tuple[TestClient, Users]]:
    users = Users()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[current_user_id] = lambda: users.current
    with TestClient(app) as c:
        yield c, users


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def send(c: TestClient, thread_id: str, text: str) -> list[tuple[str, dict[str, Any]]]:
    resp = c.post(f"/threads/{thread_id}/messages", json={"text": text})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    return parse_sse(resp.text)


def test_stream_and_history(api: tuple[TestClient, Users]) -> None:
    c, _ = api
    thread = c.post("/threads").json()
    events = send(c, thread["id"], "Had a calm morning")
    assert events[0][0] == "start" and events[-1] == ("end", {"crisis": False})
    tokens = [d["text"] for e, d in events if e == "token"]
    assert len(tokens) > 1, "reply should arrive as several tokens"
    assert "".join(tokens) in CANNED_REPLIES

    history = c.get(f"/threads/{thread['id']}/messages").json()["messages"]
    assert history == [
        {"role": "user", "content": "Had a calm morning"},
        {"role": "assistant", "content": "".join(tokens)},
    ]


def test_crisis_turn(api: tuple[TestClient, Users], settings: Settings) -> None:
    c, _ = api
    thread = c.post("/threads").json()
    events = send(c, thread["id"], "I want to die")
    assert "".join(d["text"] for e, d in events if e == "token") == CRISIS_RESPONSE
    assert events[-1] == ("end", {"crisis": True})
    assert "safety_flagged" not in c.get("/threads").json()[0]


def test_threads_are_private(api: tuple[TestClient, Users]) -> None:
    c, users = api
    thread = c.post("/threads").json()
    send(c, thread["id"], "hello")
    users.current = "user-b"
    assert c.get(f"/threads/{thread['id']}/messages").status_code == 404
    assert c.post(f"/threads/{thread['id']}/messages", json={"text": "hi"}).status_code == 404
    assert c.get("/threads").json() == []


def test_unknown_thread_404(api: tuple[TestClient, Users]) -> None:
    c, _ = api
    resp = c.get("/threads/00000000-0000-0000-0000-000000000000/messages")
    assert resp.status_code == 404


def test_message_validation(api: tuple[TestClient, Users]) -> None:
    c, _ = api
    thread = c.post("/threads").json()
    assert c.post(f"/threads/{thread['id']}/messages", json={"text": ""}).status_code == 422
    big = "x" * 8001
    assert c.post(f"/threads/{thread['id']}/messages", json={"text": big}).status_code == 422


def test_threads_require_auth(client: TestClient) -> None:
    assert client.post("/threads").status_code == 401
    assert client.get("/threads").status_code == 401
