from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.skill import InstalledSkill
from app.models.user import User

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillResponse(BaseModel):
    name: str
    version: str
    type: str
    status: str
    description: str | None
    tools: list[str]


class SkillListResponse(BaseModel):
    skills: list[SkillResponse]


@router.get("", response_model=SkillListResponse)
async def list_skills(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InstalledSkill).order_by(InstalledSkill.name))
    skills = result.scalars().all()
    items = []
    for s in skills:
        try:
            manifest = json.loads(s.manifest) if isinstance(s.manifest, str) else s.manifest
            tools = manifest.get("tools", [])
        except Exception:
            tools = []
        items.append(SkillResponse(
            name=s.name, version=s.version, type=s.type,
            status=s.status, description=s.description, tools=tools,
        ))
    return SkillListResponse(skills=items)
