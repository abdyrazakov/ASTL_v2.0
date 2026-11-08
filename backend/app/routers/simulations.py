"""API прогонов симуляции (этап 2). Повторяет структуру `jobs.py` этапа 1:
запуск/статус/пауза/продолжение/остановка/снимок/история, плюс управление
режимом контроллера и скоростью на лету, 2D-сцена и сравнение режимов."""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.core import storage
from app.routers.intersections import load_intersection
from app.simulation.history import find_comparison, list_simulation_runs
from app.simulation.manager import manager
from app.simulation.models import CompareRequest, SimulationStartRequest
from app.simulation.worker import profile_hash

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


class ModeRequest(BaseModel):
    mode: Literal["fixed", "adaptive"]


class SpeedRequest(BaseModel):
    speed: float = Field(gt=0, le=200.0)


def _run_path(run_id: str):
    if "/" in run_id or ".." in run_id:
        raise HTTPException(400, "Некорректный ID прогона")
    return storage.OUTPUT_DIR / run_id


def _get(run_id: str):
    run = manager.get(run_id)
    if run is None:
        raise HTTPException(404, "Прогон не найден (или выполнялся до перезапуска сервера)")
    return run


@router.post("")
async def start_simulation(req: SimulationStartRequest):
    profile = load_intersection(req.profile_id)
    try:
        run = manager.start_run(profile, req.controller_mode, req.seed, req.duration_sec, req.speed)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return run.progress()


@router.get("/active")
async def get_active():
    run = manager.active_run()
    if run is None:
        return {"active": False}
    return {"active": True, **run.progress()}


@router.get("")
async def list_live_runs():
    return [r.progress() for r in manager.list_runs()]


@router.get("/runs")
async def list_saved_runs(profile_id: str | None = None):
    """Все прогоны симуляции на диске (в т.ч. до перезапуска сервера)."""
    runs = list_simulation_runs()
    if profile_id:
        runs = [r for r in runs if r["metadata"].get("profile_id") == profile_id]
    return [
        {
            "run_id": r["metadata"]["run_id"],
            "profile_id": r["metadata"].get("profile_id"),
            "profile_name": r["metadata"].get("profile_name"),
            "created_at": r["metadata"].get("created_at"),
            "seed": r["metadata"].get("seed"),
            "controller_mode": r["metadata"].get("controller_mode"),
            "duration_sec": r["metadata"].get("duration_sec"),
            "final_status": r["metadata"].get("final_status"),
            "mode_switches": len(r["metadata"].get("controller_mode_switches") or []),
            "headless": r["metadata"].get("headless", False),
            "totals": (r["summary"] or {}).get("totals"),
        }
        for r in runs
    ]


@router.get("/comparison")
async def comparison(profile_id: str, seed: int | None = None, duration_sec: float | None = None):
    profile = load_intersection(profile_id)
    s = profile.traffic.seed if seed is None else seed
    return find_comparison(profile_hash(profile), s, duration_sec)


@router.post("/compare")
async def compare(req: CompareRequest):
    """Прогнать оба режима на одном seed «как можно быстрее» и вернуть сравнение
    из реально сохранённых прогонов."""
    profile = load_intersection(req.profile_id)
    try:
        workers = await run_in_threadpool(manager.run_comparison, profile, req.seed, req.duration_sec)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    seed = workers[0].seed
    return find_comparison(profile_hash(profile), seed, req.duration_sec)


@router.get("/{run_id}")
async def get_run(run_id: str):
    return _get(run_id).progress()


@router.post("/{run_id}/pause")
async def pause_run(run_id: str):
    run = _get(run_id)
    run.pause()
    return run.progress()


@router.post("/{run_id}/resume")
async def resume_run(run_id: str):
    run = _get(run_id)
    run.resume()
    return run.progress()


@router.post("/{run_id}/stop")
async def stop_run(run_id: str):
    run = _get(run_id)
    run.stop()
    return run.progress()


@router.patch("/{run_id}/controller")
async def set_controller(run_id: str, req: ModeRequest):
    run = _get(run_id)
    run.set_controller_mode(req.mode)
    return run.progress()


@router.patch("/{run_id}/speed")
async def set_speed(run_id: str, req: SpeedRequest):
    run = _get(run_id)
    run.set_speed(req.speed)
    return run.progress()


@router.get("/{run_id}/scene")
async def get_scene(run_id: str):
    return _get(run_id).scene()


@router.get("/{run_id}/snapshot")
async def get_snapshot(run_id: str):
    run = manager.get(run_id)
    if run is not None:
        return run.snapshot()
    path = _run_path(run_id) / "traffic_state.json"
    if not path.exists():
        raise HTTPException(404, "Пока нет данных по прогону")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path, since_key: str | None = None, since: float = 0.0) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue  # строка ещё дописывается worker'ом
            if since_key is None or obj.get(since_key, 0) >= since:
                out.append(obj)
    return out


@router.get("/{run_id}/history")
async def get_history(run_id: str, since: float = 0.0):
    return _read_jsonl(_run_path(run_id) / "traffic_history.jsonl", "timestamp_sec", since)


@router.get("/{run_id}/phase-log")
async def get_phase_log(run_id: str, since: float = 0.0):
    return _read_jsonl(_run_path(run_id) / "phase_log.jsonl", "end_sec", since)


@router.get("/{run_id}/summary")
async def get_summary(run_id: str):
    run = manager.get(run_id)
    if run is not None and run.status.value in ("running", "paused", "queued"):
        with run._lock:
            return run.sim.summary()
    path = _run_path(run_id) / "summary.json"
    if not path.exists():
        raise HTTPException(404, "Итогов пока нет")
    return json.loads(path.read_text(encoding="utf-8"))
