"""Фоновый worker одного задания анализа видео.

Один активный worker в один момент времени (см. manager.py). Каждое задание
получает свой run_id и папку output/<run_id>/. Пауза останавливает цикл
обработки кадров — время видео не продвигается, поэтому ожидание машин не
растёт во время паузы и не зависит от скорости CPU.
"""
from __future__ import annotations

import csv
import json
import subprocess
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import cv2

from app.core.lane_engine import AnalyticsEngine, Detection
from app.core.render import DEFAULT_RENDER_OPTIONS, draw_dynamic_layers, draw_static_layers
from app.core.storage import atomic_write_json, run_dir
from app.models.job import JobStatus, RunMetadata
from app.models.profile import Profile
from app.workers.model_registry import DEVICE, get_model

HISTORY_EMIT_INTERVAL_SEC = 1.0
CSV_COLUMNS = [
    "timestamp_sec", "run_id", "lane_id", "lane_name", "vehicles", "queued",
    "queue_truncated_by_frame", "avg_wait_sec", "max_wait_sec", "wait_sample_size",
    "flow_count_window", "flow_window_available_sec", "flow_window_target_sec",
    "total_crossings", "composition_car", "composition_bus", "composition_truck",
    "composition_motorcycle",
]


class JobWorker:
    def __init__(self, run_id: str, profile: Profile, video_path: Path):
        self.run_id = run_id
        self.profile = profile
        self.video_path = video_path
        self.out_dir = run_dir(run_id)

        self.status = JobStatus.queued
        self.error_message: str | None = None
        self.model_ready = False

        self._run_event = threading.Event()
        self._run_event.set()
        self._stop_flag = threading.Event()
        self._lock = threading.RLock()

        self.render_options = dict(DEFAULT_RENDER_OPTIONS)
        self._latest_jpeg: bytes | None = None

        self.frames_processed = 0
        self.frames_total = 0
        self.video_time_sec = 0.0
        self.processing_fps = 0.0
        self._fps_window: deque = deque(maxlen=30)
        self.started_at: datetime | None = None

        self._thread: threading.Thread | None = None
        self._csv_fh = None
        self._csv_writer = None
        self._jsonl_fh = None

    # --- управление ---

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        with self._lock:
            if self.status == JobStatus.running:
                self._run_event.clear()
                self.status = JobStatus.paused

    def resume(self) -> None:
        with self._lock:
            if self.status == JobStatus.paused:
                self._run_event.set()
                self.status = JobStatus.running

    def stop(self) -> None:
        self._stop_flag.set()
        self._run_event.set()  # разбудить, если на паузе

    def set_render_options(self, options: dict) -> None:
        with self._lock:
            self.render_options.update(options)

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    def progress(self) -> dict:
        with self._lock:
            return {
                "run_id": self.run_id,
                "video_id": self.video_path.parent.name,
                "profile_id": self.profile.profile_id,
                "status": self.status.value,
                "video_time_sec": round(self.video_time_sec, 2),
                "source_duration_sec": self.profile.source_video.duration_sec,
                "frames_processed": self.frames_processed,
                "frames_total": self.frames_total,
                "processing_fps": round(self.processing_fps, 2),
                "source_fps": self.profile.source_video.fps,
                "realtime_ratio": round(
                    self.processing_fps / self.profile.source_video.fps, 3
                )
                if self.profile.source_video.fps and self.processing_fps
                else 0.0,
                "started_at": self.started_at,
                "error_message": self.error_message,
                "model_ready": self.model_ready,
            }

    # --- основной цикл ---

    def _run(self) -> None:
        try:
            self._run_impl()
        except Exception as exc:  # noqa: BLE001
            self.status = JobStatus.error
            self.error_message = f"{exc}\n{traceback.format_exc(limit=5)}"
        finally:
            self._finalize()

    def _run_impl(self) -> None:
        profile = self.profile
        class_name_to_id = {v: k for k, v in get_model(profile.analysis_params.model_name).names.items()}
        class_ids = [class_name_to_id[c] for c in profile.analysis_params.classes if c in class_name_to_id]

        model = get_model(profile.analysis_params.model_name)
        self.model_ready = True

        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Не удалось открыть видео: {self.video_path}")

        src_fps = cap.get(cv2.CAP_PROP_FPS) or profile.source_video.fps
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or profile.source_video.width
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or profile.source_video.height
        self.frames_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        engine = AnalyticsEngine(profile, w, h)
        self.engine = engine

        self._raw_video_path = self.out_dir / "_raw_annotated.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(self._raw_video_path), fourcc, src_fps, (w, h))

        self._open_export_files()
        self._write_static_exports()

        self.status = JobStatus.running
        self.started_at = datetime.now(timezone.utc)
        last_emit_time = -1e9
        frame_idx = 0

        while True:
            if self._stop_flag.is_set():
                break
            self._run_event.wait(timeout=0.2)
            if self._stop_flag.is_set():
                continue
            if not self._run_event.is_set():
                continue  # всё ещё на паузе

            ok, frame = cap.read()
            if not ok:
                break  # конец видео — обработка завершена естественным образом

            t_wall0 = time.time()
            video_time = frame_idx / src_fps

            results = model.track(
                frame,
                classes=class_ids,
                conf=profile.analysis_params.conf_threshold,
                iou=profile.analysis_params.iou_threshold,
                tracker="bytetrack.yaml",
                persist=True,
                verbose=False,
                device=DEVICE,
            )
            detections = self._extract_detections(results, model.names)
            engine.update(video_time, detections)

            annotated = frame.copy()
            with self._lock:
                opts = dict(self.render_options)
            draw_static_layers(annotated, profile, opts)
            draw_dynamic_layers(annotated, detections, engine, opts)
            writer.write(annotated)

            ok2, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok2:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()

            if video_time - last_emit_time >= HISTORY_EMIT_INTERVAL_SEC or frame_idx == 0:
                self._emit_history(engine.snapshot(video_time))
                last_emit_time = video_time

            frame_idx += 1
            self.frames_processed = frame_idx
            self.video_time_sec = video_time
            dt = time.time() - t_wall0
            self._fps_window.append(dt)
            if self._fps_window:
                mean_dt = sum(self._fps_window) / len(self._fps_window)
                self.processing_fps = 1.0 / mean_dt if mean_dt > 0 else 0.0

        cap.release()
        writer.release()
        self._transcode_to_h264()

        if self._stop_flag.is_set():
            self.status = JobStatus.stopped
        else:
            self.status = JobStatus.completed
            # финальный снимок на конец ролика
            self._emit_history(engine.snapshot(self.video_time_sec))

    def _transcode_to_h264(self) -> None:
        """cv2.VideoWriter (mp4v) пишет MPEG-4 Part 2, который не проигрывается
        в браузерах. Перекодируем в H.264 (+ faststart для сразу проигрываемого
        файла), чтобы экспортированное видео открывалось нативным <video>."""
        final_path = self.out_dir / "annotated_video.mp4"
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(self._raw_video_path),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(final_path),
                ],
                check=True, capture_output=True, timeout=600,
            )
            self._raw_video_path.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            # Не роняем задание из-за транскодирования — отдаём исходный файл
            # и явно отмечаем ограничение в метаданных запуска.
            self._raw_video_path.replace(final_path)
            self.error_message = (
                (self.error_message + "; " if self.error_message else "")
                + f"Перекодирование в H.264 не выполнено, экспорт в исходном кодеке: {exc}"
            )

    def _extract_detections(self, results, names) -> list[Detection]:
        out = []
        r = results[0] if isinstance(results, list) else results
        if r.boxes is None or r.boxes.id is None:
            return out
        ids = r.boxes.id.tolist()
        clss = r.boxes.cls.tolist()
        confs = r.boxes.conf.tolist()
        xyxy = r.boxes.xyxy.tolist()
        for tid, c, conf, box in zip(ids, clss, confs, xyxy):
            out.append(
                Detection(
                    track_id=int(tid),
                    cls=names[int(c)],
                    conf=float(conf),
                    bbox=tuple(box),
                )
            )
        return out

    # --- экспорт ---

    def _open_export_files(self) -> None:
        self._csv_fh = open(self.out_dir / "traffic_metrics.csv", "w", newline="", encoding="utf-8")
        self._csv_writer = csv.DictWriter(self._csv_fh, fieldnames=CSV_COLUMNS)
        self._csv_writer.writeheader()
        self._jsonl_fh = open(self.out_dir / "traffic_history.jsonl", "a", encoding="utf-8")

    def _write_static_exports(self) -> None:
        atomic_write_json(
            self.out_dir / "profile.json", json.loads(self.profile.model_dump_json())
        )
        meta = RunMetadata(
            run_id=self.run_id,
            profile_id=self.profile.profile_id,
            profile_name=self.profile.name,
            video_id=self.video_path.parent.name,
            video_filename=self.profile.source_video.filename,
            model_name=self.profile.analysis_params.model_name,
            source_fps=self.profile.source_video.fps,
            source_width=self.profile.source_video.width,
            source_height=self.profile.source_video.height,
            source_duration_sec=self.profile.source_video.duration_sec,
            device=DEVICE,
        )
        atomic_write_json(self.out_dir / "run_metadata.json", json.loads(meta.model_dump_json()))

    def _emit_history(self, snapshot: dict) -> None:
        snapshot = dict(snapshot)
        snapshot["run_id"] = self.run_id
        snapshot["profile_id"] = self.profile.profile_id
        snapshot["window_duration_sec"] = HISTORY_EMIT_INTERVAL_SEC

        atomic_write_json(self.out_dir / "traffic_state.json", snapshot)

        self._jsonl_fh.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
        self._jsonl_fh.flush()

        for lane in snapshot["lanes"]:
            comp = lane["vehicle_types"]
            self._csv_writer.writerow(
                {
                    "timestamp_sec": snapshot["timestamp_sec"],
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
                }
            )
        self._csv_fh.flush()

    def _finalize(self) -> None:
        try:
            if self._csv_fh:
                self._csv_fh.close()
            if self._jsonl_fh:
                self._jsonl_fh.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            meta_path = self.out_dir / "run_metadata.json"
            if meta_path.exists():
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                data["final_status"] = self.status.value
                data["completed_at"] = datetime.now(timezone.utc).isoformat()
                data["frames_processed"] = self.frames_processed
                if self.error_message:
                    data["error_message"] = self.error_message
                atomic_write_json(meta_path, data)
        except Exception:  # noqa: BLE001
            pass
