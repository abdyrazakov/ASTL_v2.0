"""Поиск завершённых прогонов в output/ и честное сравнение режимов.

Сравнение «фиксированный vs адаптивный» строится только из реально выполненных
прогонов с одинаковыми содержимым профиля (profile_hash), seed и длительностью,
завершённых полностью и без переключения режима посреди прогона. Если пары нет —
API так и отвечает (`available: false`), вторая цифра не придумывается.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core import storage


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def list_simulation_runs(output_dir: Path | None = None) -> list[dict]:
    output_dir = storage.OUTPUT_DIR if output_dir is None else output_dir
    runs = []
    for d in output_dir.iterdir() if output_dir.exists() else []:
        if not d.is_dir():
            continue
        meta = _read_json(d / "run_metadata.json")
        if not meta or meta.get("kind") != "simulation":
            continue
        summary = _read_json(d / "summary.json")
        runs.append({"metadata": meta, "summary": summary})
    runs.sort(key=lambda r: r["metadata"].get("created_at", ""), reverse=True)
    return runs


def _comparable(run: dict) -> bool:
    meta, summary = run["metadata"], run["summary"]
    return (
        summary is not None
        and meta.get("final_status") == "completed"
        and not meta.get("controller_mode_switches")
        and meta.get("duration_sec") is not None
    )


def find_comparison(
    profile_hash: str, seed: int, duration_sec: float | None = None, output_dir: Path | None = None
) -> dict:
    """Последняя пара (fixed, adaptive) на одном сценарии. Если duration_sec не
    задана — берётся длительность, для которой есть оба режима (самая свежая)."""
    candidates = [
        r for r in list_simulation_runs(output_dir)
        if _comparable(r)
        and r["metadata"].get("profile_hash") == profile_hash
        and r["metadata"].get("seed") == seed
        and (duration_sec is None or abs(r["metadata"]["duration_sec"] - duration_sec) < 1e-6)
    ]
    by_duration: dict[float, dict[str, dict]] = {}
    for r in candidates:  # уже отсортированы от новых к старым
        dur = r["metadata"]["duration_sec"]
        mode = r["metadata"]["controller_mode"]
        by_duration.setdefault(dur, {}).setdefault(mode, r)
    for dur, modes in by_duration.items():
        if "fixed" in modes and "adaptive" in modes:
            return {
                "available": True,
                "seed": seed,
                "profile_hash": profile_hash,
                "duration_sec": dur,
                "fixed": _brief(modes["fixed"]),
                "adaptive": _brief(modes["adaptive"]),
            }
    have = sorted({r["metadata"]["controller_mode"] for r in candidates})
    return {
        "available": False,
        "seed": seed,
        "profile_hash": profile_hash,
        "have_modes": have,
        "message": "Для сравнения запустите оба режима (фиксированный и адаптивный) на "
                   "одном сценарии: тот же профиль, seed и длительность, без переключения "
                   "режима во время прогона.",
    }


def _brief(run: dict) -> dict:
    meta, s = run["metadata"], run["summary"]
    return {
        "run_id": meta["run_id"],
        "created_at": meta.get("created_at"),
        "controller_mode": meta["controller_mode"],
        "totals": s["totals"],
        "lanes": s["lanes"],
        "phases": s["phases"],
        "safety": s["safety"],
        "trajectory_digest": s.get("trajectory_digest"),
    }
