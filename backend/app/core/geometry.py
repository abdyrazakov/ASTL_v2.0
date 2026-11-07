"""Геометрические примитивы для подсчёта пересечений линии и привязки к полосам.

Все функции работают в пиксельных координатах конкретного кадра (после
денормализации профиля под фактическое разрешение видео).
"""
from __future__ import annotations

from dataclasses import dataclass

Vec2 = tuple[float, float]


def _ccw(p: Vec2, q: Vec2, r: Vec2) -> float:
    return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])


def segments_intersect(a1: Vec2, a2: Vec2, b1: Vec2, b2: Vec2) -> bool:
    """True, если отрезок a1-a2 пересекает отрезок b1-b2 (включая вырожденные касания)."""
    d1 = _ccw(b1, b2, a1)
    d2 = _ccw(b1, b2, a2)
    d3 = _ccw(a1, a2, b1)
    d4 = _ccw(a1, a2, b2)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True
    # Коллинеарные / граничные случаи не считаем валидным пересечением —
    # для линии подсчёта это means "прошёл точно по линии", крайне редко,
    # и трактуется как отсутствие строгого пересечения на этом кадре.
    return False


def line_side_sign(p1: Vec2, p2: Vec2, point: Vec2) -> float:
    """Знак векторного произведения (p2-p1) x (point-p1)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return dx * (point[1] - p1[1]) - dy * (point[0] - p1[0])


@dataclass(frozen=True)
class CountLinePx:
    """Линия подсчёта в пиксельных координатах с заданной положительной стороной."""

    p1: Vec2
    p2: Vec2
    positive_sign: float  # знак line_side_sign(p1, p2, positive_side_point)
    direction: str  # "positive" | "negative" | "both"

    def crossing_direction(self, prev: Vec2, curr: Vec2) -> str | None:
        """Возвращает 'positive', 'negative' или None, если нет валидного пересечения
        именно отрезка [prev, curr] с отрезком линии подсчёта [p1, p2]."""
        if not segments_intersect(prev, curr, self.p1, self.p2):
            return None
        prev_side = line_side_sign(self.p1, self.p2, prev)
        curr_side = line_side_sign(self.p1, self.p2, curr)
        if prev_side == 0 or curr_side == 0:
            return None
        prev_positive = (prev_side > 0) == (self.positive_sign > 0)
        curr_positive = (curr_side > 0) == (self.positive_sign > 0)
        if prev_positive == curr_positive:
            return None
        return "positive" if curr_positive else "negative"

    def counts(self, prev: Vec2, curr: Vec2) -> bool:
        d = self.crossing_direction(prev, curr)
        if d is None:
            return False
        if self.direction == "both":
            return True
        return d == self.direction
