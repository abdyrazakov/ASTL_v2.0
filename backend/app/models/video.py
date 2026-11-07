from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class VideoInfo(BaseModel):
    video_id: str = Field(default_factory=lambda: uuid4().hex)
    filename: str
    width: int
    height: int
    fps: float
    duration_sec: float
    frame_count: int
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
