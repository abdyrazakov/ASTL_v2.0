"""Ленивая загрузка и кэш модели YOLO. Устройство выбирается автоматически:
CUDA, если доступна, иначе CPU (работа на CPU обязательна)."""
from __future__ import annotations

import threading

import torch
from ultralytics import YOLO

_lock = threading.Lock()
_models: dict[str, YOLO] = {}

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def get_model(model_name: str) -> YOLO:
    with _lock:
        if model_name not in _models:
            model = YOLO(model_name)
            _models[model_name] = model
        return _models[model_name]
