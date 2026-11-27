from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.adapters.llm import CANNED_REPLIES, MockChatModel
from app.graph.graph import build_graph
from app.safety.guard import RuleGuard
from app.safety.resources import CRISIS_RESPONSE

pytestmark = pytest.mark.anyio


class SpyModel(MockChatModel):
    """Records what the companion was sent."""

    calls: list[list[BaseMessage]] = []

    def _generate(self, messages: list[BaseMessage], *a: Any, **kw: Any) -> Any:
        self.calls.append(messages)
        return super()._generate(messages, *a, **kw)


def make(spy: SpyModel) -> Any:
    return build_graph(guard=RuleGuard(), companion_model=spy, checkpointer=InMemorySaver())


async def turn(graph: Any, text: str, thread: str = "t1") -> dict[str, Any]:
    out: dict[str, Any] = await graph.ainvoke(
        {"messages": [HumanMessage(content=text)], "user_id": "u", "thread_id": thread},
        {"configurable": {"thread_id": thread}},
    )
    return out


async def test_ok_message_reaches_companion() -> None:
    spy = SpyModel(calls=[])
    out = await turn(make(spy), "Had a nice walk today")
    assert out["safety"] == "ok"
    assert out["messages"][-1].content in CANNED_REPLIES
    assert len(spy.calls) == 1
    assert isinstance(spy.calls[0][0], SystemMessage)


async def test_crisis_skips_companion_and_gives_resources() -> None:
    spy = SpyModel(calls=[])
    out = await turn(make(spy), "I keep thinking about killing myself")
    assert out["safety"] == "crisis"
    reply = out["messages"][-1]
    assert isinstance(reply, AIMessage) and reply.content == CRISIS_RESPONSE
    assert "988" in reply.content
    assert spy.calls == []


async def test_concern_adds_check_in_instruction() -> None:
    spy = SpyModel(calls=[])
    await turn(make(spy), "I feel completely hopeless")
    system = str(spy.calls[0][0].content)
    assert "check in" in system and "Do not suggest a meditation" in system


async def test_history_persists_within_thread() -> None:
    spy = SpyModel(calls=[])
    graph = make(spy)
    await turn(graph, "first")
    out = await turn(graph, "second")
    assert [m.content for m in out["messages"] if isinstance(m, HumanMessage)] == [
        "first",
        "second",
    ]
    assert len(out["messages"]) == 4
