"""Milestone 3 'done when': the companion recalls the default tradition and a theme from an
earlier session. Runs end to end through the API, the job handler and the graph."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.adapters.llm import MEMORY_ECHO
from app.auth import current_user_id
from app.config import Settings, get_settings
from app.jobs import InMemoryJobQueue
from app.main import create_app
from app.worker import process_one


@pytest.fixture
def api(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[current_user_id] = lambda: "user-a"
    with TestClient(app) as c:
        yield c


def reply(c: TestClient, thread_id: str, text: str) -> str:
    body = c.post(f"/threads/{thread_id}/messages", json={"text": text}).text
    return "".join(
        line.split('"text": "', 1)[1].rsplit('"', 1)[0]
        for line in body.splitlines()
        if line.startswith("data:") and '"text"' in line
    )


def test_recall_across_sessions(api: TestClient) -> None:
    rt = api.app.state.runtime  # type: ignore[attr-defined]
    api.put("/profile", json={"default_tradition": "raja-yoga"})

    # Session 1: talk about work.
    t1 = api.post("/threads").json()["id"]
    reply(api, t1, "My boss moved the deadline again.")
    jobs: InMemoryJobQueue = rt.jobs
    assert [j.kind for j in jobs.queued] == ["summarize"]
    assert jobs.queued[0].payload == {"user_id": "user-a", "thread_id": t1}  # ids only

    # The worker runs the summary.
    job = api.portal.call(process_one, rt)  # type: ignore[union-attr]
    assert job is not None and jobs.done == [job] and not jobs.failed

    # Session 2: a new thread. The companion's prompt carries the memory.
    t2 = api.post("/threads").json()["id"]
    text = reply(api, t2, "Hi again.")
    assert MEMORY_ECHO.format("work stress") in text


def test_summarize_is_debounced_per_thread(api: TestClient) -> None:
    rt = api.app.state.runtime  # type: ignore[attr-defined]
    t1 = api.post("/threads").json()["id"]
    reply(api, t1, "one")
    reply(api, t1, "two")
    assert len(rt.jobs.queued) == 1
