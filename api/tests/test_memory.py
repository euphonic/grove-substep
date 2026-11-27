from datetime import date
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.store.memory import InMemoryStore

from app.adapters.embeddings import MockEmbedder
from app.memory.context import build_memory_context
from app.memory.store import get_profile, merge_themes, recent_themes, update_profile
from app.memory.summarize import RuleSummarizer
from app.traditions import Pack

pytestmark = pytest.mark.anyio


def make_store() -> InMemoryStore:
    emb = MockEmbedder(64)

    async def aembed(texts: Any) -> list[list[float]]:
        return emb.embed(list(texts))

    return InMemoryStore(index={"dims": 64, "embed": aembed, "fields": ["label"]})


PACKS = {"raja-yoga": Pack(id="raja-yoga", display_name="Raja Yoga (BK)", description="d")}


async def test_profile_roundtrip() -> None:
    store = make_store()
    assert (await get_profile(store, "u")).default_tradition is None
    await update_profile(store, "u", default_tradition="raja-yoga")
    await update_profile(store, "u", summary="Working through a job change.")
    p = await get_profile(store, "u")
    assert p.default_tradition == "raja-yoga" and p.summary


async def test_merge_themes_keeps_first_seen_and_counts() -> None:
    store = make_store()
    await merge_themes(store, "u", [("work stress", None)], date(2026, 11, 1))
    await merge_themes(store, "u", [("Work Stress", "tense"), ("sleep", None)], date(2026, 11, 5))
    themes = {t.label.lower(): t for t in await recent_themes(store, "u")}
    ws = themes["work stress"]
    assert (ws.first_seen, ws.last_seen, ws.count, ws.mood) == (
        date(2026, 11, 1),
        date(2026, 11, 5),
        2,
        "tense",
    )
    assert "sleep" in themes


async def test_themes_are_per_user() -> None:
    store = make_store()
    await merge_themes(store, "alice", [("grief", None)], date(2026, 11, 1))
    assert await recent_themes(store, "bob") == []


async def test_memory_context_includes_tradition_and_themes() -> None:
    store = make_store()
    await update_profile(store, "u", default_tradition="raja-yoga")
    await merge_themes(store, "u", [("work stress", None)], date(2026, 11, 1))
    ctx = await build_memory_context(store, "u", "how was work", PACKS)
    assert ctx is not None
    assert "Raja Yoga (BK)" in ctx and "- work stress" in ctx


async def test_no_memory_no_context() -> None:
    assert await build_memory_context(make_store(), "new-user", "hi", PACKS) is None


async def test_rule_summarizer_themes_from_user_messages_only() -> None:
    out = await RuleSummarizer().summarize(
        [
            HumanMessage(content="My boss moved the deadline again and I slept badly."),
            AIMessage(content="That sounds tiring. How is your family?"),
        ],
        None,
    )
    labels = {t.label for t in out.themes}
    assert labels == {"work stress", "sleep"}  # "family" was only in the AI message
