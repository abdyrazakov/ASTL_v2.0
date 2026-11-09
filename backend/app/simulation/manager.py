"""Реестр прогонов симуляции — тот же паттерн, что `JobManager` этапа 1:
одновременно активен не более одного прогона, повторный запуск возвращает ошибку,
а не второй конфликтующий worker."""
from __future__ import annotations

import threading
from uuid import uuid4

from app.models.job import JobStatus
from app.simulation.models import IntersectionProfile
from app.simulation.worker import SimulationWorker

ACTIVE_STATES = {JobStatus.queued, JobStatus.running, JobStatus.paused}


class SimulationManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runs: dict[str, SimulationWorker] = {}
        self._batch_running = False

    def active_run(self) -> SimulationWorker | None:
        with self._lock:
            for run in self._runs.values():
                if run.status in ACTIVE_STATES and not run.headless:
                    return run
        return None

    def _check_free(self) -> None:
        active = self.active_run()
        if active is not None:
            raise RuntimeError(
                f"Уже выполняется прогон {active.run_id} (статус {active.status.value}). "
                "Остановите его перед запуском нового."
            )
        if self._batch_running:
            raise RuntimeError("Выполняется сравнение режимов — дождитесь его окончания.")

    def start_run(
        self,
        profile: IntersectionProfile,
        controller_mode: str,
        seed: int | None,
        duration_sec: float | None,
        speed: float,
    ) -> SimulationWorker:
        with self._lock:
            self._check_free()
            worker = SimulationWorker(
                run_id=uuid4().hex, profile=profile, controller_mode=controller_mode,
                seed=seed, duration_sec=duration_sec, speed=speed,
            )
            self._runs[worker.run_id] = worker
        worker.start()
        return worker

    def run_comparison(
        self, profile: IntersectionProfile, seed: int | None, duration_sec: float
    ) -> list[SimulationWorker]:
        """Оба режима на одном seed, «как можно быстрее», последовательно в
        вызывающем потоке. Занимает слот активного прогона на время сравнения."""
        with self._lock:
            self._check_free()
            self._batch_running = True
        try:
            workers = []
            for mode in ("fixed", "adaptive"):
                w = SimulationWorker(
                    run_id=uuid4().hex, profile=profile, controller_mode=mode,
                    seed=seed, duration_sec=duration_sec, speed=0, headless=True,
                )
                with self._lock:
                    self._runs[w.run_id] = w
                w.run_blocking()
                workers.append(w)
            return workers
        finally:
            with self._lock:
                self._batch_running = False

    def get(self, run_id: str) -> SimulationWorker | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[SimulationWorker]:
        return sorted(
            self._runs.values(),
            key=lambda r: r.started_at.timestamp() if r.started_at else 0.0,
            reverse=True,
        )


manager = SimulationManager()
