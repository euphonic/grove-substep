"""public.profiles: what the UI lists (display name, default tradition, timezone)."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel


class ProfileRow(BaseModel):
    display_name: str | None = None
    default_tradition: str | None = None
    timezone: str = "UTC"


class ProfileRepo(Protocol):
    async def get(self, user_id: str) -> ProfileRow | None: ...
    async def upsert(self, user_id: str, row: ProfileRow) -> None: ...


class PostgresProfileRepo:
    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    async def get(self, user_id: str) -> ProfileRow | None:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "select display_name, default_tradition, timezone from public.profiles"
                " where user_id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
        return ProfileRow(**row) if row else None

    async def upsert(self, user_id: str, row: ProfileRow) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                """insert into public.profiles (user_id, display_name, default_tradition, timezone)
                   values (%s, %s, %s, %s)
                   on conflict (user_id) do update set display_name = excluded.display_name,
                     default_tradition = excluded.default_tradition,
                     timezone = excluded.timezone""",
                (user_id, row.display_name, row.default_tradition, row.timezone),
            )


@dataclass
class InMemoryProfileRepo:
    rows: dict[str, ProfileRow] = field(default_factory=dict)

    async def get(self, user_id: str) -> ProfileRow | None:
        return self.rows.get(user_id)

    async def upsert(self, user_id: str, row: ProfileRow) -> None:
        self.rows[user_id] = row
