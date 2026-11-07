"""Пути хранения данных приложения и атомарная запись JSON."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

DATA_DIR = BACKEND_DIR / "data"
VIDEOS_DIR = DATA_DIR / "videos"
PROFILES_DIR = DATA_DIR / "profiles"
OUTPUT_DIR = PROJECT_ROOT / "output"

for d in (VIDEOS_DIR, PROFILES_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, data: dict) -> None:
    """Атомарная запись JSON: пишем во временный файл в той же директории и
    переименовываем, чтобы читатели никогда не видели частично записанный файл."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def run_dir(run_id: str) -> Path:
    d = OUTPUT_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d
