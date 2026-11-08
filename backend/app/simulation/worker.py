"""Фоновый worker одного прогона симуляции — тот же паттерн, что `JobWorker` этапа 1.

Каждый прогон получает свой run_id и папку output/<run_id>/. Пауза останавливает
цикл шагов модели — модельное время не идёт, поэтому ожидание и задержка во время
паузы не растут (как время видео в этапе 1). Скорость (×1/×5/×50…) меняет только
то, сколько тиков модели выполняется за секунду реального времени; результат
прогона от скорости не зависит (тот же seed → те же числа).

Экспорт (output/<run_id>/):
- traffic_state.json    — последний снимок (атомарная запись), схема снимка 1.1;
- traffic_history.jsonl — снимок каждую секунду модельного времени;
- traffic_metrics.csv   — колонки этапа 1 + новые колонки этапа 2;
- phase_log.jsonl       — завершённые зелёные: фаза, начало, длительность, причина;
- signal_log.jsonl      — каждый переход автомата сигналов с полным набором сигналов;
- events.jsonl          — смены режима контроллера, скорости, пауза/продолжение;
- profile.json          — профиль перекрёстка (схема intersection 2.0);
- run_metadata.json     — seed, режим, параметры генератора трафика, итоговый статус;
- summary.json          — итоговые показатели прогона.
"""
from __future__ import annotations

import csv
import hashlib
import json
import threading
import time
import traceback
from datetime import datetime, timezone

from app.core.storage import atomic_write_json, run_dir
from app.models.job import JobStatus
from app.simulation.engine import Simulation
from app.simulation.models import SIM_DT, IntersectionProfile

HISTORY_EMIT_INTERVAL_SEC = 1.0
MAX_TICKS_PER_BATCH = 2000
RUN_METADATA_SCHEMA_VERSION = "2.0"

CSV_COLUMNS = [
    # колонки этапа 1 (те же имена и порядок)
    "timestamp_sec", "run_id", "lane_id", "lane_name", "vehicles", "queued",
    "queue_truncated_by_frame", "avg_wait_sec", "max_wait_sec", "wait_sample_size",
    "flow_count_window", "flow_window_available_sec", "flow_window_target_sec",
    "total_crossings", "composition_car", "composition_bus", "composition_truck",
    "composition_motorcycle",
    # новые колонки этапа 2
    "avg_delay_sec", "stops_per_vehicle", "throughput_per_hour", "departed_count",
    "entry_backlog", "controller_mode", "signal_state", "active_phase", "phase_remaining_sec",
]


def profile_hash(profile: IntersectionProfile) -> str:
    """Хэш содержимого профиля, влияющего на прогон (без имени/дат/ID/заметок и
    без seed — seed сравнивается отдельно). Нужен, чтобы сравнивать
    «фиксированный vs адаптивный» только на действительно одинаковом сценарии."""
    data = json.loads(profile.model_dump_json())
    for k in ("profile_id", "name", "notes", "created_at", "updated_at", "template"):
        data.pop(k, None)
    data.get("traffic", {}).pop("seed", None)
    data.get("traffic", {}).pop("scenario_name", None)
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class SimulationWorker:
    def __init__(
        self,
        run_id: str,
        profile: IntersectionProfile,
        controller_mode: str = "adaptive",
        seed: int | None = None,
        duration_sec: float | None = 3600.0,
        speed: float = 5.0,
        headless: bool = False,
    ):
        self.run_id = run_id
        self.kind = "simulation"
        self.profile = profile
        self.initial_mode = controller_mode
        self.duration_sec = duration_sec
        self.speed = speed
        self.headless = headless
        self.out_dir = run_dir(run_id)
        self.sim = Simulation(profile, controller_mode, seed)
        self.seed = self.sim.seed

        self.status = JobStatus.queued
        self.error_message: str | None = None
        self.started_at: datetime | None = None
        self.realtime_ratio = 0.0

        self._run_event = threading.Event()
        self._run_event.set()
        self._stop_flag = threading.Event()
        self._lock = threading.RLock()  # защищает self.sim от одновременного чтения/записи
        self._thread: threading.Thread | None = None

        self._next_emit_sec = 0.0
        self._signal_log_idx = 0
        self._green_log_idx = 0
        self._latest_snapshot: dict | None = None
        self._csv_fh = None
        self._csv_writer = None
        self._jsonl_fh = None
        self._phase_fh = None
        self._signal_fh = None
        self._events_fh = None

    # --- управление ---

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def run_blocking(self) -> None:
        """Прогон «как можно быстрее» в текущем потоке (сравнение режимов)."""
        self._run()

    def pause(self) -> None:
        with self._lock:
            if self.status == JobStatus.running:
                self._run_event.clear()
                self.status = JobStatus.paused
                self._event("pause")

    def resume(self) -> None:
        with self._lock:
            if self.status == JobStatus.paused:
                self._run_event.set()
                self.status = JobStatus.running
                self._event("resume")

    def stop(self) -> None:
        self._stop_flag.set()
        self._run_event.set()  # разбудить, если на паузе

    def set_speed(self, speed: float) -> None:
        with self._lock:
            self.speed = float(speed)
            self._event("speed", speed=self.speed)

    def set_controller_mode(self, mode: str) -> None:
        with self._lock:
            prev = self.sim.controller_mode
            self.sim.set_controller_mode(mode)
            if prev != mode:
                self._event("controller_mode", **{"from": prev, "to": mode})

    # --- чтение состояния (из потоков API) ---

    def progress(self) -> dict:
        with self._lock:
            m = self.sim.machine
            snap_state = m.state.value
            return {
                "run_id": self.run_id,
                "kind": self.kind,
                "profile_id": self.profile.profile_id,
                "profile_name": self.profile.name,
                "status": self.status.value,
                "sim_time_sec": round(self.sim.time_sec, 2),
                "duration_sec": self.duration_sec,
                "speed": self.speed,
                "realtime_ratio": round(self.realtime_ratio, 2),
                "controller_mode": self.sim.controller_mode,
                "initial_controller_mode": self.initial_mode,
                "mode_switches": len(self.sim.controller_mode_switches),
                "seed": self.seed,
                "signal_state": snap_state,
                "active_phase": m.phase if snap_state in ("GREEN", "YELLOW") else None,
                "next_phase": m.next_phase if snap_state in ("YELLOW", "ALL_RED") else None,
                "phase_remaining_sec": m.remaining_sec(self.sim._last_demand),
                "phase_remaining_is_estimate": self.sim.controller_mode == "adaptive" and snap_state == "GREEN",
                "started_at": self.started_at,
                "error_message": self.error_message,
                "headless": self.headless,
            }

    def scene(self) -> dict:
        with self._lock:
            return self.sim.scene()

    def snapshot(self) -> dict:
        with self._lock:
            snap = self.sim.snapshot()
        return self._decorate(snap)

    def green_log(self) -> list[dict]:
        with self._lock:
            return list(self.sim.machine.green_log)

    # --- основной цикл ---

    def _run(self) -> None:
        # Итоговый статус становится виден снаружи только ПОСЛЕ записи summary.json и
        # run_metadata.json: клиент, увидевший «завершено/остановлено», не должен
        # прочитать недописанные файлы экспорта.
        final = JobStatus.error
        try:
            final = self._run_impl()
        except Exception as exc:  # noqa: BLE001
            self.error_message = f"{exc}\n{traceback.format_exc(limit=5)}"
        finally:
            self._finalize(final)
            self.status = final

    def _target_reached(self) -> bool:
        return self.duration_sec is not None and self.sim.time_sec >= self.duration_sec - 1e-9

    def _run_impl(self) -> JobStatus:
        self._open_export_files()
        self._write_static_exports()
        self.status = JobStatus.running
        self.started_at = datetime.now(timezone.utc)
        with self._lock:
            self._emit(force=True)

        if self.headless:
            while not self._stop_flag.is_set() and not self._target_reached():
                with self._lock:
                    for _ in range(MAX_TICKS_PER_BATCH):
                        if self._target_reached():
                            break
                        self._step_once()
                    self._flush_logs()
        else:
            self._run_realtime()

        with self._lock:
            self._emit(force=True)
            self._flush_logs()
        if self._stop_flag.is_set() and not self._target_reached():
            return JobStatus.stopped
        return JobStatus.completed

    def _run_realtime(self) -> None:
        last_wall = time.monotonic()
        carry = 0.0
        ratio_wall, ratio_model = 0.0, 0.0
        while not self._stop_flag.is_set() and not self._target_reached():
            if not self._run_event.is_set():
                self._run_event.wait(timeout=0.2)
                last_wall = time.monotonic()  # время на паузе не превращается в тики
                continue
            now = time.monotonic()
            elapsed = now - last_wall
            last_wall = now
            carry += elapsed * self.speed / SIM_DT
            n = int(carry)
            carry -= n
            if n > MAX_TICKS_PER_BATCH:  # не успеваем — честно отстаём от заданной скорости
                n, carry = MAX_TICKS_PER_BATCH, 0.0
            done = 0
            with self._lock:
                for _ in range(n):
                    if self._target_reached() or self._stop_flag.is_set():
                        break
                    if not self._run_event.is_set():
                        break
                    self._step_once()
                    done += 1
                self._flush_logs()
            ratio_wall += elapsed
            ratio_model += done * SIM_DT
            if ratio_wall >= 1.0:
                self.realtime_ratio = ratio_model / ratio_wall
                ratio_wall, ratio_model = 0.0, 0.0
            time.sleep(0.02)

    def _step_once(self) -> None:
        self.sim.step()
        if self.sim.time_sec + 1e-9 >= self._next_emit_sec:
            self._emit()

    # --- экспорт ---

    def _decorate(self, snap: dict) -> dict:
        snap = dict(snap)
        snap["run_id"] = self.run_id
        snap["profile_id"] = self.profile.profile_id
        snap["window_duration_sec"] = HISTORY_EMIT_INTERVAL_SEC
        snap["seed"] = self.seed
        return snap

    def _emit(self, force: bool = False) -> None:
        t = self.sim.time_sec
        if not force and t + 1e-9 < self._next_emit_sec:
            return
        self._next_emit_sec = (int(t / HISTORY_EMIT_INTERVAL_SEC + 1e-9) + 1) * HISTORY_EMIT_INTERVAL_SEC
        snap = self._decorate(self.sim.snapshot())
        if self._latest_snapshot is not None and self._latest_snapshot["timestamp_sec"] == snap["timestamp_sec"]:
            atomic_write_json(self.out_dir / "traffic_state.json", snap)
            return  # тот же момент времени уже записан в историю
        self._latest_snapshot = snap
        self.sim.update_digest()
        atomic_write_json(self.out_dir / "traffic_state.json", snap)
        self._jsonl_fh.write(json.dumps(snap, ensure_ascii=False) + "\n")
        for lane in snap["lanes"]:
            comp = lane["vehicle_types"]
            self._csv_writer.writerow(
                {
                    "timestamp_sec": snap["timestamp_sec"],
                    "run_id": self.run_id,
                    "lane_id": lane["lane_id"],
                    "lane_name": lane["name"],
                    "vehicles": lane["vehicles"],
                    "queued": lane["queued"],
                    "queue_truncated_by_frame": lane["queue_truncated_by_frame"],
                    "avg_wait_sec": lane["avg_wait_sec"],
                    "max_wait_sec": lane["max_wait_sec"],
                    "wait_sample_size": lane["wait_sample_size"],
                    "flow_count_window": lane["flow_count_window"],
                    "flow_window_available_sec": lane["flow_window_available_sec"],
                    "flow_window_target_sec": lane["flow_window_target_sec"],
                    "total_crossings": lane["total_crossings"],
                    "composition_car": comp.get("car", 0),
                    "composition_bus": comp.get("bus", 0),
                    "composition_truck": comp.get("truck", 0),
                    "composition_motorcycle": comp.get("motorcycle", 0),
                    "avg_delay_sec": lane["avg_delay_sec"],
                    "stops_per_vehicle": lane["stops_per_vehicle"],
                    "throughput_per_hour": lane["throughput_per_hour"],
                    "departed_count": lane["departed_count"],
                    "entry_backlog": lane["entry_backlog"],
                    "controller_mode": snap["controller_mode"],
                    "signal_state": snap["signal_state"],
                    "active_phase": snap["active_phase"] or "",
                    "phase_remaining_sec": snap["phase_remaining_sec"],
                }
            )

    def _flush_logs(self) -> None:
        m = self.sim.machine
        for tr in m.transitions[self._signal_log_idx:]:
            self._signal_fh.write(json.dumps(tr, ensure_ascii=False) + "\n")
        self._signal_log_idx = len(m.transitions)
        for g in m.green_log[self._green_log_idx:]:
            self._phase_fh.write(json.dumps(g, ensure_ascii=False) + "\n")
        self._green_log_idx = len(m.green_log)
        for fh in (self._jsonl_fh, self._csv_fh, self._signal_fh, self._phase_fh, self._events_fh):
            fh.flush()

    def _event(self, kind: str, **data) -> None:
        if self._events_fh is None:
            return
        rec = {"t": self.sim.time_sec, "event": kind, "wall_time": datetime.now(timezone.utc).isoformat(), **data}
        self._events_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._events_fh.flush()

    def _open_export_files(self) -> None:
        d = self.out_dir
        self._csv_fh = open(d / "traffic_metrics.csv", "w", newline="", encoding="utf-8")
        self._csv_writer = csv.DictWriter(self._csv_fh, fieldnames=CSV_COLUMNS)
        self._csv_writer.writeheader()
        self._jsonl_fh = open(d / "traffic_history.jsonl", "w", encoding="utf-8")
        self._phase_fh = open(d / "phase_log.jsonl", "w", encoding="utf-8")
        self._signal_fh = open(d / "signal_log.jsonl", "w", encoding="utf-8")
        self._events_fh = open(d / "events.jsonl", "w", encoding="utf-8")

    def metadata(self) -> dict:
        p = self.profile
        return {
            "schema_version": RUN_METADATA_SCHEMA_VERSION,
            "kind": "simulation",
            "run_id": self.run_id,
            "profile_id": p.profile_id,
            "profile_name": p.name,
            "profile_hash": profile_hash(p),
            "template": p.template,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seed": self.seed,
            "controller_mode": self.initial_mode,
            "duration_sec": self.duration_sec,
            "dt_sec": SIM_DT,
            "headless": self.headless,
            "traffic_generator": {
                "model": "независимый пуассоновский поток на каждую полосу; "
                         "сценарий — множители интенсивности (прореживание)",
                "rng": "random.Random(f'{seed}|{lane_id}') на каждую полосу",
                "arrival_rate_vph": {lane.id: lane.arrival_rate_vph for lane in p.lanes},
                "composition": p.traffic.composition,
                "min_gap_m": p.traffic.min_gap_m,
                "scenario_name": p.traffic.scenario_name,
                "scenario": [s.model_dump() for s in p.traffic.scenario],
            },
            "timings": p.timings.model_dump(),
            "adaptive_params": p.adaptive.model_dump(),
        }

    def _write_static_exports(self) -> None:
        atomic_write_json(self.out_dir / "profile.json", json.loads(self.profile.model_dump_json()))
        atomic_write_json(self.out_dir / "run_metadata.json", self.metadata())

    def _finalize(self, final: JobStatus) -> None:
        summary = None
        try:
            with self._lock:
                summary = self.sim.summary()
            summary["run_id"] = self.run_id
            summary["final_status"] = final.value
            atomic_write_json(self.out_dir / "summary.json", summary)
        except Exception:  # noqa: BLE001
            pass
        for fh in (self._csv_fh, self._jsonl_fh, self._phase_fh, self._signal_fh, self._events_fh):
            try:
                if fh:
                    fh.close()
            except Exception:  # noqa: BLE001
                pass
        self._events_fh = None
        try:
            meta_path = self.out_dir / "run_metadata.json"
            data = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else self.metadata()
            data["final_status"] = final.value
            data["completed_at"] = datetime.now(timezone.utc).isoformat()
            data["sim_time_sec"] = round(self.sim.time_sec, 3)
            data["controller_mode_final"] = self.sim.controller_mode
            data["controller_mode_switches"] = self.sim.controller_mode_switches
            if summary:
                data["safety"] = summary["safety"]
                data["trajectory_digest"] = summary["trajectory_digest"]
            if self.error_message:
                data["error_message"] = self.error_message
            atomic_write_json(meta_path, data)
        except Exception:  # noqa: BLE001
            pass
