from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from app.core.storage import VIDEOS_DIR, atomic_write_json
from app.models.video import VideoInfo

router = APIRouter(prefix="/api/videos", tags=["videos"])

ALLOWED_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _video_dir(video_id: str) -> Path:
    return VIDEOS_DIR / video_id


@router.post("", response_model=VideoInfo)
async def upload_video(file: UploadFile):
    ext = Path(file.filename or "video.mp4").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Неподдерживаемый формат файла: {ext}")

    info = VideoInfo(filename=file.filename or "video.mp4", width=0, height=0, fps=0, duration_sec=0, frame_count=0)
    vdir = _video_dir(info.video_id)
    vdir.mkdir(parents=True, exist_ok=True)
    dest = vdir / f"source{ext}"
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)

    cap = cv2.VideoCapture(str(dest))
    if not cap.isOpened():
        shutil.rmtree(vdir, ignore_errors=True)
        raise HTTPException(400, "Не удалось прочитать видеофайл (повреждён или неподдерживаемый кодек)")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps else 0.0
    cap.release()

    info.width, info.height, info.fps = w, h, fps
    info.frame_count, info.duration_sec = frame_count, duration

    atomic_write_json(vdir / "meta.json", json.loads(info.model_dump_json()))
    return info


@router.get("", response_model=list[VideoInfo])
async def list_videos():
    out = []
    for vdir in sorted(VIDEOS_DIR.glob("*")):
        meta = vdir / "meta.json"
        if meta.exists():
            out.append(VideoInfo.model_validate(json.loads(meta.read_text(encoding="utf-8"))))
    return sorted(out, key=lambda v: v.uploaded_at, reverse=True)


@router.get("/{video_id}", response_model=VideoInfo)
async def get_video(video_id: str):
    meta = _video_dir(video_id) / "meta.json"
    if not meta.exists():
        raise HTTPException(404, "Видео не найдено")
    return VideoInfo.model_validate(json.loads(meta.read_text(encoding="utf-8")))


def _find_source_file(video_id: str) -> Path:
    vdir = _video_dir(video_id)
    for p in vdir.glob("source.*"):
        return p
    raise HTTPException(404, "Видео не найдено")


@router.get("/{video_id}/file")
async def get_video_file(video_id: str):
    path = _find_source_file(video_id)
    return FileResponse(path, media_type="video/mp4")


@router.get("/{video_id}/frame")
async def get_frame(video_id: str, t: float = 0.0):
    """Кадр видео на заданной секунде — используется ползунком выбора кадра в редакторе."""
    path = _find_source_file(video_id)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise HTTPException(404, "Видео не найдено")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    target_frame = max(0, min(int(t * fps), max(frame_count - 1, 0)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise HTTPException(500, "Не удалось извлечь кадр")
    ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok2:
        raise HTTPException(500, "Не удалось закодировать кадр")
    return Response(content=buf.tobytes(), media_type="image/jpeg")
