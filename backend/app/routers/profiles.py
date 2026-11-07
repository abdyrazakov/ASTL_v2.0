from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.core.storage import PROFILES_DIR, atomic_write_json
from app.models.profile import Profile

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _path(profile_id: str):
    return PROFILES_DIR / f"{profile_id}.json"


def _validation_messages(exc: ValidationError) -> list[str]:
    msgs = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        msgs.append(f"{loc}: {err['msg']}")
    return msgs


@router.post("", response_model=Profile)
async def create_profile(payload: dict):
    try:
        profile = Profile.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, {"errors": _validation_messages(exc)})
    atomic_write_json(_path(profile.profile_id), json.loads(profile.model_dump_json()))
    return profile


@router.get("", response_model=list[Profile])
async def list_profiles():
    out = []
    for p in sorted(PROFILES_DIR.glob("*.json")):
        out.append(Profile.model_validate(json.loads(p.read_text(encoding="utf-8"))))
    return sorted(out, key=lambda p: p.updated_at, reverse=True)


@router.get("/{profile_id}", response_model=Profile)
async def get_profile(profile_id: str):
    path = _path(profile_id)
    if not path.exists():
        raise HTTPException(404, "Профиль не найден")
    return Profile.model_validate(json.loads(path.read_text(encoding="utf-8")))


@router.put("/{profile_id}", response_model=Profile)
async def update_profile(profile_id: str, payload: dict):
    path = _path(profile_id)
    if not path.exists():
        raise HTTPException(404, "Профиль не найден")
    payload = dict(payload)
    payload["profile_id"] = profile_id
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        profile = Profile.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, {"errors": _validation_messages(exc)})
    atomic_write_json(path, json.loads(profile.model_dump_json()))
    return profile


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str):
    path = _path(profile_id)
    if not path.exists():
        raise HTTPException(404, "Профиль не найден")
    path.unlink()
    return {"ok": True}


@router.post("/{profile_id}/duplicate", response_model=Profile)
async def duplicate_profile(profile_id: str):
    path = _path(profile_id)
    if not path.exists():
        raise HTTPException(404, "Профиль не найден")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("profile_id", None)
    data["name"] = f"{data['name']} (копия)"
    data["status"] = "preliminary"
    new_profile = Profile.model_validate(data)
    atomic_write_json(_path(new_profile.profile_id), json.loads(new_profile.model_dump_json()))
    return new_profile


@router.post("/validate")
async def validate_profile(payload: dict):
    try:
        Profile.model_validate(payload)
    except ValidationError as exc:
        return {"valid": False, "errors": _validation_messages(exc)}
    return {"valid": True, "errors": []}
