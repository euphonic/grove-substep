from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from app.graph.state import GroveState
from app.memory.context import build_memory_context
from app.prompts import load_prompt
from app.traditions import Pack

HISTORY_LIMIT = 40


def _latest_user_text(state: GroveState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


def make_companion_node(model: BaseChatModel, packs: dict[str, Pack]) -> Any:
    async def companion_node(state: GroveState, runtime: Runtime[None]) -> dict[str, Any]:
        parts = [load_prompt("companion")]
        if runtime.store is not None:
            memory = await build_memory_context(
                runtime.store, state["user_id"], _latest_user_text(state), packs
            )
            if memory:
                parts.append(f"{load_prompt('companion_memory')}\n\n{memory}")
        if state.get("safety") == "concern":
            parts.append(load_prompt("companion_concern"))
        history = state["messages"][-HISTORY_LIMIT:]
        reply = await model.ainvoke([SystemMessage(content="\n\n".join(parts)), *history])
        return {"messages": [reply], "phase": "chat"}

    return companion_node
