"""Thread ownership records (public.threads). Conversation content lives in the checkpointer."""

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


@dataclass(frozen=True)
class Thread:
    id: uuid.UUID
    user_id: str
    safety_flagged: bool
    created_at: datetime
    last_message_at: datetime

    def public(self) -> dict[str, Any]:
        """What the client may see (the safety flag is not exposed)."""
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "last_message_at": self.last_message_at.isoformat(),
        }


class ThreadStore(Protocol):
    async def create(self, user_id: str) -> Thread: ...
    async def get(self, thread_id: uuid.UUID, user_id: str) -> Thread | None: ...
    async def list(self, user_id: str, limit: int = 20) -> list[Thread]: ...
    async def touch(self, thread_id: uuid.UUID, *, safety_flagged: bool = False) -> None: ...


class PostgresThreadStore:
    """Runs as the API's database role; ownership is enforced by user_id in every query."""

    _COLUMNS = "id, user_id::text as user_id, safety_flagged, created_at, last_message_at"

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    async def create(self, user_id: str) -> Thread:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"insert into public.threads (user_id) values (%s) returning {self._COLUMNS}",  # noqa: S608
                (user_id,),
            )
            row = await cur.fetchone()
        assert row is not None
        return Thread(**row)

    async def get(self, thread_id: uuid.UUID, user_id: str) -> Thread | None:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"select {self._COLUMNS} from public.threads where id = %s and user_id = %s",  # noqa: S608
                (thread_id, user_id),
            )
            row = await cur.fetchone()
        return Thread(**row) if row else None

    async def list(self, user_id: str, limit: int = 20) -> list[Thread]:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"select {self._COLUMNS} from public.threads where user_id = %s"  # noqa: S608
                " order by last_message_at desc limit %s",
                (user_id, limit),
            )
            rows = await cur.fetchall()
        return [Thread(**r) for r in rows]

    async def touch(self, thread_id: uuid.UUID, *, safety_flagged: bool = False) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "update public.threads set last_message_at = now(),"
                " safety_flagged = safety_flagged or %s where id = %s",
                (safety_flagged, thread_id),
            )


@dataclass
class InMemoryThreadStore:
    """For tests and CHECKPOINTER_BACKEND=memory."""

    rows: dict[uuid.UUID, Thread] = field(default_factory=dict)

    async def create(self, user_id: str) -> Thread:
        now = datetime.now(UTC)
        t = Thread(uuid.uuid4(), user_id, False, now, now)
        self.rows[t.id] = t
        return t

    async def get(self, thread_id: uuid.UUID, user_id: str) -> Thread | None:
        t = self.rows.get(thread_id)
        return t if t and t.user_id == user_id else None

    async def list(self, user_id: str, limit: int = 20) -> list[Thread]:
        mine = [t for t in self.rows.values() if t.user_id == user_id]
        return sorted(mine, key=lambda t: t.last_message_at, reverse=True)[:limit]

    async def touch(self, thread_id: uuid.UUID, *, safety_flagged: bool = False) -> None:
        t = self.rows[thread_id]
        self.rows[thread_id] = replace(
            t,
            last_message_at=datetime.now(UTC),
            safety_flagged=t.safety_flagged or safety_flagged,
        )
