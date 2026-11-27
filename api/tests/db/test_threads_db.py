"""Conversation persistence against local Supabase (make check-db)."""

import base64
import json
import os
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.auth import current_user_id
from app.config import Settings, get_settings
from app.main import create_app

pytestmark = pytest.mark.db


@pytest.fixture
def db_settings(tmp_path: object) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        local_storage_dir=tmp_path,  # type: ignore[arg-type]
        app_env="test",
        checkpointer_backend="postgres",
        journal_encryption_key=base64.urlsafe_b64encode(os.urandom(32)).decode(),
    )


@pytest.fixture
def user_id(db_settings: Settings) -> Iterator[str]:
    with psycopg.connect(db_settings.database_url, autocommit=True) as conn:
        row = conn.execute(
            "insert into auth.users (id, email, aud, role) values (gen_random_uuid(),"
            " 'thread-test-' || gen_random_uuid() || '@rls.test', 'authenticated',"
            " 'authenticated') returning id::text"
        ).fetchone()
        assert row
        uid: str = row[0]
        yield uid
        conn.execute("delete from auth.users where id = %s", (uid,))  # cascades to threads


def _client(settings: Settings, uid: str) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[current_user_id] = lambda: uid
    return TestClient(app)


def _send(c: TestClient, thread_id: str, text: str) -> str:
    resp = c.post(f"/threads/{thread_id}/messages", json={"text": text})
    tokens = []
    for block in resp.text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        if fields["event"] == "error":
            pytest.fail(f"turn failed: {fields['data']}")
        if fields["event"] == "token":
            tokens.append(json.loads(fields["data"])["text"])
    return "".join(tokens)


def test_conversation_survives_restart(db_settings: Settings, user_id: str) -> None:
    with _client(db_settings, user_id) as c:
        thread_id = c.post("/threads").json()["id"]
        reply = _send(c, thread_id, "Had a calm morning")

    # A brand-new app (new pools, new graph) is what a reload after a restart looks like.
    with _client(db_settings, user_id) as c:
        assert c.get("/threads").json()[0]["id"] == thread_id
        history = c.get(f"/threads/{thread_id}/messages").json()["messages"]
    assert history == [
        {"role": "user", "content": "Had a calm morning"},
        {"role": "assistant", "content": reply},
    ]


def test_crisis_sets_flag_without_storing_label_text(db_settings: Settings, user_id: str) -> None:
    with _client(db_settings, user_id) as c:
        thread_id = c.post("/threads").json()["id"]
        _send(c, thread_id, "I want to die")
    with psycopg.connect(db_settings.database_url) as conn:
        row = conn.execute(
            "select safety_flagged from public.threads where id = %s", (thread_id,)
        ).fetchone()
    assert row == (True,)


def test_checkpoints_live_in_private_schema(db_settings: Settings, user_id: str) -> None:
    with _client(db_settings, user_id) as c:
        c.post("/threads")  # lifespan runs saver.setup()
    with psycopg.connect(db_settings.database_url) as conn:
        schemas = {
            r[0]
            for r in conn.execute(
                "select table_schema from information_schema.tables"
                " where table_name in ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes')"
            ).fetchall()
        }
        assert schemas == {"langgraph"}
        for role in ("anon", "authenticated"):
            ok = conn.execute(
                "select has_schema_privilege(%s, 'langgraph', 'USAGE')", (role,)
            ).fetchone()
            assert ok == (False,), f"{role} must not reach the langgraph schema"


def test_checkpoints_are_encrypted_at_rest(db_settings: Settings, user_id: str) -> None:
    marker = "lantern-orchard-marker"
    with _client(db_settings, user_id) as c:
        thread_id = c.post("/threads").json()["id"]
        _send(c, thread_id, f"My secret word is {marker}.")
        # Round trip still works through the encrypted serializer.
        history = c.get(f"/threads/{thread_id}/messages").json()["messages"]
    assert marker in history[0]["content"]

    with psycopg.connect(db_settings.database_url) as conn:
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            hits = conn.execute(
                f"select count(*) from langgraph.{table} t where thread_id = %s"  # noqa: S608
                " and position(%s in encode(convert_to(t::text, 'UTF8'), 'escape')) > 0",
                (thread_id, marker),
            ).fetchone()
            assert hits == (0,), f"plaintext message found in langgraph.{table}"
        types = {
            r[0]
            for r in conn.execute(
                "select distinct type from langgraph.checkpoint_blobs where thread_id = %s"
                " and channel = 'messages'",
                (thread_id,),
            ).fetchall()
        }
    assert types and all(t.endswith("+aes") for t in types), types


def test_wrong_key_cannot_read_history(db_settings: Settings, user_id: str) -> None:
    with _client(db_settings, user_id) as c:
        thread_id = c.post("/threads").json()["id"]
        _send(c, thread_id, "hello")
    other_key = db_settings.model_copy(
        update={"journal_encryption_key": base64.urlsafe_b64encode(os.urandom(32)).decode()}
    )
    with _client(other_key, user_id) as c, pytest.raises(ValueError):
        c.get(f"/threads/{thread_id}/messages")
