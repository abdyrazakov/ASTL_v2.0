"""Схема профиля перекрёстка этапа 2 (логика сигналов, а не разметка видео).

Не путать с `app.models.profile.Profile` этапа 1: тот описывает полигоны полос
на кадре видео, этот — подходы, полосы, сигнальные группы, матрицу конфликтов,
фазы, тайминги и параметры генератора трафика. Это разные сущности, поэтому и
схема отдельная (`kind = "intersection"`, `schema_version = "2.0"`).

Все длительности квантуются шагом модели `SIM_DT` (0.1 с): автомат сигналов
считает время в целых тиках, поэтому тайминги соблюдаются точно, без накопления
ошибки плавающей точки. Значения, не кратные 0.1 с, округляются при валидации.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.profile import VEHICLE_CLASSES  # классы транспорта этапа 1

INTERSECTION_SCHEMA_VERSION = "2.0"
SIM_DT = 0.1  # шаг модельного времени, с


def _q(value: float) -> float:
    """Квантование длительности к шагу модели."""
    return round(round(value / SIM_DT) * SIM_DT, 3)


class Heading(str, Enum):
    """Сторона, С КОТОРОЙ приходит транспорт подхода (N = едут с севера на юг)."""

    N = "N"
    E = "E"
    S = "S"
    W = "W"


class Movement(str, Enum):
    straight = "straight"
    left = "left"
    right = "right"


class Approach(BaseModel):
    id: str
    name: str
    heading: Heading


class SimLane(BaseModel):
    id: str
    approach_id: str
    # 0 — полоса у осевой (самая левая для водителя), далее вправо к обочине.
    index: int = Field(ge=0, le=5)
    name: str
    color: str = Field(default="#2dd4bf", pattern=r"^#[0-9a-fA-F]{6}$")
    movements: list[Movement] = Field(min_length=1)
    length_m: float = Field(default=150.0, ge=30.0, le=1000.0)
    speed_limit_mps: float = Field(default=13.9, gt=1.0, le=40.0)
    arrival_rate_vph: float = Field(default=300.0, ge=0.0, le=3000.0)

    @field_validator("movements")
    @classmethod
    def _unique_movements(cls, v: list[Movement]) -> list[Movement]:
        if len(v) != len(set(v)):
            raise ValueError("манёвры полосы повторяются")
        return v


class LaneMovement(BaseModel):
    lane_id: str
    movement: Movement


class SignalGroup(BaseModel):
    id: str
    name: str
    movements: list[LaneMovement] = Field(min_length=1)


class Phase(BaseModel):
    id: str
    name: str
    signal_groups: list[str] = Field(min_length=1)
    # Длительность зелёного в фиксированном цикле. Обязана лежать в [min, max].
    fixed_green_sec: float = Field(default=20.0, gt=0)
    # Переопределения глобальных таймингов для этой фазы (None — берётся глобальное).
    min_green_sec: float | None = Field(default=None, gt=0)
    max_green_sec: float | None = Field(default=None, gt=0)

    @field_validator("fixed_green_sec", "min_green_sec", "max_green_sec")
    @classmethod
    def _quant(cls, v):
        return None if v is None else _q(v)


class Timings(BaseModel):
    min_green_sec: float = Field(default=7.0, gt=0)
    max_green_sec: float = Field(default=45.0, gt=0)
    # ≥ 3 с: машина, которая на жёлтом уже не может остановиться (≤ v²/2b до линии),
    # успевает её проехать — для всех классов v/(2b) < 2.5 с (см. engine.VEHICLE_SPECS).
    yellow_sec: float = Field(default=3.0, ge=3.0, le=8.0)
    all_red_clearance_sec: float = Field(default=2.0, gt=0, le=10.0)
    startup_all_red_sec: float = Field(default=3.0, gt=0, le=30.0)
    gap_out_sec: float = Field(default=3.0, gt=0, le=20.0)
    max_red_wait_sec: float = Field(default=90.0, gt=0, le=600.0)
    # Виртуальный детектор адаптивного режима: столько метров до стоп-линии.
    detector_distance_m: float = Field(default=30.0, ge=5.0, le=200.0)

    @field_validator(
        "min_green_sec", "max_green_sec", "yellow_sec", "all_red_clearance_sec",
        "startup_all_red_sec", "gap_out_sec", "max_red_wait_sec",
    )
    @classmethod
    def _quant(cls, v: float) -> float:
        return _q(v)


class ScenarioSegment(BaseModel):
    """Множитель интенсивности на интервале модельного времени.

    Например, `{start_sec: 600, end_sec: 1200, lane_ids: ["n1"], multiplier: 3}` —
    тройной поток на полосе n1 с 10-й по 20-ю минуту. Пустой `lane_ids` = все полосы.
    Перекрывающиеся сегменты перемножаются.
    """

    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    lane_ids: list[str] = Field(default_factory=list)
    multiplier: float = Field(ge=0.0, le=20.0)
    label: str = ""

    @model_validator(mode="after")
    def _order(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("сегмент сценария: end_sec должен быть больше start_sec")
        return self


class TrafficParams(BaseModel):
    # Доли классов (нормируются при генерации). Классы — те же, что в этапе 1.
    composition: dict[str, float] = Field(
        default_factory=lambda: {"car": 0.85, "bus": 0.04, "truck": 0.06, "motorcycle": 0.05}
    )
    seed: int = 42
    min_gap_m: float = Field(default=2.0, ge=0.5, le=10.0)
    scenario: list[ScenarioSegment] = Field(default_factory=list)
    scenario_name: str = ""

    @field_validator("composition")
    @classmethod
    def _check_comp(cls, v: dict[str, float]) -> dict[str, float]:
        unknown = [k for k in v if k not in VEHICLE_CLASSES]
        if unknown:
            raise ValueError(f"неизвестные классы транспорта: {unknown}; допустимы {VEHICLE_CLASSES}")
        if any(x < 0 for x in v.values()):
            raise ValueError("доли классов не могут быть отрицательными")
        if sum(v.values()) <= 0:
            raise ValueError("сумма долей классов транспорта должна быть больше нуля")
        return v


class AdaptiveParams(BaseModel):
    # Вес ожидания в формуле спроса фазы: D = Σ (1 + w · wait_sec).
    # 0.1 означает: машина, ждущая 10 с, весит как две только что вставшие.
    wait_weight_per_sec: float = Field(default=0.1, ge=0.0, le=10.0)
    # Правило «очистка очереди»: после min_green зелёный уступает, когда у активной
    # фазы не осталось машин в очереди, а спрос D другой фазы достиг этого порога.
    # None — правило выключено (остаются только gap-out и max_green).
    queue_clear_min_demand: float | None = Field(default=2.0, gt=0.0, le=50.0)


class IntersectionProfile(BaseModel):
    schema_version: str = INTERSECTION_SCHEMA_VERSION
    kind: Literal["intersection"] = "intersection"
    profile_id: str = Field(default_factory=lambda: uuid4().hex)
    name: str = Field(min_length=1)
    template: str = "custom"
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    approaches: list[Approach] = Field(min_length=1)
    lanes: list[SimLane] = Field(min_length=1)
    signal_groups: list[SignalGroup] = Field(min_length=1)
    # Матрица конфликтов в виде списков смежности: group_id -> конфликтующие group_id.
    # Обязана быть симметричной (проверяется), группа не конфликтует сама с собой.
    conflicts: dict[str, list[str]] = Field(default_factory=dict)
    phases: list[Phase] = Field(min_length=1)
    # Циклический порядок фаз: по нему работает фиксированный контроллер,
    # и он же — допустимые переходы по умолчанию.
    phase_order: list[str] = Field(min_length=1)
    # Явно допустимые переходы phase_id -> [phase_id]. None — из любой фазы в любую.
    transitions: dict[str, list[str]] | None = None
    timings: Timings = Field(default_factory=Timings)
    traffic: TrafficParams = Field(default_factory=TrafficParams)
    adaptive: AdaptiveParams = Field(default_factory=AdaptiveParams)

    @model_validator(mode="after")
    def _validate_semantics(self):
        errors, _ = check_profile(self)
        if errors:
            raise ValueError("; ".join(errors))
        return self

    # --- удобные запросы ---

    def lane(self, lane_id: str) -> SimLane:
        return next(lane for lane in self.lanes if lane.id == lane_id)

    def approach_of(self, lane: SimLane) -> Approach:
        return next(a for a in self.approaches if a.id == lane.approach_id)

    def phase(self, phase_id: str) -> Phase:
        return next(p for p in self.phases if p.id == phase_id)

    def min_green(self, phase_id: str) -> float:
        p = self.phase(phase_id)
        return p.min_green_sec if p.min_green_sec is not None else self.timings.min_green_sec

    def max_green(self, phase_id: str) -> float:
        p = self.phase(phase_id)
        return p.max_green_sec if p.max_green_sec is not None else self.timings.max_green_sec

    def movement_group(self) -> dict[tuple[str, str], str]:
        """(lane_id, movement) -> id сигнальной группы."""
        out: dict[tuple[str, str], str] = {}
        for g in self.signal_groups:
            for lm in g.movements:
                out[(lm.lane_id, lm.movement.value)] = g.id
        return out

    def conflict_pairs(self) -> set[frozenset[str]]:
        return {frozenset((a, b)) for a, bs in self.conflicts.items() for b in bs if a != b}

    def allowed_next(self, phase_id: str) -> list[str]:
        if self.transitions is None:
            return [p for p in self.phase_order if p != phase_id]
        return [p for p in self.transitions.get(phase_id, []) if p != phase_id]

    def cycle_next(self, phase_id: str) -> str:
        order = self.phase_order
        return order[(order.index(phase_id) + 1) % len(order)]


def check_profile(p: IntersectionProfile) -> tuple[list[str], list[str]]:
    """Семантическая проверка профиля. Возвращает (ошибки, предупреждения).

    Ошибки блокируют сохранение и запуск: заведомо сломанный сценарий (например,
    полоса с трафиком, которую не обслуживает ни одна фаза, — машины копились бы
    вечно) не должен запускаться молча.
    """
    errors: list[str] = []
    warnings: list[str] = []

    def dupes(ids: list[str]) -> list[str]:
        seen, out = set(), []
        for i in ids:
            if i in seen and i not in out:
                out.append(i)
            seen.add(i)
        return out

    approach_ids = {a.id for a in p.approaches}
    lane_ids = {lane.id for lane in p.lanes}
    group_ids = {g.id for g in p.signal_groups}
    phase_ids = {ph.id for ph in p.phases}

    for label, ids in (
        ("подходов", [a.id for a in p.approaches]),
        ("полос", [lane.id for lane in p.lanes]),
        ("сигнальных групп", [g.id for g in p.signal_groups]),
        ("фаз", [ph.id for ph in p.phases]),
    ):
        d = dupes(ids)
        if d:
            errors.append(f"повторяющиеся ID {label}: {d}")

    headings = [a.heading for a in p.approaches]
    if len(headings) != len(set(headings)):
        errors.append("два подхода не могут приходить с одной стороны (heading)")

    # --- полосы ---
    for lane in p.lanes:
        if lane.approach_id not in approach_ids:
            errors.append(f"полоса {lane.id}: неизвестный подход {lane.approach_id}")
    for a in p.approaches:
        idx = [lane.index for lane in p.lanes if lane.approach_id == a.id]
        if len(idx) != len(set(idx)):
            errors.append(f"подход {a.id}: номера полос (index) повторяются")
        if not idx:
            warnings.append(f"у подхода {a.name} нет ни одной полосы")

    # --- сигнальные группы ---
    owner: dict[tuple[str, str], str] = {}
    lane_by_id = {lane.id: lane for lane in p.lanes}
    for g in p.signal_groups:
        for lm in g.movements:
            lane = lane_by_id.get(lm.lane_id)
            if lane is None:
                errors.append(f"группа {g.id}: неизвестная полоса {lm.lane_id}")
                continue
            if lm.movement not in lane.movements:
                errors.append(
                    f"группа {g.id}: полоса {lane.id} не разрешает манёвр {lm.movement.value}"
                )
                continue
            key = (lm.lane_id, lm.movement.value)
            if key in owner and owner[key] != g.id:
                errors.append(
                    f"манёвр {lm.movement.value} полосы {lane.id} управляется сразу двумя "
                    f"группами ({owner[key]}, {g.id}) — сигнал неоднозначен"
                )
            owner[key] = g.id

    for lane in p.lanes:
        for m in lane.movements:
            if (lane.id, m.value) not in owner:
                msg = f"манёвр {m.value} полосы {lane.name} не привязан ни к одной сигнальной группе"
                if lane.arrival_rate_vph > 0:
                    errors.append(msg + " — машины с этим манёвром никогда не проедут")
                else:
                    warnings.append(msg)

    # --- матрица конфликтов ---
    for a, bs in p.conflicts.items():
        if a not in group_ids:
            errors.append(f"матрица конфликтов: неизвестная группа {a}")
            continue
        for b in bs:
            if b not in group_ids:
                errors.append(f"матрица конфликтов: неизвестная группа {b}")
            elif b == a:
                errors.append(f"матрица конфликтов: группа {a} не может конфликтовать сама с собой")
            elif a not in p.conflicts.get(b, []):
                errors.append(
                    f"матрица конфликтов несимметрична: {a} конфликтует с {b}, но {b} не с {a}"
                )

    pairs = {frozenset((a, b)) for a, bs in p.conflicts.items() for b in bs if a != b}

    # --- фазы ---
    in_some_phase: set[str] = set()
    for ph in p.phases:
        unknown = [g for g in ph.signal_groups if g not in group_ids]
        if unknown:
            errors.append(f"фаза {ph.name}: неизвестные группы {unknown}")
        if len(ph.signal_groups) != len(set(ph.signal_groups)):
            errors.append(f"фаза {ph.name}: группы повторяются")
        gs = [g for g in ph.signal_groups if g in group_ids]
        in_some_phase.update(gs)
        for i, a in enumerate(gs):
            for b in gs[i + 1:]:
                if frozenset((a, b)) in pairs:
                    errors.append(
                        f"фаза {ph.name} содержит конфликтующие группы {a} и {b} — "
                        "такая фаза недопустима"
                    )

    for g in p.signal_groups:
        if g.id not in in_some_phase:
            errors.append(f"сигнальная группа {g.name} не входит ни в одну фазу")

    # полоса с трафиком должна обслуживаться хотя бы одной фазой по каждому манёвру
    for lane in p.lanes:
        if lane.arrival_rate_vph <= 0:
            continue
        for m in lane.movements:
            gid = owner.get((lane.id, m.value))
            if gid is not None and gid not in in_some_phase:
                errors.append(
                    f"полосу {lane.name} (манёвр {m.value}) не обслуживает ни одна фаза — "
                    "машины будут копиться бесконечно"
                )

    if len(p.phases) < 2:
        errors.append(
            "нужно минимум две фазы: с одной фазой автомату некуда переключаться "
            "(по max_green он ушёл бы в FAULT), а светофор без конфликтов не нужен"
        )

    # --- порядок фаз и переходы ---
    if sorted(p.phase_order) != sorted(phase_ids) or len(p.phase_order) != len(set(p.phase_order)):
        errors.append("порядок фаз должен содержать каждую фазу ровно один раз")

    if p.transitions is not None:
        for a, bs in p.transitions.items():
            if a not in phase_ids:
                errors.append(f"переходы: неизвестная фаза {a}")
            for b in bs:
                if b not in phase_ids:
                    errors.append(f"переходы: неизвестная фаза {b}")
        for ph in p.phases:
            nexts = [b for b in p.transitions.get(ph.id, []) if b != ph.id]
            if len(p.phases) > 1 and not nexts:
                errors.append(f"из фазы {ph.name} нет ни одного допустимого перехода")
        # циклический порядок обязан быть допустимым (на нём работает фиксированный режим)
        if not errors and len(p.phase_order) > 1:
            for i, a in enumerate(p.phase_order):
                b = p.phase_order[(i + 1) % len(p.phase_order)]
                if b not in p.transitions.get(a, []):
                    errors.append(
                        f"переход {a} → {b} из циклического порядка фаз не разрешён в списке переходов"
                    )
        if not errors and len(p.phases) > 1:
            complete = all(
                set(p.transitions.get(a, [])) >= (phase_ids - {a}) for a in phase_ids
            )
            if not complete:
                warnings.append(
                    "не все фазы достижимы напрямую друг из друга — защита от голодания "
                    "ведёт к нужной фазе по кратчайшему пути разрешённых переходов, "
                    "гарантия max_red_wait_sec ослабевает на длину этого пути"
                )

    # --- тайминги ---
    t = p.timings
    for ph in p.phases:
        mn = ph.min_green_sec if ph.min_green_sec is not None else t.min_green_sec
        mx = ph.max_green_sec if ph.max_green_sec is not None else t.max_green_sec
        if mn > mx:
            errors.append(f"фаза {ph.name}: min_green ({mn} с) больше max_green ({mx} с)")
        if not (mn <= ph.fixed_green_sec <= mx):
            errors.append(
                f"фаза {ph.name}: зелёный фиксированного цикла {ph.fixed_green_sec} с вне "
                f"диапазона [min_green {mn}; max_green {mx}]"
            )
        # Худший случай для защиты от голодания: машина встаёт в очередь в момент,
        # когда чужая фаза уходит в жёлтый, а следующей выбрана ещё одна чужая фаза:
        # жёлтый + all-red + min_green(чужой) + жёлтый + all-red до её зелёного.
        need = mn + 2 * (t.yellow_sec + t.all_red_clearance_sec)
        if t.max_red_wait_sec < need:
            errors.append(
                f"max_red_wait_sec ({t.max_red_wait_sec} с) меньше, чем min_green фазы "
                f"{ph.name} + 2×(жёлтый + all-red) = {need:.1f} с — защита от голодания "
                "не сможет гарантированно уложиться в этот срок"
            )

    # --- сценарий ---
    for seg in p.traffic.scenario:
        bad = [lid for lid in seg.lane_ids if lid not in lane_ids]
        if bad:
            errors.append(f"сценарий: неизвестные полосы {bad}")

    if not any(lane.arrival_rate_vph > 0 for lane in p.lanes):
        warnings.append("интенсивность всех полос равна нулю — машин не будет")

    return errors, warnings


def phase_path(p: IntersectionProfile, src: str, dst: str) -> list[str]:
    """Кратчайший путь по допустимым переходам src → … → dst (без src)."""
    if src == dst:
        return []
    prev: dict[str, str] = {}
    q = deque([src])
    seen = {src}
    while q:
        cur = q.popleft()
        for nxt in p.allowed_next(cur):
            if nxt in seen:
                continue
            seen.add(nxt)
            prev[nxt] = cur
            if nxt == dst:
                path = [dst]
                while prev[path[-1]] != src:
                    path.append(prev[path[-1]])
                return list(reversed(path))
            q.append(nxt)
    return []


class SimulationStartRequest(BaseModel):
    profile_id: str
    controller_mode: Literal["fixed", "adaptive"] = "adaptive"
    seed: int | None = None  # None — берётся из профиля
    duration_sec: float | None = Field(default=3600.0, gt=0, le=24 * 3600)  # None — бесконечно
    speed: float = Field(default=5.0, gt=0, le=200.0)


class CompareRequest(BaseModel):
    profile_id: str
    seed: int | None = None
    duration_sec: float = Field(default=3600.0, gt=0, le=4 * 3600)
