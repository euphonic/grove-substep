"""Per-user memory in the LangGraph store (docs/SPEC.md, LangGraph store namespaces).

Namespaces are ("user", <user_id>, <kind>). Values are plain JSON in the private langgraph
schema. Only theme labels are embedded for semantic search.
"""

import re
from datetime import date
from typing import Any

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

PROFILE_KEY = "profile"
THEME_LIMIT = 50  # cap per user; oldest are dropped by summarize


def ns(user_id: str, kind: str) -> tuple[str, ...]:
    return ("user", user_id, kind)


class Profile(BaseModel):
    default_tradition: str | None = None
    preferred_approaches: list[str] = Field(default_factory=list)
    summary: str | None = None


class Theme(BaseModel):
    label: str
    mood: str | None = None
    first_seen: date
    last_seen: date
    count: int = 1


def theme_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:60] or "theme"


async def get_profile(store: BaseStore, user_id: str) -> Profile:
    item = await store.aget(ns(user_id, "profile"), PROFILE_KEY)
    return Profile.model_validate(item.value) if item else Profile()


async def update_profile(store: BaseStore, user_id: str, **changes: Any) -> Profile:
    profile = (await get_profile(store, user_id)).model_copy(update=changes)
    await store.aput(
        ns(user_id, "profile"), PROFILE_KEY, profile.model_dump(mode="json"), index=False
    )
    return profile


async def all_themes(store: BaseStore, user_id: str) -> list[Theme]:
    items = await store.asearch(ns(user_id, "themes"), limit=THEME_LIMIT * 2)
    return [Theme.model_validate(i.value) for i in items]


async def recent_themes(store: BaseStore, user_id: str, limit: int = 5) -> list[Theme]:
    themes = await all_themes(store, user_id)
    return sorted(themes, key=lambda t: (t.last_seen, t.count), reverse=True)[:limit]


async def relevant_themes(
    store: BaseStore, user_id: str, query: str, limit: int = 3, min_score: float = 0.35
) -> list[Theme]:
    if not query.strip():
        return []
    items = await store.asearch(ns(user_id, "themes"), query=query, limit=limit)
    return [Theme.model_validate(i.value) for i in items if i.score is None or i.score >= min_score]


async def merge_themes(
    store: BaseStore, user_id: str, labels: list[tuple[str, str | None]], seen_on: date
) -> list[Theme]:
    """Upsert themes by normalised label: keep first_seen, bump last_seen and count."""
    space = ns(user_id, "themes")
    merged: list[Theme] = []
    for label, mood in labels:
        key = theme_key(label)
        existing = await store.aget(space, key)
        if existing:
            old = Theme.model_validate(existing.value)
            theme = old.model_copy(
                update={
                    "last_seen": max(old.last_seen, seen_on),
                    "count": old.count + 1,
                    "mood": mood or old.mood,
                }
            )
        else:
            theme = Theme(label=label, mood=mood, first_seen=seen_on, last_seen=seen_on)
        await store.aput(space, key, theme.model_dump(mode="json"), index=["label"])
        merged.append(theme)

    themes = await all_themes(store, user_id)
    if len(themes) > THEME_LIMIT:
        for old in sorted(themes, key=lambda t: (t.last_seen, t.count))[
            : len(themes) - THEME_LIMIT
        ]:
            await store.adelete(space, theme_key(old.label))
    return merged
