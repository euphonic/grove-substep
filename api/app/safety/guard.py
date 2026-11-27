"""Crisis-risk classification for every user input.

Two implementations, chosen by config:
- RuleGuard: deterministic keyword rules. Used offline (mock mode) so `make check` can test
  routing. It is NOT a substitute for the model guard; real risk detection is evaluated with
  `make check-live`.
- ModelGuard: the fast model with structured output. Fails safe to "concern" on any error.
"""

import logging
import re
from collections.abc import Sequence
from typing import Literal, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from app.adapters.llm import get_chat_model
from app.config import Settings
from app.prompts import load_prompt

log = logging.getLogger("grove.guard")

SafetyLabel = Literal["ok", "concern", "crisis"]
CONTEXT_MESSAGES = 6


class GuardResult(BaseModel):
    label: SafetyLabel


class Guard(Protocol):
    async def classify(self, messages: Sequence[BaseMessage]) -> SafetyLabel: ...


def _latest_user_text(messages: Sequence[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


_CRISIS_PATTERNS = [
    r"\bkill(ing)? my ?self\b",
    r"\bsuicid",
    r"\bend (it all|my life)\b",
    r"\b(want|wish|wanted) to die\b",
    r"\bbetter off dead\b",
    r"\bno reason to (live|go on)\b",
    r"\b(don'?t|do not) want to (be alive|live|wake up)\b",
    r"\b(hope|wish) i (don'?t|do not|never) wake up\b",
    r"\b(hurt|harm|cut|cutting|burn) (myself|my ?self)\b",
    r"\bself[- ]?harm",
    r"\boverdos",
    r"\bcan'?t go on\b",
    r"\bdisappear (forever|for good)\b",
]
_CONCERN_PATTERNS = [
    r"\bhopeless",
    r"\bworthless\b",
    r"\bcan'?t cope\b",
    r"\bfalling apart\b",
    r"\bpanic attack",
    r"\bcan'?t (stop crying|breathe)\b",
    r"\boverwhelmed\b",
    r"\bnothing matters\b",
]


class RuleGuard:
    def __init__(self) -> None:
        self._crisis = [re.compile(p, re.IGNORECASE) for p in _CRISIS_PATTERNS]
        self._concern = [re.compile(p, re.IGNORECASE) for p in _CONCERN_PATTERNS]

    async def classify(self, messages: Sequence[BaseMessage]) -> SafetyLabel:
        text = _latest_user_text(messages)
        if any(p.search(text) for p in self._crisis):
            return "crisis"
        if any(p.search(text) for p in self._concern):
            return "concern"
        return "ok"


class ModelGuard:
    def __init__(self, model: BaseChatModel) -> None:
        # "nostream" keeps the classifier's output out of the user-facing token stream.
        self._runnable = model.with_structured_output(GuardResult).with_config(
            tags=["nostream"], run_name="guard"
        )

    async def classify(self, messages: Sequence[BaseMessage]) -> SafetyLabel:
        context = [m for m in messages if isinstance(m, HumanMessage)][-CONTEXT_MESSAGES:]
        if not context:
            return "ok"
        try:
            result = await self._runnable.ainvoke(
                [SystemMessage(content=load_prompt("guard")), *context]
            )
        except Exception as exc:  # noqa: BLE001 - fail safe, never fail open
            log.warning("guard model failed (%s); treating as concern", type(exc).__name__)
            return "concern"
        if isinstance(result, GuardResult):
            return result.label
        log.warning("guard returned unexpected type; treating as concern")
        return "concern"


def get_guard(settings: Settings) -> Guard:
    if settings.llm_provider_fast == "mock":
        return RuleGuard()
    return ModelGuard(get_chat_model(settings, "fast"))
