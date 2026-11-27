"""Job queue against local Supabase (make check-db)."""

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import psycopg
import pytest

from app.config import Settings
from app.jobs import MAX_ATTEMPTS, PostgresJobQueue
from app.runtime import Runtime, open_runtime

pytestmark = [pytest.mark.db, pytest.mark.anyio]


@pytest.fixture
async def rt(db_settings: Settings) -> AsyncIterator[Runtime]:
    async with open_runtime(db_settings) as runtime:
        yield runtime


def _q(rt: Runtime) -> PostgresJobQueue:
    assert isinstance(rt.jobs, PostgresJobQueue)
    return rt.jobs


async def test_enqueue_claim_complete(rt: Runtime) -> None:
    key = f"test:{uuid.uuid4()}"
    await _q(rt).enqueue("test", {"id": key}, dedupe_key=key)
    job = await _q(rt).claim()
    while job and job.payload.get("id") != key:  # skip jobs left by other tests
        await _q(rt).complete(job)
        job = await _q(rt).claim()
    assert job is not None and job.attempts == 1
    await _q(rt).complete(job)


async def test_debounce_pushes_run_after(rt: Runtime, db_settings: Settings) -> None:
    key = f"test:{uuid.uuid4()}"
    await _q(rt).enqueue("test", {"id": key}, dedupe_key=key, delay=timedelta(seconds=5))
    await _q(rt).enqueue("test", {"id": key}, dedupe_key=key, delay=timedelta(minutes=10))
    with psycopg.connect(db_settings.database_url) as conn:
        rows = conn.execute(
            "select run_after > now() + interval '5 minutes' from public.jobs"
            " where dedupe_key = %s",
            (key,),
        ).fetchall()
    assert rows == [(True,)], "one queued job, pushed later by the second enqueue"


async def test_failure_retries_then_gives_up(rt: Runtime, db_settings: Settings) -> None:
    key = f"test:{uuid.uuid4()}"
    await _q(rt).enqueue("test", {"id": key}, dedupe_key=key)
    with psycopg.connect(db_settings.database_url, autocommit=True) as conn:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            conn.execute("update public.jobs set run_after = now() where dedupe_key = %s", (key,))
            job = await _q(rt).claim()
            while job and job.payload.get("id") != key:
                await _q(rt).complete(job)
                job = await _q(rt).claim()
            assert job is not None and job.attempts == attempt
            await _q(rt).fail(job, "TimeoutError")
        row = conn.execute(
            "select status, attempts, last_error from public.jobs where dedupe_key = %s", (key,)
        ).fetchone()
    assert row == ("failed", MAX_ATTEMPTS, "TimeoutError")


def test_client_roles_cannot_see_jobs(db_settings: Settings) -> None:
    with psycopg.connect(db_settings.database_url) as conn:
        for role in ("anon", "authenticated"):
            ok = conn.execute(
                "select has_table_privilege(%s, 'public.jobs', 'SELECT')", (role,)
            ).fetchone()
            assert ok == (False,)
