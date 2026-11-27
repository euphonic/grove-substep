"""Turns stored memory into a short context block for the companion's system prompt."""

from langgraph.store.base import BaseStore

from app.memory.store import Theme, get_profile, recent_themes, relevant_themes
from app.traditions import Pack

MEMORY_HEADER = "MEMORY:"


async def build_memory_context(
    store: BaseStore, user_id: str, latest_text: str, packs: dict[str, Pack]
) -> str | None:
    profile = await get_profile(store, user_id)
    themes: list[Theme] = []
    seen: set[str] = set()
    for t in [
        *await relevant_themes(store, user_id, latest_text),
        *await recent_themes(store, user_id),
    ]:
        if t.label.lower() not in seen:
            seen.add(t.label.lower())
            themes.append(t)
    themes = themes[:5]

    lines: list[str] = []
    if profile.default_tradition:
        pack = packs.get(profile.default_tradition)
        name = pack.display_name if pack else profile.default_tradition
        lines.append(f"Their default tradition: {name}")
    if themes:
        lines.append("What they've been carrying lately:")
        lines.extend(
            f"- {t.label}"
            + (f", feeling {t.mood}" if t.mood else "")
            + f" (last mentioned {t.last_seen.isoformat()})"
            for t in themes
        )
    if profile.summary:
        lines.append(f"Summary: {profile.summary}")
    return "\n".join([MEMORY_HEADER, *lines]) if lines else None
