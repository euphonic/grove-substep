import base64
import os
from collections.abc import Iterator

import psycopg
import pytest

from app.config import Settings


@pytest.fixture(autouse=True, scope="session")
def _cleanup_test_jobs() -> Iterator[None]:
    """Jobs of kind 'test' exist only in these tests; don't leave them for the dev worker."""
    yield
    url = Settings(_env_file=None, checkpointer_backend="memory").database_url  # type: ignore[call-arg]
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("delete from public.jobs where kind = 'test'")


@pytest.fixture
def db_settings(tmp_path: object) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        local_storage_dir=tmp_path,  # type: ignore[arg-type]
        app_env="test",
        checkpointer_backend="postgres",
        journal_encryption_key=base64.urlsafe_b64encode(os.urandom(32)).decode(),
        summarize_delay_seconds=0,
    )


@pytest.fixture
def user_id(db_settings: Settings) -> Iterator[str]:
    with psycopg.connect(db_settings.database_url, autocommit=True) as conn:
        row = conn.execute(
            "insert into auth.users (id, email, aud, role) values (gen_random_uuid(),"
            " 'db-test-' || gen_random_uuid() || '@rls.test', 'authenticated',"
            " 'authenticated') returning id::text"
        ).fetchone()
        assert row
        uid: str = row[0]
        yield uid
        conn.execute("delete from auth.users where id = %s", (uid,))
        conn.execute("delete from public.jobs where payload->>'user_id' = %s", (uid,))
        conn.execute("delete from langgraph.store where prefix like %s", (f"user.{uid}.%",))
