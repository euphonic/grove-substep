from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from app.graph.state import GroveState
from app.prompts import load_prompt

HISTORY_LIMIT = 40


def make_companion_node(model: BaseChatModel) -> Any:
    async def companion_node(state: GroveState) -> dict[str, Any]:
        system = load_prompt("companion")
        if state.get("safety") == "concern":
            system = f"{system}\n\n{load_prompt('companion_concern')}"
        history = state["messages"][-HISTORY_LIMIT:]
        reply = await model.ainvoke([SystemMessage(content=system), *history])
        return {"messages": [reply], "phase": "chat"}

    return companion_node
