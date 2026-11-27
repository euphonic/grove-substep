"""Chat endpoints. Every message goes through the graph, whose entry node is the guard."""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.auth import current_user_id
from app.graph.graph import USER_FACING_NODES
from app.graph.state import GroveState
from app.runtime import Runtime
from app.threads import Thread

log = logging.getLogger("grove.chat")
router = APIRouter(prefix="/threads", tags=["chat"])

UserId = Annotated[str, Depends(current_user_id)]
GENERIC_ERROR = "Something went wrong on our side. Please try again in a moment."


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


def get_runtime(request: Request) -> Runtime:
    rt: Runtime = request.app.state.runtime
    return rt


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]


async def _owned_thread(rt: Runtime, thread_id: uuid.UUID, user_id: str) -> Thread:
    thread = await rt.threads.get(thread_id, user_id)
    if thread is None:
        # Same response for "missing" and "someone else's", so ids can't be probed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "thread not found")
    return thread


def _config(thread: Thread) -> RunnableConfig:
    return {"configurable": {"thread_id": str(thread.id)}}


def _text(content: Any) -> str:
    """Message content may be a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in content
            if not isinstance(b, dict) or b.get("type") == "text"
        )
    return ""


def _to_public(msg: BaseMessage) -> dict[str, str] | None:
    if isinstance(msg, HumanMessage):
        return {"role": "user", "content": _text(msg.content)}
    if isinstance(msg, AIMessage):
        return {"role": "assistant", "content": _text(msg.content)}
    return None


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("")
async def list_threads(user_id: UserId, rt: RuntimeDep) -> list[dict[str, Any]]:
    return [t.public() for t in await rt.threads.list(user_id)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_thread(user_id: UserId, rt: RuntimeDep) -> dict[str, Any]:
    return (await rt.threads.create(user_id)).public()


@router.get("/{thread_id}/messages")
async def get_messages(
    thread_id: uuid.UUID, user_id: UserId, rt: RuntimeDep
) -> dict[str, list[dict[str, str]]]:
    thread = await _owned_thread(rt, thread_id, user_id)
    snapshot = await rt.graph.aget_state(_config(thread))
    messages: list[BaseMessage] = snapshot.values.get("messages", []) if snapshot.values else []
    return {"messages": [m for m in map(_to_public, messages) if m]}


@router.post("/{thread_id}/messages")
async def post_message(
    thread_id: uuid.UUID, body: MessageIn, user_id: UserId, rt: RuntimeDep
) -> StreamingResponse:
    thread = await _owned_thread(rt, thread_id, user_id)
    config = _config(thread)
    turn_input: GroveState = {
        "messages": [HumanMessage(content=body.text)],
        "user_id": user_id,
        "thread_id": str(thread.id),
    }

    async def events() -> AsyncIterator[str]:
        yield _sse("start", {})
        try:
            async for chunk, meta in rt.graph.astream(turn_input, config, stream_mode="messages"):
                node = meta.get("langgraph_node") if isinstance(meta, dict) else None
                if node not in USER_FACING_NODES:
                    continue
                text = _text(getattr(chunk, "content", ""))
                if text:
                    yield _sse("token", {"text": text})
            snapshot = await rt.graph.aget_state(config)
            crisis = snapshot.values.get("safety") == "crisis"
            await rt.threads.touch(thread.id, safety_flagged=crisis)
            yield _sse("end", {"crisis": crisis})
        except Exception as exc:  # noqa: BLE001
            # Never log message content: only the error type.
            log.error("chat turn failed: %s", type(exc).__name__)
            yield _sse("error", {"message": GENERIC_ERROR})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
