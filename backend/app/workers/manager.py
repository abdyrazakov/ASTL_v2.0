"""Реестр заданий анализа. Гарантирует, что одновременно активно не более
одного задания (MVP): повторный запуск не создаёт конфликтующий worker."""
from __future__ import annotations

import threading
from pathlib import Path
from uuid import uuid4

from app.models.job import JobStatus
from app.models.profile import Profile
from app.workers.job_worker import JobWorker

ACTIVE_STATES = {JobStatus.queued, JobStatus.running, JobStatus.paused}


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, JobWorker] = {}

    def active_job(self) -> JobWorker | None:
        with self._lock:
            for job in self._jobs.values():
                if job.status in ACTIVE_STATES:
                    return job
        return None

    def start_job(self, profile: Profile, video_path: Path) -> JobWorker:
        with self._lock:
            active = self.active_job()
            if active is not None:
                raise RuntimeError(
                    f"Уже выполняется задание {active.run_id} (статус {active.status.value}). "
                    "Остановите его перед запуском нового."
                )
            run_id = uuid4().hex
            worker = JobWorker(run_id=run_id, profile=profile, video_path=video_path)
            self._jobs[run_id] = worker
        worker.start()
        return worker

    def get(self, run_id: str) -> JobWorker | None:
        return self._jobs.get(run_id)

    def list_jobs(self) -> list[JobWorker]:
        return sorted(self._jobs.values(), key=lambda j: j.run_id)


manager = JobManager()
