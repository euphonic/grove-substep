"""RLS tests against local Supabase. Run with `make check-db` (needs `supabase start`).

Each test runs in a transaction that is rolled back, so nothing persists.
"""

import json
import uuid
from collections.abc import Iterator

import psycopg
import pytest

from app.config import Settings

pytestmark = pytest.mark.db

USER_TABLES = ["profiles", "journal_entries", "sessions", "uploads", "threads"]


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    url = Settings(_env_file=None).database_url  # type: ignore[call-arg]
    try:
        c = psycopg.connect(url, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.fail("local Supabase is not running: run `supabase start` first")
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _make_user(conn: psycopg.Connection) -> uuid.UUID:
    uid = uuid.uuid4()
    conn.execute(
        "insert into auth.users (id, email, aud, role)"
        " values (%s, %s, 'authenticated', 'authenticated')",
        (uid, f"{uid}@rls.test"),
    )
    conn.execute("insert into public.profiles (user_id, display_name) values (%s, 'rls')", (uid,))
    conn.execute(
        "insert into public.journal_entries (user_id, source, body_encrypted)"
        " values (%s, 'paste', %s)",
        (uid, b"ciphertext"),
    )
    conn.execute(
        "insert into public.sessions (user_id, tradition, approach, minutes) "
        "values (%s, 'mindfulness', 'breath', 10)",
        (uid,),
    )
    conn.execute(
        "insert into public.uploads (user_id, filename, mime) values (%s, 'a.txt', 'text/plain')",
        (uid,),
    )
    conn.execute("insert into public.threads (user_id) values (%s)", (uid,))
    return uid


def _act_as(conn: psycopg.Connection, uid: uuid.UUID | None) -> None:
    if uid is None:
        conn.execute("set local role anon")
        conn.execute("select set_config('request.jwt.claims', '', true)")
        return
    conn.execute("set local role authenticated")
    claims = json.dumps({"sub": str(uid), "role": "authenticated"})
    conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))


@pytest.mark.parametrize("table", USER_TABLES)
def test_user_sees_only_own_rows(conn: psycopg.Connection, table: str) -> None:
    alice, bob = _make_user(conn), _make_user(conn)
    _act_as(conn, alice)
    rows = conn.execute(f"select user_id from public.{table}").fetchall()  # noqa: S608
    assert rows and {r[0] for r in rows} == {alice}
    assert bob not in {r[0] for r in rows}


@pytest.mark.parametrize("table", USER_TABLES)
def test_user_cannot_modify_other_users_rows(conn: psycopg.Connection, table: str) -> None:
    alice, bob = _make_user(conn), _make_user(conn)
    _act_as(conn, alice)
    cur = conn.execute(f"delete from public.{table} where user_id = %s", (bob,))  # noqa: S608
    assert cur.rowcount == 0


def test_user_cannot_insert_as_someone_else(conn: psycopg.Connection) -> None:
    alice, bob = _make_user(conn), _make_user(conn)
    _act_as(conn, alice)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            "insert into public.journal_entries (user_id, source, body_encrypted) "
            "values (%s, 'paste', 'x')",
            (bob,),
        )


@pytest.mark.parametrize("table", [*USER_TABLES, "image_library", "audio_cache"])
def test_anon_has_no_access(conn: psycopg.Connection, table: str) -> None:
    _make_user(conn)
    _act_as(conn, None)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"select 1 from public.{table}")  # noqa: S608


def test_authenticated_cannot_read_audio_cache(conn: psycopg.Connection) -> None:
    _act_as(conn, _make_user(conn))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select 1 from public.audio_cache")


def test_authenticated_can_read_but_not_write_image_library(conn: psycopg.Connection) -> None:
    _act_as(conn, _make_user(conn))
    conn.execute("select 1 from public.image_library")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            "insert into public.image_library (tradition, theme, time_of_day, storage_key) "
            "values ('x', 'y', 'morning', 'k')"
        )


def test_journal_has_no_plaintext_column(conn: psycopg.Connection) -> None:
    cols = conn.execute(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = 'public' and table_name = 'journal_entries'"
    ).fetchall()
    types = dict(cols)
    assert types["body_encrypted"] == "bytea"
    assert not any(t in ("text", "character varying") for c, t in cols if c.startswith("body"))
