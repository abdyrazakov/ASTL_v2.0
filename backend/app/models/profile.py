"""Схема профиля перекрёстка (разметка полос).

Координаты полигонов и линий хранятся НОРМАЛИЗОВАННЫМИ относительно исходного
разрешения видео (0..1 по x и y), чтобы разметка не "ехала" при изменении
размера окна редактора или при открытии видео другого разрешения с тем же
соотношением сторон.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"

VEHICLE_CLASSES = ["car", "bus", "truck", "motorcycle"]


class ReferencePointMode(str, Enum):
    bottom_center = "bottom_center"
    bottom_left = "bottom_left"
    bottom_right = "bottom_right"
    center = "center"


class CountDirection(str, Enum):
    """Направление допустимого пересечения линии подсчёта.

    Линия задаётся двумя точками p1->p2. Нормаль (positive_side_point)
    однозначно определяет, какая сторона линии считается "положительной":
    знак векторного произведения (p2-p1) x (point-p1) в точке
    positive_side_point задаёт положительный знак.

    - positive: считается переход с отрицательной стороны на положительную
    - negative: считается переход с положительной стороны на отрицательную
    - both: считаются оба направления (раздельно не различаются)
    """

    positive = "positive"
    negative = "negative"
    both = "both"


class Point(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


class CountLine(BaseModel):
    p1: Point
    p2: Point
    # Любая точка не на линии — задаёт "положительную" сторону нормали.
    positive_side_point: Point
    direction: CountDirection = CountDirection.positive

    @model_validator(mode="after")
    def _check_nonzero_length(self):
        dx = self.p2.x - self.p1.x
        dy = self.p2.y - self.p1.y
        if (dx * dx + dy * dy) ** 0.5 < 1e-6:
            raise ValueError("Линия подсчёта имеет нулевую длину")
        # positive_side_point не должна лежать на самой линии
        cross = dx * (self.positive_side_point.y - self.p1.y) - dy * (
            self.positive_side_point.x - self.p1.x
        )
        if abs(cross) < 1e-9:
            raise ValueError(
                "Точка направления лежит на линии подсчёта — направление не определено"
            )
        return self


def _polygon_self_intersects(points: list[tuple[float, float]]) -> bool:
    """Проверка простого многоугольника на самопересечение рёбер (не считая соседних)."""

    def seg_intersect(a1, a2, b1, b2) -> bool:
        def ccw(p, q, r):
            return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])

        d1 = ccw(b1, b2, a1)
        d2 = ccw(b1, b2, a2)
        d3 = ccw(a1, a2, b1)
        d4 = ccw(a1, a2, b2)
        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
            (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
        ):
            return True
        return False

    n = len(points)
    if n < 4:
        return False
    edges = [(points[i], points[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if abs(i - j) in (0, 1, n - 1):
                continue  # соседние или совпадающие рёбра не считаем
            if seg_intersect(*edges[i], *edges[j]):
                return True
    return False


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


class Polygon(BaseModel):
    points: list[Point] = Field(min_length=3)

    @field_validator("points")
    @classmethod
    def _check_simple(cls, points: list[Point]) -> list[Point]:
        coords = [p.as_tuple() for p in points]
        if _polygon_self_intersects(coords):
            raise ValueError("Полигон имеет самопересекающиеся рёбра")
        return points

    def contains(self, point: tuple[float, float]) -> bool:
        return _point_in_polygon(point, [p.as_tuple() for p in self.points])

    def centroid(self) -> tuple[float, float]:
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def touches_frame_border(self, epsilon: float = 0.01) -> bool:
        for p in self.points:
            if p.x <= epsilon or p.x >= 1 - epsilon or p.y <= epsilon or p.y >= 1 - epsilon:
                return True
        return False


class Lane(BaseModel):
    id: str = Field(default_factory=lambda: f"lane_{uuid4().hex[:8]}")
    name: str
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    observation_polygon: Polygon
    queue_zone_polygon: Polygon
    count_line: CountLine
    reference_point_mode: ReferencePointMode | None = None  # override профиля

    @model_validator(mode="after")
    def _queue_inside_observation(self):
        # Практическая проверка: центроид и все вершины зоны очереди должны
        # преимущественно лежать внутри полигона наблюдения полосы.
        obs = self.observation_polygon
        outside = sum(
            1 for p in self.queue_zone_polygon.points if not obs.contains(p.as_tuple())
        )
        if outside > 0:
            raise ValueError(
                f"Зона очереди полосы '{self.name}' выходит за пределы полигона "
                f"наблюдения ({outside} вершин снаружи)"
            )
        return self


class AnalysisParams(BaseModel):
    model_name: str = "yolo11n.pt"
    conf_threshold: float = 0.35
    iou_threshold: float = 0.5
    classes: list[str] = Field(default_factory=lambda: list(VEHICLE_CLASSES))

    # Стабилизация привязки к полосе
    lane_switch_hysteresis_sec: float = 0.5

    # Удержание потерянного трека (устойчивость к кратким перекрытиям)
    track_lost_grace_sec: float = 1.0

    # Окно сглаживания скорости — ВРЕМЯ (секунды видео), а не число кадров.
    # Это принципиально: дрожание рамки детектора в несколько пикселей неизбежно
    # даже у неподвижной машины. На коротком окне (доли секунды) это дрожание,
    # делённое на крошечный интервал времени, превращается в огромную ложную
    # скорость — именно поэтому окно должно быть измерено в секундах реального
    # времени видео, а не в кадрах (при 60 к/с 5 кадров — это ~0.08 с, этого
    # недостаточно для сглаживания шума детектора).
    speed_window_sec: float = 0.8
    stop_enter_speed: float = 0.08  # норм. скорость (высот bbox/сек), ниже = "стоит"
    stop_duration_threshold_sec: float = 2.0
    stop_exit_speed: float = 0.20  # выше = считается "поехал" (гистерезис)
    queue_exit_duration_sec: float = 1.0

    # Окно потока
    flow_window_sec: float = 60.0

    # Защита от повторного счёта на линии
    crossing_cooldown_sec: float = 0.5


class SourceVideoInfo(BaseModel):
    filename: str
    width: int
    height: int
    fps: float
    duration_sec: float


class Profile(BaseModel):
    schema_version: str = SCHEMA_VERSION
    profile_id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    status: Literal["preliminary", "verified"] = "preliminary"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_video: SourceVideoInfo
    reference_point_mode: ReferencePointMode = ReferencePointMode.bottom_center
    lanes: list[Lane] = Field(default_factory=list)
    analysis_params: AnalysisParams = Field(default_factory=AnalysisParams)
    notes: str = ""

    @field_validator("lanes")
    @classmethod
    def _unique_lane_ids(cls, lanes: list[Lane]) -> list[Lane]:
        ids = [lane.id for lane in lanes]
        if len(ids) != len(set(ids)):
            raise ValueError("ID полос должны быть уникальны в пределах профиля")
        names = [lane.name for lane in lanes]
        if len(names) != len(set(names)):
            raise ValueError("Названия полос должны быть уникальны в пределах профиля")
        return lanes
