"""Background job queue backed by public.jobs (Postgres) or memory (tests).

Payloads must contain ids only. Never put message, journal or theme text in a job.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Protocol

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

MAX_ATTEMPTS = 3
STALE_AFTER = timedelta(minutes=10)


@dataclass(frozen=True)
class Job:
    id: int
    kind: str
    payload: dict[str, Any]
    attempts: int


class JobQueue(Protocol):
    async def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        delay: timedelta = timedelta(0),
        dedupe_key: str | None = None,
    ) -> None: ...
    async def claim(self) -> Job | None: ...
    async def complete(self, job: Job) -> None: ...
    async def fail(self, job: Job, error_type: str) -> None: ...


def _check_payload(payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        if not isinstance(value, (str, int, uuid.UUID)) or len(str(value)) > 64:
            raise ValueError(f"job payload field '{key}' must be a short id, not content")


class PostgresJobQueue:
    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    async def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        delay: timedelta = timedelta(0),
        dedupe_key: str | None = None,
    ) -> None:
        _check_payload(payload)
        async with self._pool.connection() as conn:
            # Debounce: a newer enqueue for the same key pushes the queued job later.
            await conn.execute(
                """insert into public.jobs (kind, payload, dedupe_key, run_after)
                   values (%s, %s, %s, now() + %s)
                   on conflict (dedupe_key) where status = 'queued' and dedupe_key is not null
                   do update set run_after = excluded.run_after, updated_at = now()""",
                (kind, json.dumps({k: str(v) for k, v in payload.items()}), dedupe_key, delay),
            )

    async def requeue_stale(self) -> int:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "update public.jobs set status = 'queued', locked_at = null, updated_at = now()"
                " where status = 'running' and locked_at < now() - %s",
                (STALE_AFTER,),
            )
            return int(cur.rowcount)

    async def claim(self) -> Job | None:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """update public.jobs set status = 'running', locked_at = now(),
                          attempts = attempts + 1, updated_at = now()
                   where id = (
                     select id from public.jobs
                     where status = 'queued' and run_after <= now()
                     order by run_after
                     for update skip locked
                     limit 1)
                   returning id, kind, payload, attempts"""
            )
            row = await cur.fetchone()
        return Job(**row) if row else None

    async def complete(self, job: Job) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "update public.jobs set status = 'done', locked_at = null, updated_at = now()"
                " where id = %s",
                (job.id,),
            )

    async def fail(self, job: Job, error_type: str) -> None:
        final = job.attempts >= MAX_ATTEMPTS
        async with self._pool.connection() as conn:
            await conn.execute(
                """update public.jobs set status = %s, last_error = %s, locked_at = null,
                          run_after = now() + %s, updated_at = now()
                   where id = %s""",
                (
                    "failed" if final else "queued",
                    error_type[:80],
                    timedelta(seconds=30 * job.attempts),
                    job.id,
                ),
            )


@dataclass
class InMemoryJobQueue:
    """Records jobs for tests. Ignores delays: claim() returns jobs in order."""

    queued: list[Job] = field(default_factory=list)
    done: list[Job] = field(default_factory=list)
    failed: list[tuple[Job, str]] = field(default_factory=list)
    _next_id: int = 1
    _keys: dict[str, int] = field(default_factory=dict)

    async def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        delay: timedelta = timedelta(0),
        dedupe_key: str | None = None,
    ) -> None:
        _check_payload(payload)
        if dedupe_key and dedupe_key in self._keys:
            return
        job = Job(self._next_id, kind, {k: str(v) for k, v in payload.items()}, 0)
        self._next_id += 1
        self.queued.append(job)
        if dedupe_key:
            self._keys[dedupe_key] = job.id

    async def claim(self) -> Job | None:
        if not self.queued:
            return None
        job = self.queued.pop(0)
        self._keys = {k: v for k, v in self._keys.items() if v != job.id}
        return Job(job.id, job.kind, job.payload, job.attempts + 1)

    async def complete(self, job: Job) -> None:
        self.done.append(job)

    async def fail(self, job: Job, error_type: str) -> None:
        self.failed.append((job, error_type))
