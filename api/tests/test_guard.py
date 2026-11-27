from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.safety.guard import GuardResult, ModelGuard, RuleGuard

pytestmark = pytest.mark.anyio


def msgs(*texts: str) -> list[BaseMessage]:
    return [HumanMessage(content=t) for t in texts]


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("I want to die", "crisis"),
        ("thinking about SUICIDE lately", "crisis"),
        ("I feel hopeless", "concern"),
        ("work is killing me lol", "ok"),
        ("lovely walk today", "ok"),
    ],
)
async def test_rule_guard(text: str, label: str) -> None:
    assert await RuleGuard().classify(msgs(text)) == label


async def test_rule_guard_reads_latest_user_message_only() -> None:
    history: list[BaseMessage] = [
        HumanMessage(content="I want to die"),
        AIMessage(content="I'm here."),
        HumanMessage(content="I'm feeling better now, thanks"),
    ]
    assert await RuleGuard().classify(history) == "ok"


class _FakeStructured:
    def __init__(self, result: Any = None, exc: Exception | None = None) -> None:
        self.result, self.exc = result, exc
        self.seen: list[Any] = []

    def with_config(self, **_: Any) -> "_FakeStructured":
        return self

    async def ainvoke(self, messages: Any) -> Any:
        self.seen.append(messages)
        if self.exc:
            raise self.exc
        return self.result


class _FakeModel:
    def __init__(self, structured: _FakeStructured) -> None:
        self.structured = structured

    def with_structured_output(self, schema: Any) -> _FakeStructured:
        assert schema is GuardResult
        return self.structured


async def test_model_guard_returns_model_label() -> None:
    guard = ModelGuard(_FakeModel(_FakeStructured(GuardResult(label="crisis"))))  # type: ignore[arg-type]
    assert await guard.classify(msgs("anything")) == "crisis"


async def test_model_guard_fails_safe_to_concern() -> None:
    guard = ModelGuard(_FakeModel(_FakeStructured(exc=TimeoutError())))  # type: ignore[arg-type]
    assert await guard.classify(msgs("anything")) == "concern"


async def test_model_guard_rejects_unexpected_output() -> None:
    guard = ModelGuard(_FakeModel(_FakeStructured({"label": "ok"})))  # type: ignore[arg-type]
    assert await guard.classify(msgs("anything")) == "concern"
