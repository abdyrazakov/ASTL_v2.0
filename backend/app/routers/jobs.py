from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.storage import PROFILES_DIR, VIDEOS_DIR, run_dir
from app.models.job import JobCreateRequest
from app.models.profile import Profile
from app.workers.manager import manager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _load_profile(profile_id: str) -> Profile:
    path = PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        raise HTTPException(404, "Профиль не найден")
    return Profile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _find_source_file(video_id: str) -> Path:
    vdir = VIDEOS_DIR / video_id
    for p in vdir.glob("source.*"):
        return p
    raise HTTPException(404, "Видео не найдено")


@router.post("")
async def create_job(req: JobCreateRequest):
    profile = _load_profile(req.profile_id)
    video_path = _find_source_file(req.video_id)
    if not profile.lanes:
        raise HTTPException(422, "В профиле нет ни одной полосы — нечего анализировать")
    try:
        worker = manager.start_job(profile, video_path)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return worker.progress()


@router.get("/active")
async def get_active_job():
    job = manager.active_job()
    if job is None:
        return {"active": False}
    return {"active": True, **job.progress()}


@router.get("")
async def list_jobs():
    return [j.progress() for j in manager.list_jobs()]


@router.get("/{run_id}")
async def get_job(run_id: str):
    job = manager.get(run_id)
    if job is None:
        raise HTTPException(404, "Задание не найдено")
    return job.progress()


@router.post("/{run_id}/pause")
async def pause_job(run_id: str):
    job = manager.get(run_id)
    if job is None:
        raise HTTPException(404, "Задание не найдено")
    job.pause()
    return job.progress()


@router.post("/{run_id}/resume")
async def resume_job(run_id: str):
    job = manager.get(run_id)
    if job is None:
        raise HTTPException(404, "Задание не найдено")
    job.resume()
    return job.progress()


@router.post("/{run_id}/stop")
async def stop_job(run_id: str):
    job = manager.get(run_id)
    if job is None:
        raise HTTPException(404, "Задание не найдено")
    job.stop()
    return job.progress()


@router.patch("/{run_id}/render-options")
async def set_render_options(run_id: str, options: dict):
    job = manager.get(run_id)
    if job is None:
        raise HTTPException(404, "Задание не найдено")
    job.set_render_options(options)
    return {"render_options": job.render_options}


@router.get("/{run_id}/snapshot")
async def get_snapshot(run_id: str):
    path = run_dir(run_id) / "traffic_state.json"
    if not path.exists():
        raise HTTPException(404, "Пока нет данных по заданию")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/{run_id}/history")
async def get_history(run_id: str, since: float = 0.0):
    path = run_dir(run_id) / "traffic_history.jsonl"
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("timestamp_sec", 0) >= since:
                out.append(obj)
    return out


@router.get("/{run_id}/live.mjpg")
async def live_mjpeg(run_id: str):
    job = manager.get(run_id)
    if job is None:
        raise HTTPException(404, "Задание не найдено")

    async def gen():
        boundary = b"--frame"
        while True:
            current = manager.get(run_id)
            if current is None:
                break
            jpeg = current.latest_jpeg()
            if jpeg is not None:
                yield (
                    boundary + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jpeg)).encode()
                    + b"\r\n\r\n" + jpeg + b"\r\n"
                )
            await asyncio.sleep(0.12)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")
