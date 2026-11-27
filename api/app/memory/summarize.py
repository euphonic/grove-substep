"""The background `summarize` job: conversation -> profile summary + themes.

RuleSummarizer is the offline (mock) stand-in: keyword-mapped themes, no summary text.
ModelSummarizer uses the fast model with structured output.
Crisis content is never stored: both prompt rules and a final filter enforce it.
"""

import logging
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.adapters.llm import get_chat_model
from app.config import Settings
from app.memory.store import get_profile, merge_themes, update_profile
from app.prompts import load_prompt
from app.safety.guard import CRISIS_PATTERNS

log = logging.getLogger("grove.summarize")


class ThemeOut(BaseModel):
    label: str = Field(min_length=2, max_length=40)
    mood: str | None = Field(default=None, max_length=20)


class SummaryOut(BaseModel):
    summary: str | None = Field(default=None, max_length=400)
    themes: list[ThemeOut] = Field(default_factory=list, max_length=5)


class Summarizer(Protocol):
    async def summarize(
        self, messages: Sequence[BaseMessage], current_summary: str | None
    ) -> SummaryOut: ...


_THEME_KEYWORDS: dict[str, str] = {
    "work stress": r"\b(work|job|boss|deadline|office|meeting)s?\b",
    "sleep": r"\b(sleep|slept|insomnia|exhausted|tired)\b",
    "family": r"\b(mum|mom|dad|family|parents?|sister|brother)\b",
    "relationships": r"\b(partner|girlfriend|boyfriend|husband|wife|breakup|divorce)\b",
    "grief": r"\b(grief|grieving|died|passed away|funeral)\b",
    "anxiety": r"\b(anxious|anxiety|worried|worry|nervous|panic)\b",
    "gratitude": r"\b(grateful|gratitude|thankful)\b",
    "health": r"\b(sick|illness|pain|doctor|hospital)\b",
    "moving home": r"\b(move|moving|new flat|new house|relocat\w*)\b",
}


class RuleSummarizer:
    async def summarize(
        self, messages: Sequence[BaseMessage], current_summary: str | None
    ) -> SummaryOut:
        text = " ".join(str(m.content) for m in messages if isinstance(m, HumanMessage))
        themes = [
            ThemeOut(label=label)
            for label, pattern in _THEME_KEYWORDS.items()
            if re.search(pattern, text, re.IGNORECASE)
        ][:5]
        return SummaryOut(summary=current_summary, themes=themes)


class ModelSummarizer:
    def __init__(self, model: BaseChatModel) -> None:
        self._runnable = model.with_structured_output(SummaryOut).with_config(
            tags=["nostream"], run_name="summarize"
        )

    async def summarize(
        self, messages: Sequence[BaseMessage], current_summary: str | None
    ) -> SummaryOut:
        transcript = "\n".join(
            f"{'Person' if isinstance(m, HumanMessage) else 'Companion'}: {m.content}"
            for m in messages
            if isinstance(m, (HumanMessage, AIMessage))
        )
        existing = current_summary or "(none yet)"
        result = await self._runnable.ainvoke(
            [
                SystemMessage(content=load_prompt("summarize")),
                HumanMessage(
                    content=f"Existing summary: {existing}\n\nConversation:\n{transcript}"
                ),
            ]
        )
        if not isinstance(result, SummaryOut):
            raise TypeError("summarizer returned unexpected type")
        return result


def get_summarizer(settings: Settings) -> Summarizer:
    if settings.llm_provider_fast == "mock":
        return RuleSummarizer()
    return ModelSummarizer(get_chat_model(settings, "fast"))


_crisis = [re.compile(p, re.IGNORECASE) for p in CRISIS_PATTERNS]
_crisis_words = re.compile(r"suicid|self[- ]?harm|crisis|kill|overdose|die\b", re.IGNORECASE)


def _safe(text: str | None) -> bool:
    return (
        bool(text)
        and not any(p.search(text or "") for p in _crisis)
        and not (_crisis_words.search(text or ""))
    )


async def summarize_thread(rt: Any, payload: dict[str, str]) -> None:
    """Job handler. `rt` is an app.runtime.Runtime (typed loosely to avoid an import cycle)."""
    user_id, thread_id = payload["user_id"], payload["thread_id"]
    thread = await rt.threads.get(uuid.UUID(thread_id), user_id)
    if thread is None:
        return  # thread deleted, or ids don't match: nothing to do
    snapshot = await rt.graph.aget_state({"configurable": {"thread_id": thread_id}})
    messages: list[BaseMessage] = (snapshot.values or {}).get("messages", [])
    if not any(isinstance(m, HumanMessage) for m in messages):
        return

    profile = await get_profile(rt.store, user_id)
    out = await rt.summarizer.summarize(messages[-60:], profile.summary)
    themes = [(t.label.strip().lower(), t.mood) for t in out.themes if _safe(t.label)]
    await merge_themes(rt.store, user_id, themes, datetime.now(UTC).date())
    if out.summary and _safe(out.summary) and out.summary != profile.summary:
        await update_profile(rt.store, user_id, summary=out.summary)
    log.info("summarized thread: %d themes", len(themes))
