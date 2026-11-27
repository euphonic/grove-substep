"""Long-lived resources: database pools, checkpointer, thread store and the compiled graph."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.adapters.llm import get_chat_model
from app.config import Settings
from app.graph.graph import GroveGraph, build_graph
from app.memory.keys import CHECKPOINT_KEY_INFO, derive_key
from app.safety.guard import get_guard
from app.threads import InMemoryThreadStore, PostgresThreadStore, ThreadStore


@dataclass
class Runtime:
    graph: GroveGraph
    threads: ThreadStore


def _pool(conninfo: str, **extra: Any) -> AsyncConnectionPool[Any]:
    return AsyncConnectionPool(
        conninfo,
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row, **extra},
    )


@asynccontextmanager
async def open_runtime(settings: Settings) -> AsyncIterator[Runtime]:
    guard = get_guard(settings)
    companion = get_chat_model(settings, "main")

    if settings.checkpointer_backend == "memory":
        graph = build_graph(guard=guard, companion_model=companion, checkpointer=InMemorySaver())
        yield Runtime(graph=graph, threads=InMemoryThreadStore())
        return

    # LangGraph tables live in a private schema (see the threads migration).
    lg_pool = _pool(settings.database_url, options=f"-c search_path={settings.langgraph_schema}")
    app_pool = _pool(settings.database_url)
    await lg_pool.open()
    await app_pool.open()
    try:
        # Conversation state is encrypted (AES-EAX) before it reaches Postgres.
        serde = EncryptedSerializer.from_pycryptodome_aes(
            key=derive_key(settings.journal_encryption_key, CHECKPOINT_KEY_INFO)
        )
        saver = AsyncPostgresSaver(lg_pool, serde=serde)
        await saver.setup()
        graph = build_graph(guard=guard, companion_model=companion, checkpointer=saver)
        yield Runtime(graph=graph, threads=PostgresThreadStore(app_pool))
    finally:
        await lg_pool.close()
        await app_pool.close()
