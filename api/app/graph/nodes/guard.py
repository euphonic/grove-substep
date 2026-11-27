from typing import Any

from app.graph.state import GroveState
from app.safety.guard import Guard


def make_guard_node(guard: Guard) -> Any:
    async def guard_node(state: GroveState) -> dict[str, Any]:
        return {"safety": await guard.classify(state["messages"])}

    return guard_node
