"""Traditions list and the user's profile (onboarding and settings)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import current_user_id
from app.memory.store import update_profile
from app.profiles import ProfileRow
from app.routes.chat import RuntimeDep

router = APIRouter(tags=["profile"])
UserId = Annotated[str, Depends(current_user_id)]


class ProfileIn(BaseModel):
    default_tradition: str = Field(min_length=1, max_length=40)
    display_name: str | None = Field(default=None, max_length=60)
    timezone: str = Field(default="UTC", max_length=64)


@router.get("/traditions")
def list_traditions(rt: RuntimeDep) -> list[dict[str, str]]:
    return [
        {"id": p.id, "display_name": p.display_name, "description": p.description}
        for p in rt.packs.values()
    ]


@router.get("/profile")
async def get_profile(user_id: UserId, rt: RuntimeDep) -> dict[str, Any]:
    row = await rt.profiles.get(user_id) or ProfileRow()
    return {**row.model_dump(), "onboarded": row.default_tradition is not None}


@router.put("/profile")
async def put_profile(body: ProfileIn, user_id: UserId, rt: RuntimeDep) -> dict[str, Any]:
    if body.default_tradition not in rt.packs:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown tradition")
    row = ProfileRow(
        display_name=(body.display_name or "").strip() or None,
        default_tradition=body.default_tradition,
        timezone=body.timezone,
    )
    await rt.profiles.upsert(user_id, row)
    # The companion reads the store; keep it in step with the UI's table.
    await update_profile(rt.store, user_id, default_tradition=body.default_tradition)
    return {**row.model_dump(), "onboarded": True}
