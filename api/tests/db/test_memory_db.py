"""Memory store and the summarize job end to end on Postgres (make check-db)."""

import asyncio
import json

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.adapters.llm import MEMORY_ECHO
from app.auth import current_user_id
from app.config import Settings, get_settings
from app.main import create_app
from app.memory.store import recent_themes
from app.runtime import open_runtime
from app.worker import run

pytestmark = pytest.mark.db


def _client(settings: Settings, uid: str) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[current_user_id] = lambda: uid
    return TestClient(app)


def _reply(c: TestClient, thread_id: str, text: str) -> str:
    out = []
    body = c.post(f"/threads/{thread_id}/messages", json={"text": text}).text
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        if fields["event"] == "error":
            pytest.fail(fields["data"])
        if fields["event"] == "token":
            out.append(json.loads(fields["data"])["text"])
    return "".join(out)


async def _run_worker_until_idle(settings: Settings, user_id: str) -> None:
    """Run the real worker loop until this user's summarize job is done."""
    stop = asyncio.Event()
    task = asyncio.create_task(run(settings, stop))
    try:
        for _ in range(100):
            await asyncio.sleep(0.1)
            with psycopg.connect(settings.database_url) as conn:
                row = conn.execute(
                    "select status from public.jobs where payload->>'user_id' = %s"
                    " order by id desc limit 1",
                    (user_id,),
                ).fetchone()
            if row and row[0] in ("done", "failed"):
                assert row[0] == "done"
                return
        pytest.fail("worker did not finish the summarize job")
    finally:
        stop.set()
        await task


def test_recall_across_restart(db_settings: Settings, user_id: str) -> None:
    with _client(db_settings, user_id) as c:
        assert c.put("/profile", json={"default_tradition": "raja-yoga"}).status_code == 200
        t1 = c.post("/threads").json()["id"]
        _reply(c, t1, "Moving house next week and I can't sleep.")

    asyncio.run(_run_worker_until_idle(db_settings, user_id))

    async def themes() -> set[str]:
        async with open_runtime(db_settings) as rt:
            return {t.label for t in await recent_themes(rt.store, user_id)}

    assert {"moving home", "sleep"} <= asyncio.run(themes())

    # A fresh app (as after a restart) recalls it in a new conversation.
    with _client(db_settings, user_id) as c:
        t2 = c.post("/threads").json()["id"]
        text = _reply(c, t2, "Hello")
        assert c.get("/profile").json()["default_tradition"] == "raja-yoga"
    assert MEMORY_ECHO.format("moving home") in text or MEMORY_ECHO.format("sleep") in text


def test_store_tables_in_private_schema(db_settings: Settings) -> None:
    async def setup() -> None:
        async with open_runtime(db_settings):
            pass

    asyncio.run(setup())
    with psycopg.connect(db_settings.database_url) as conn:
        schemas = {
            r[0]
            for r in conn.execute(
                "select table_schema from information_schema.tables"
                " where table_name in ('store', 'store_vectors')"
            ).fetchall()
        }
    assert schemas == {"langgraph"}
