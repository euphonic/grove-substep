"""Long-lived resources shared by the API and the worker: database pools, checkpointer,
memory store, job queue, thread store, tradition packs and the compiled graph."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.store.base import BaseStore, IndexConfig
from langgraph.store.memory import InMemoryStore
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.adapters.embeddings import get_embedder
from app.adapters.llm import get_chat_model
from app.config import Settings
from app.graph.graph import GroveGraph, build_graph
from app.jobs import InMemoryJobQueue, JobQueue, PostgresJobQueue
from app.memory.keys import CHECKPOINT_KEY_INFO, derive_key
from app.memory.summarize import Summarizer, get_summarizer
from app.profiles import InMemoryProfileRepo, PostgresProfileRepo, ProfileRepo
from app.safety.guard import get_guard
from app.threads import InMemoryThreadStore, PostgresThreadStore, ThreadStore
from app.traditions import Pack, get_packs


@dataclass
class Runtime:
    settings: Settings
    graph: GroveGraph
    threads: ThreadStore
    store: BaseStore
    jobs: JobQueue
    packs: dict[str, Pack]
    summarizer: Summarizer
    profiles: ProfileRepo


def _pool(conninfo: str, **extra: Any) -> AsyncConnectionPool[Any]:
    return AsyncConnectionPool(
        conninfo,
        min_size=1,
        max_size=10,
        open=False,
        # Validate connections on checkout so the app recovers after a database restart.
        check=AsyncConnectionPool.check_connection,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row, **extra},
    )


def _index(settings: Settings) -> IndexConfig:
    embedder = get_embedder(settings)

    async def aembed(texts: Sequence[str]) -> list[list[float]]:
        return embedder.embed(list(texts))

    return {"dims": settings.embedding_dim, "embed": aembed, "fields": ["label"]}


@asynccontextmanager
async def open_runtime(settings: Settings) -> AsyncIterator[Runtime]:
    guard = get_guard(settings)
    companion = get_chat_model(settings, "main")
    packs = get_packs(settings.traditions_dir)
    summarizer = get_summarizer(settings)

    if settings.checkpointer_backend == "memory":
        store: BaseStore = InMemoryStore(index=_index(settings))
        graph = build_graph(
            guard=guard,
            companion_model=companion,
            checkpointer=InMemorySaver(),
            store=store,
            packs=packs,
        )
        yield Runtime(
            settings,
            graph,
            InMemoryThreadStore(),
            store,
            InMemoryJobQueue(),
            packs,
            summarizer,
            InMemoryProfileRepo(),
        )
        return

    # LangGraph tables live in a private schema; `extensions` is where Supabase keeps pgvector.
    lg_pool = _pool(
        settings.database_url,
        options=f"-c search_path={settings.langgraph_schema},extensions",
    )
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
        pg_store = AsyncPostgresStore(lg_pool, index=_index(settings))  # type: ignore[arg-type]
        await pg_store.setup()
        graph = build_graph(
            guard=guard,
            companion_model=companion,
            checkpointer=saver,
            store=pg_store,
            packs=packs,
        )
        yield Runtime(
            settings,
            graph,
            PostgresThreadStore(app_pool),
            pg_store,
            PostgresJobQueue(app_pool),
            packs,
            summarizer,
            PostgresProfileRepo(app_pool),
        )
    finally:
        await lg_pool.close()
        await app_pool.close()
