from typing import Any

from langchain_core.messages import AIMessage

from app.graph.state import GroveState
from app.safety.resources import CRISIS_RESPONSE


async def crisis_response_node(state: GroveState) -> dict[str, Any]:
    # Fixed, reviewed text: no model output on this path, and never a meditation offer.
    return {"messages": [AIMessage(content=CRISIS_RESPONSE)], "phase": "chat"}
