"""One graph per turn: guard first, then companion or crisis_response."""

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore

from app.graph.nodes.companion import make_companion_node
from app.graph.nodes.crisis import crisis_response_node
from app.graph.nodes.guard import make_guard_node
from app.graph.state import GroveState
from app.safety.guard import Guard
from app.traditions import Pack

# Nodes whose messages are streamed to the user. The guard is never one of them.
USER_FACING_NODES = frozenset({"companion", "crisis_response"})

GroveGraph = CompiledStateGraph[GroveState, None, GroveState, GroveState]


def _route_after_guard(state: GroveState) -> Literal["companion", "crisis_response"]:
    return "crisis_response" if state.get("safety") == "crisis" else "companion"


def build_graph(
    *,
    guard: Guard,
    companion_model: BaseChatModel,
    checkpointer: BaseCheckpointSaver[str] | None,
    store: BaseStore | None = None,
    packs: dict[str, Pack] | None = None,
) -> GroveGraph:
    g = StateGraph(GroveState)
    g.add_node("guard", make_guard_node(guard))
    g.add_node("companion", make_companion_node(companion_model, packs or {}))
    g.add_node("crisis_response", crisis_response_node)
    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", _route_after_guard, ["companion", "crisis_response"])
    g.add_edge("companion", END)
    g.add_edge("crisis_response", END)
    return g.compile(checkpointer=checkpointer, store=store)
