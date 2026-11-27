"""Graph state shared by every node (docs/SPEC.md, Agent architecture)."""

from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.safety.guard import SafetyLabel

Phase = Literal["chat", "offering", "playing", "reflecting"]


class GroveState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    thread_id: str
    safety: NotRequired[SafetyLabel]
    phase: NotRequired[Phase]
    # Filled in by later milestones (router, guide, render).
    brief: NotRequired[dict[str, Any] | None]
    script: NotRequired[str | None]
    render_result: NotRequired[dict[str, Any] | None]
