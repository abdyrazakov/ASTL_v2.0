"""CRUD профилей перекрёстка этапа 2 — тот же паттерн, что `profiles.py` этапа 1
(создание, список, чтение, обновление, удаление, дублирование, валидация), плюс
создание из стандартного шаблона. Хранение: backend/data/intersections/<id>.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.core.storage import DATA_DIR, atomic_write_json
from app.simulation.models import IntersectionProfile, check_profile
from app.simulation.templates import build_template, template_info

router = APIRouter(prefix="/api/intersections", tags=["intersections"])

INTERSECTIONS_DIR = DATA_DIR / "intersections"
INTERSECTIONS_DIR.mkdir(parents=True, exist_ok=True)


def _path(profile_id: str):
    if not profile_id or "/" in profile_id or ".." in profile_id:
        raise HTTPException(400, "Некорректный ID профиля")
    return INTERSECTIONS_DIR / f"{profile_id}.json"


def validation_messages(exc: ValidationError) -> list[str]:
    msgs = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        msg = str(err["msg"])
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        # семантическая проверка профиля склеивает ошибки через "; "
        for part in msg.split("; "):
            msgs.append(f"{loc}: {part}" if loc else part)
    return msgs


def load_intersection(profile_id: str) -> IntersectionProfile:
    path = _path(profile_id)
    if not path.exists():
        raise HTTPException(404, "Профиль перекрёстка не найден")
    try:
        return IntersectionProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except ValidationError as exc:
        raise HTTPException(422, {"errors": validation_messages(exc)})


def _save(profile: IntersectionProfile) -> None:
    atomic_write_json(_path(profile.profile_id), json.loads(profile.model_dump_json()))


@router.get("/templates")
async def list_templates():
    return template_info()


@router.post("/from-template/{key}", response_model=IntersectionProfile)
async def create_from_template(key: str):
    try:
        profile = build_template(key)
    except KeyError:
        raise HTTPException(404, "Шаблон не найден")
    _save(profile)
    return profile


@router.post("", response_model=IntersectionProfile)
async def create_intersection(payload: dict):
    payload = dict(payload)
    payload.pop("profile_id", None)
    try:
        profile = IntersectionProfile.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, {"errors": validation_messages(exc)})
    _save(profile)
    return profile


@router.get("", response_model=list[IntersectionProfile])
async def list_intersections():
    out = []
    for p in sorted(INTERSECTIONS_DIR.glob("*.json")):
        try:
            out.append(IntersectionProfile.model_validate(json.loads(p.read_text(encoding="utf-8"))))
        except (ValidationError, json.JSONDecodeError):
            continue  # повреждённый файл не должен ронять весь список
    return sorted(out, key=lambda p: p.updated_at, reverse=True)


@router.post("/validate")
async def validate_intersection(payload: dict):
    try:
        profile = IntersectionProfile.model_validate(payload)
    except ValidationError as exc:
        return {"valid": False, "errors": validation_messages(exc), "warnings": []}
    _, warnings = check_profile(profile)
    return {"valid": True, "errors": [], "warnings": warnings}


@router.get("/{profile_id}", response_model=IntersectionProfile)
async def get_intersection(profile_id: str):
    return load_intersection(profile_id)


@router.put("/{profile_id}", response_model=IntersectionProfile)
async def update_intersection(profile_id: str, payload: dict):
    path = _path(profile_id)
    if not path.exists():
        raise HTTPException(404, "Профиль перекрёстка не найден")
    payload = dict(payload)
    payload["profile_id"] = profile_id
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        profile = IntersectionProfile.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, {"errors": validation_messages(exc)})
    _save(profile)
    return profile


@router.delete("/{profile_id}")
async def delete_intersection(profile_id: str):
    path = _path(profile_id)
    if not path.exists():
        raise HTTPException(404, "Профиль перекрёстка не найден")
    path.unlink()
    return {"ok": True}


@router.post("/{profile_id}/duplicate", response_model=IntersectionProfile)
async def duplicate_intersection(profile_id: str):
    src = load_intersection(profile_id)
    data = json.loads(src.model_dump_json())
    for k in ("profile_id", "created_at", "updated_at"):
        data.pop(k, None)
    data["name"] = f"{src.name} (копия)"
    profile = IntersectionProfile.model_validate(data)
    _save(profile)
    return profile
