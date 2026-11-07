from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    paused = "paused"
    completed = "completed"
    error = "error"
    stopped = "stopped"


class JobCreateRequest(BaseModel):
    video_id: str
    profile_id: str


class RunMetadata(BaseModel):
    schema_version: str = "1.0"
    run_id: str = Field(default_factory=lambda: uuid4().hex)
    profile_id: str
    profile_name: str
    video_id: str
    video_filename: str
    model_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_fps: float
    source_width: int
    source_height: int
    source_duration_sec: float
    device: str  # "cpu" | "cuda"


class JobProgress(BaseModel):
    run_id: str
    video_id: str
    profile_id: str
    status: JobStatus
    video_time_sec: float = 0.0
    source_duration_sec: float = 0.0
    frames_processed: int = 0
    frames_total: int = 0
    processing_fps: float = 0.0
    source_fps: float = 0.0
    realtime_ratio: float = 0.0  # processing_fps / source_fps
    started_at: datetime | None = None
    error_message: str | None = None
    model_ready: bool = False
