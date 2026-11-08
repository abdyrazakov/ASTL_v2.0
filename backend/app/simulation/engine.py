"""Дискретно-временная модель одного перекрёстка: трафик, движение, аналитика.

Шаг модели dt = 0.1 с. Единственный источник времени — номер тика: пауза
worker'а просто не вызывает `step()`, поэтому модельное время, ожидание и
задержка во время паузы не растут (как время видео в этапе 1).

ПОРЯДОК ОДНОГО ТИКА
 1. Прибытия: пуассоновские потоки по полосам до момента t+dt → очередь въезда.
 2. Спрос (`DemandView`) по текущему состоянию → шаг автомата сигналов.
 3. Движение машин каждой полосы (от головы к хвосту) под новые сигналы.
 4. Въезд новых машин из очереди въезда, если у начала полосы есть место.
 5. Переходы состояния очереди, пересечения стоп-линии, выезд из перекрёстка.

ТРАФИК
- Прибытия по каждой полосе — независимый пуассоновский поток (экспоненциальные
  интервалы) со средней интенсивностью `arrival_rate_vph`. Сценарий умножает
  интенсивность на интервалах времени; неоднородный поток строится прореживанием
  (thinning).
- У каждой полосы СВОЙ генератор `random.Random(f"{seed}|{lane_id}")`, и он
  используется только для прибытий (время, класс, манёвр). Поэтому при одном seed
  последовательность прибытий одинакова в фиксированном и адаптивном режимах —
  сравнение честное: отличается только управление.

КИНЕМАТИКА (упрощённая, не car-following модель вроде IDM)
Машина — точка на одномерной полосе (позиция переднего бампера, м от начала
участка; стоп-линия на `length_m`). На каждом тике ищется ближайшее препятствие:
задний бампер впереди идущей машины минус `min_gap_m`, и стоп-линия, если сигнал
её группы красный (или жёлтый, а машина успевает остановиться). Скорость:

    v' = min(v + a·dt, v_max, sqrt(2·b·d), d/dt),  d — расстояние до препятствия

То есть машина разгоняется с постоянным ускорением, едет с v_max и тормозит так,
чтобы остановиться у препятствия; столкновение и проезд стоп-линии на красный
невозможны по построению (последнее ещё и страхуется явной проверкой,
`red_clamps` — счётчик срабатываний страховки, в норме 0).
Жёлтый: машина останавливается, если расстояние до линии ≥ v²/(2b), иначе
проезжает (при жёлтом ≥ 3 с успевает до красного).
Внутри перекрёстка машины не взаимодействуют друг с другом (конфликты исключает
сигнальная логика) и удаляются, проехав условный путь манёвра.

СОСТОЯНИЕ ОЧЕРЕДИ: moving → waiting → moving
- moving → waiting: скорость < STOP_SPEED (0.5 м/с) И машина в очереди у
  стоп-линии: до линии ≤ 1 м, ИЛИ впереди идущая машина (ещё не проехавшая
  линию) сама в состоянии waiting и зазор до неё ≤ min_gap + 1 м. Порога
  длительности нет: данные модели точные, шума детектора нет.
- waiting → moving: скорость ≥ MOVE_SPEED (1.0 м/с; гистерезис против дребезга
  на ползущей очереди).
- Эпизод очереди (`queue_join_time`) начинается с ПЕРВОГО перехода в waiting и
  заканчивается только проездом стоп-линии: подползание в очереди не обнуляет
  ожидание (как в этапе 1). Каждый переход moving → waiting — одна остановка.
- Машина, не поместившаяся на участок (очередь въезда, `entry_backlog`), считается
  стоящей в очереди с момента своего прибытия.

ПОКАЗАТЕЛИ ПО ПОЛОСЕ (имена полей этапа 1 + новые поля этапа 2)
- vehicles — машин на участке полосы, ещё не проехавших стоп-линию.
- queued — из них в состоянии waiting (стоят в очереди).
- avg_wait_sec / max_wait_sec / wait_sample_size — по машинам, которые сейчас в
  эпизоде очереди (встали и ещё не проехали стоп-линию, включая очередь въезда):
  время от начала эпизода до текущего момента. В отличие от этапа 1 это ПОЛНОЕ
  ожидание: начало жизни машины в модели известно точно.
- flow_count_window / flow_window_available_sec / flow_window_target_sec —
  проезды стоп-линии за последние 60 с модельного времени (и реально доступное окно).
- total_crossings — проезды стоп-линии за прогон.
- vehicle_types — состав по классам среди всех машин, когда-либо прибывших на полосу.
- queue_truncated_by_frame — всегда False: кадра в симуляции нет. Аналог —
  новое поле queue_spillback (очередь вышла за начало моделируемого участка).
Новые (агрегаты по ВЫБЫВШИМ машинам — уже проехавшим стоп-линию этой полосы):
- avg_delay_sec — средняя задержка: (момент проезда стоп-линии − момент прибытия)
  − время проезда участка от въезда до стоп-линии со свободной скоростью
  min(v_max класса, лимит полосы). Включает торможение, стояние, разгон и
  ожидание в очереди въезда.
- stops_per_vehicle — среднее число остановок (переходов в waiting) на машину.
- departed_count — число выбывших машин (размер выборки для двух полей выше).
- throughput_per_hour — пропускная способность за скользящее окно:
  flow_count_window · 3600 / flow_window_available_sec, машин/ч.
"""
from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, deque
from dataclasses import dataclass, field

from app.models.profile import VEHICLE_CLASSES
from app.simulation.controllers import DemandView, make_controller
from app.simulation.models import SIM_DT, IntersectionProfile
from app.simulation.signals import GREEN, RED, YELLOW, SignalMachine

SNAPSHOT_SCHEMA_VERSION = "1.1"  # надмножество схемы снимка этапа 1 (1.0): поля не переименованы

VEHICLE_SPECS: dict[str, dict] = {
    # длина, м; ускорение, м/с²; комфортное торможение, м/с²; предел скорости класса, м/с
    "car": {"length": 4.5, "accel": 2.5, "decel": 3.5, "vmax": 16.7},
    "bus": {"length": 12.0, "accel": 1.2, "decel": 2.5, "vmax": 12.0},
    "truck": {"length": 10.0, "accel": 1.0, "decel": 2.5, "vmax": 12.5},
    "motorcycle": {"length": 2.2, "accel": 3.5, "decel": 4.0, "vmax": 16.7},
}
# Условная длина пути через перекрёсток после стоп-линии (только для момента выезда).
CROSS_PATH_M = {"straight": 24.0, "left": 30.0, "right": 12.0}

STOP_SPEED = 0.5
MOVE_SPEED = 1.0
QUEUE_STOPLINE_TOL_M = 1.0
QUEUE_GAP_TOL_M = 1.0
FLOW_WINDOW_SEC = 60.0
assert set(VEHICLE_SPECS) == set(VEHICLE_CLASSES)


@dataclass
class Vehicle:
    vid: int
    lane_id: str
    cls: str
    movement: str
    group: str
    length: float
    accel: float
    decel: float
    vmax: float
    arrival_time: float
    spawn_time: float
    pos: float
    speed: float
    state: str = "moving"
    crossed: bool = False
    cross_time: float | None = None
    queue_join_time: float | None = None
    stops: int = 0
    detector_passed: bool = False
    yellow_decision: str | None = None  # None | "go" | "stop"


@dataclass
class PendingArrival:
    arrival_time: float
    cls: str
    movement: str


@dataclass
class LaneRuntime:
    lane_id: str
    length: float
    speed_limit: float
    movements: list[str]
    base_rate_vph: float
    rng: random.Random
    vehicles: list[Vehicle] = field(default_factory=list)  # от головы к хвосту
    backlog: deque = field(default_factory=deque)
    next_candidate_time: float = 0.0
    rate_upper_vph: float = 0.0
    crossing_times: deque = field(default_factory=deque)
    total_crossings: int = 0
    seen_classes: Counter = field(default_factory=Counter)
    arrivals: int = 0
    departed: int = 0
    sum_delay: float = 0.0
    sum_stops: int = 0
    sum_wait_departed: float = 0.0
    max_wait_departed: float = 0.0
    max_delay: float = 0.0


class Simulation:
    def __init__(
        self,
        profile: IntersectionProfile,
        controller_mode: str = "adaptive",
        seed: int | None = None,
        dt: float = SIM_DT,
    ):
        self.profile = profile
        self.dt = dt
        self.seed = profile.traffic.seed if seed is None else int(seed)
        self.controller_mode = controller_mode
        self.controller_mode_switches: list[dict] = []
        self.machine = SignalMachine(profile, make_controller(controller_mode, profile), dt)
        self.tick = 0
        self.min_gap = profile.traffic.min_gap_m
        self.wait_weight = profile.adaptive.wait_weight_per_sec
        self.detector_m = profile.timings.detector_distance_m
        self.movement_group = profile.movement_group()
        self.red_clamps = 0
        self._next_vid = 1
        self._digest = hashlib.sha256()
        self._last_demand = DemandView()
        self._group_last_actuation: dict[str, int] = {}
        self.departed_total = 0
        self.sum_delay_total = 0.0
        self.sum_stops_total = 0

        comp = profile.traffic.composition
        total = sum(comp.values())
        self._class_cdf: list[tuple[float, str]] = []
        acc = 0.0
        for cls in VEHICLE_CLASSES:  # фиксированный порядок → детерминизм
            share = comp.get(cls, 0.0) / total
            if share > 0:
                acc += share
                self._class_cdf.append((acc, cls))

        self.lanes: dict[str, LaneRuntime] = {}
        for lane in profile.lanes:
            rt = LaneRuntime(
                lane_id=lane.id,
                length=lane.length_m,
                speed_limit=lane.speed_limit_mps,
                movements=[m.value for m in lane.movements],
                base_rate_vph=lane.arrival_rate_vph,
                rng=random.Random(f"{self.seed}|{lane.id}"),
            )
            upper = lane.arrival_rate_vph
            for seg in profile.traffic.scenario:
                if not seg.lane_ids or lane.id in seg.lane_ids:
                    upper *= max(1.0, seg.multiplier)
            rt.rate_upper_vph = upper
            rt.next_candidate_time = self._draw_interval(rt, 0.0)
            self.lanes[lane.id] = rt

    # --- время ---

    @property
    def time_sec(self) -> float:
        return round(self.tick * self.dt, 6)

    # --- режим контроллера ---

    def set_controller_mode(self, mode: str) -> None:
        if mode == self.controller_mode:
            return
        self.machine.set_controller(make_controller(mode, self.profile))
        self.controller_mode_switches.append(
            {"t": self.time_sec, "from": self.controller_mode, "to": mode}
        )
        self.controller_mode = mode

    # --- прибытия ---

    def rate_vph(self, rt: LaneRuntime, t: float) -> float:
        r = rt.base_rate_vph
        for seg in self.profile.traffic.scenario:
            if seg.start_sec <= t < seg.end_sec and (not seg.lane_ids or rt.lane_id in seg.lane_ids):
                r *= seg.multiplier
        return r

    def _draw_interval(self, rt: LaneRuntime, t: float) -> float:
        if rt.rate_upper_vph <= 0:
            return math.inf
        return t + rt.rng.expovariate(rt.rate_upper_vph / 3600.0)

    def _generate_arrivals(self, rt: LaneRuntime, until: float) -> None:
        while rt.next_candidate_time <= until:
            t = rt.next_candidate_time
            # прореживание: кандидат принимается с вероятностью r(t)/r_max
            accept = rt.rng.random() < self.rate_vph(rt, t) / rt.rate_upper_vph
            u_cls = rt.rng.random()
            u_mov = rt.rng.random()
            if accept:
                cls = next((c for edge, c in self._class_cdf if u_cls < edge), self._class_cdf[-1][1])
                movement = rt.movements[min(int(u_mov * len(rt.movements)), len(rt.movements) - 1)]
                rt.backlog.append(PendingArrival(t, cls, movement))
                rt.arrivals += 1
                rt.seen_classes[cls] += 1
            rt.next_candidate_time = self._draw_interval(rt, t)

    def _try_spawn(self, rt: LaneRuntime, now: float) -> None:
        if not rt.backlog:
            return
        obstacle = rt.length
        if rt.vehicles:
            last = rt.vehicles[-1]
            obstacle = last.pos - last.length - self.min_gap
            if obstacle < 0:
                return  # нет места у начала участка — машина остаётся в очереди въезда
        pa: PendingArrival = rt.backlog.popleft()
        spec = VEHICLE_SPECS[pa.cls]
        vmax = min(spec["vmax"], rt.speed_limit)
        group = self.movement_group[(rt.lane_id, pa.movement)]
        v0 =min(vmax, math.sqrt(2 * spec["decel"] * max(obstacle, 0.0)))
        veh = Vehicle(
            vid=self._next_vid, lane_id=rt.lane_id, cls=pa.cls, movement=pa.movement, group=group,
            length=spec["length"], accel=spec["accel"], decel=spec["decel"], vmax=vmax,
            arrival_time=pa.arrival_time, spawn_time=now, pos=0.0, speed=v0,
        )
        self._next_vid += 1
        if now - pa.arrival_time > self.dt + 1e-9:
            # стояла в очереди въезда за пределами участка — это ожидание и остановка
            veh.queue_join_time = pa.arrival_time
            veh.stops = 1
        rt.vehicles.append(veh)

    # --- спрос для контроллера ---

    def _build_demand(self, now: float) -> DemandView:
        gd: dict[str, float] = {}
        gw: dict[str, float] = {}
        gq: dict[str, int] = {}
        w = self.wait_weight
        for rt in self.lanes.values():
            for v in rt.vehicles:
                if v.crossed or v.queue_join_time is None:
                    continue
                wait = now - v.queue_join_time
                gq[v.group] = gq.get(v.group, 0) + 1
                gd[v.group] = gd.get(v.group, 0.0) + 1.0 + w * wait
                if wait > gw.get(v.group, -1.0):
                    gw[v.group] = wait
            for pa in rt.backlog:
                group = self.movement_group[(rt.lane_id, pa.movement)]
                wait = max(0.0, now - pa.arrival_time)
                gq[group] = gq.get(group, 0) + 1
                gd[group] = gd.get(group, 0.0) + 1.0 + w * wait
                if wait > gw.get(group, -1.0):
                    gw[group] = wait
        return DemandView(group_demand=gd, group_max_wait=gw, group_queue_count=gq,
                          group_last_actuation=dict(self._group_last_actuation))

    # --- шаг ---

    def step(self) -> None:
        t0 = self.tick * self.dt
        t1 = (self.tick + 1) * self.dt

        for rt in self.lanes.values():
            self._generate_arrivals(rt, t1)

        demand = self._build_demand(t0)
        self.machine.step(demand)
        self._last_demand = demand
        signals = self.machine.signals
        self.tick += 1

        for rt in self.lanes.values():
            self._move_lane(rt, signals, t0, t1)
            self._try_spawn(rt, t1)

    def _move_lane(self, rt: LaneRuntime, signals: dict[str, str], t0: float, t1: float) -> None:
        dt = self.dt
        stop_line = rt.length
        detector = stop_line - self.detector_m
        leader: Vehicle | None = None
        survivors: list[Vehicle] = []
        for v in rt.vehicles:
            obstacle = math.inf
            if leader is not None:
                obstacle = leader.pos - leader.length - self.min_gap
            sig = signals.get(v.group, RED)
            if not v.crossed:
                if sig == GREEN:
                    v.yellow_decision = None
                    must_stop = False
                elif sig == YELLOW:
                    if v.yellow_decision is None:
                        dist = stop_line - v.pos
                        braking = v.speed * v.speed / (2 * v.decel)
                        v.yellow_decision = "stop" if dist >= braking else "go"
                    must_stop = v.yellow_decision == "stop"
                else:
                    v.yellow_decision = None
                    must_stop = True
                if must_stop:
                    obstacle = min(obstacle, stop_line)

            d = max(0.0, obstacle - v.pos)
            v_new = min(v.speed + v.accel * dt, v.vmax, math.sqrt(2 * v.decel * d), d / dt)
            v_new = max(0.0, v_new)
            old_pos = v.pos
            new_pos = old_pos + v_new * dt

            if not v.crossed and new_pos > stop_line and sig == RED:
                # страховка: на красном стоп-линию не пересечь (в норме не срабатывает)
                self.red_clamps += 1
                new_pos, v_new = stop_line, 0.0

            v.pos, v.speed = new_pos, v_new

            if not v.crossed and not v.detector_passed and detector > 0 and old_pos < detector <= new_pos:
                v.detector_passed = True
                self._group_last_actuation[v.group] = self.tick

            if not v.crossed and new_pos > stop_line:
                frac = (stop_line - old_pos) / (new_pos - old_pos) if new_pos > old_pos else 1.0
                self._on_cross(rt, v, t0 + frac * dt)

            if not v.crossed:
                self._update_queue_state(v, leader, stop_line, t1)

            if v.crossed and v.pos > stop_line + CROSS_PATH_M[v.movement]:
                pass  # выехала из перекрёстка — удаляем
            else:
                survivors.append(v)
            leader = v
        rt.vehicles = survivors

        while rt.crossing_times and rt.crossing_times[0] < t1 - FLOW_WINDOW_SEC:
            rt.crossing_times.popleft()

    def _update_queue_state(self, v: Vehicle, leader: Vehicle | None, stop_line: float, now: float) -> None:
        if v.state == "moving":
            if v.speed < STOP_SPEED:
                at_line = stop_line - v.pos <= QUEUE_STOPLINE_TOL_M
                behind_queue = (
                    leader is not None
                    and not leader.crossed
                    and leader.state == "waiting"
                    and (leader.pos - leader.length - v.pos) <= self.min_gap + QUEUE_GAP_TOL_M
                )
                if at_line or behind_queue:
                    v.state = "waiting"
                    v.stops += 1
                    if v.queue_join_time is None:
                        v.queue_join_time = now
        elif v.speed >= MOVE_SPEED:
            v.state = "moving"

    def _on_cross(self, rt: LaneRuntime, v: Vehicle, t_cross: float) -> None:
        v.crossed = True
        v.cross_time = t_cross
        v.state = "moving"
        self._group_last_actuation[v.group] = self.tick
        rt.crossing_times.append(t_cross)
        rt.total_crossings += 1
        free_flow = rt.length / v.vmax
        delay = max(0.0, (t_cross - v.arrival_time) - free_flow)
        wait = (t_cross - v.queue_join_time) if v.queue_join_time is not None else 0.0
        rt.departed += 1
        rt.sum_delay += delay
        rt.max_delay = max(rt.max_delay, delay)
        rt.sum_stops += v.stops
        rt.sum_wait_departed += wait
        rt.max_wait_departed = max(rt.max_wait_departed, wait)
        self.departed_total += 1
        self.sum_delay_total += delay
        self.sum_stops_total += v.stops

    def run_until(self, t_sec: float) -> None:
        target = int(round(t_sec / self.dt))
        while self.tick < target:
            self.step()

    # --- снимки ---

    def lane_snapshot(self, rt: LaneRuntime, now: float) -> dict:
        lane = self.profile.lane(rt.lane_id)
        on_lane = [v for v in rt.vehicles if not v.crossed]
        queued = [v for v in on_lane if v.state == "waiting"]
        waits = [now - v.queue_join_time for v in on_lane if v.queue_join_time is not None]
        waits += [max(0.0, now - pa.arrival_time) for pa in rt.backlog]
        flow = len(rt.crossing_times)
        window = min(FLOW_WINDOW_SEC, now)
        signals = {
            m: self.machine.signals.get(self.movement_group.get((rt.lane_id, m), ""), RED)
            for m in rt.movements
        }
        return {
            "lane_id": rt.lane_id,
            "name": lane.name,
            "color": lane.color,
            "vehicles": len(on_lane),
            "queued": len(queued),
            "queue_truncated_by_frame": False,
            "avg_wait_sec": round(sum(waits) / len(waits), 2) if waits else 0.0,
            "max_wait_sec": round(max(waits), 2) if waits else 0.0,
            "wait_sample_size": len(waits),
            "flow_count_window": flow,
            "flow_window_available_sec": round(window, 2),
            "flow_window_target_sec": FLOW_WINDOW_SEC,
            "total_crossings": rt.total_crossings,
            "vehicle_types": {c: n for c, n in sorted(rt.seen_classes.items())},
            # --- новые поля этапа 2 ---
            "approach_id": lane.approach_id,
            "entry_backlog": len(rt.backlog),
            "queue_spillback": len(rt.backlog) > 0,
            "signals": signals,
            "arrival_rate_vph_now": round(self.rate_vph(rt, now), 1),
            "arrivals": rt.arrivals,
            "departed_count": rt.departed,
            "avg_delay_sec": round(rt.sum_delay / rt.departed, 2) if rt.departed else 0.0,
            "max_delay_sec": round(rt.max_delay, 2),
            "stops_per_vehicle": round(rt.sum_stops / rt.departed, 3) if rt.departed else 0.0,
            "avg_departed_wait_sec": round(rt.sum_wait_departed / rt.departed, 2) if rt.departed else 0.0,
            "max_departed_wait_sec": round(rt.max_wait_departed, 2),
            "throughput_per_hour": round(flow * 3600.0 / window, 1) if window >= 1.0 else 0.0,
        }

    def snapshot(self) -> dict:
        now = self.time_sec
        m = self.machine
        lanes = [self.lane_snapshot(rt, now) for rt in self.lanes.values()]
        return {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "source": "simulation",
            "timestamp_sec": round(now, 3),
            "lanes": lanes,
            "controller_mode": self.controller_mode,
            "signal_state": m.state.value,
            "active_phase": m.phase if m.state.value in ("GREEN", "YELLOW") else None,
            "next_phase": m.next_phase if m.state.value in ("YELLOW", "ALL_RED") else None,
            "phase_remaining_sec": m.remaining_sec(self._last_demand),
            "phase_remaining_is_estimate": self.controller_mode == "adaptive" and m.state.value == "GREEN",
            "signals": dict(m.signals),
            "totals": self.totals(),
            "safety": self.safety(),
        }

    def totals(self) -> dict:
        now = self.time_sec
        n = self.departed_total
        return {
            "departed": n,
            "avg_delay_sec": round(self.sum_delay_total / n, 2) if n else 0.0,
            "stops_per_vehicle": round(self.sum_stops_total / n, 3) if n else 0.0,
            "throughput_per_hour": round(n * 3600.0 / now, 1) if now >= 1.0 else 0.0,
            "vehicles_in_system": sum(
                len([v for v in rt.vehicles if not v.crossed]) + len(rt.backlog)
                for rt in self.lanes.values()
            ),
        }

    def safety(self) -> dict:
        return {
            "blocked_violations": self.machine.blocked_violations,
            "faults": self.machine.fault_count,
            "red_clamps": self.red_clamps,
            "conflict_invariant_ok_now": self.machine.is_safe(),
        }

    def scene(self) -> dict:
        """Положение машин и сигналов для 2D-схемы (не для аналитики)."""
        vehicles = []
        for rt in self.lanes.values():
            for v in rt.vehicles:
                s = v.pos - rt.length  # < 0 до стоп-линии
                vehicles.append(
                    {
                        "id": v.vid,
                        "lane_id": rt.lane_id,
                        "cls": v.cls,
                        "movement": v.movement,
                        "s": round(s, 2),
                        "length": v.length,
                        "state": v.state,
                        "crossed": v.crossed,
                        "progress": round(min(1.0, s / CROSS_PATH_M[v.movement]), 3) if v.crossed else 0.0,
                    }
                )
        m = self.machine
        return {
            "t": self.time_sec,
            "signal_state": m.state.value,
            "active_phase": m.phase if m.state.value in ("GREEN", "YELLOW") else None,
            "next_phase": m.next_phase if m.state.value in ("YELLOW", "ALL_RED") else None,
            "phase_remaining_sec": m.remaining_sec(self._last_demand),
            "phase_remaining_is_estimate": self.controller_mode == "adaptive" and m.state.value == "GREEN",
            "controller_mode": self.controller_mode,
            "signals": dict(m.signals),
            "vehicles": vehicles,
            "backlog": {rt.lane_id: len(rt.backlog) for rt in self.lanes.values()},
        }

    def trajectory_state(self) -> list[tuple]:
        """Точное состояние всех машин — для проверки детерминизма."""
        return [
            (v.vid, rt.lane_id, v.cls, v.movement, v.pos, v.speed, v.state, v.crossed)
            for rt in self.lanes.values()
            for v in rt.vehicles
        ]

    def update_digest(self) -> str:
        for item in self.trajectory_state():
            self._digest.update(repr(item).encode())
        self._digest.update(repr((self.tick, self.machine.state.value, self.machine.phase)).encode())
        return self._digest.hexdigest()

    def phase_green_stats(self) -> dict:
        out: dict[str, dict] = {}
        for p in self.profile.phases:
            ds = [g["duration_sec"] for g in self.machine.green_log if g["phase_id"] == p.id]
            out[p.id] = {
                "name": p.name,
                "greens": len(ds),
                "mean_green_sec": round(sum(ds) / len(ds), 2) if ds else 0.0,
                "min_green_sec": min(ds) if ds else 0.0,
                "max_green_sec": max(ds) if ds else 0.0,
            }
        return out

    def summary(self) -> dict:
        now = self.time_sec
        lanes = {}
        for rt in self.lanes.values():
            snap = self.lane_snapshot(rt, now)
            lanes[rt.lane_id] = {
                "name": snap["name"],
                "arrivals": rt.arrivals,
                "departed_count": rt.departed,
                "avg_delay_sec": snap["avg_delay_sec"],
                "max_delay_sec": snap["max_delay_sec"],
                "stops_per_vehicle": snap["stops_per_vehicle"],
                "avg_departed_wait_sec": snap["avg_departed_wait_sec"],
                "max_departed_wait_sec": snap["max_departed_wait_sec"],
                "throughput_per_hour": round(rt.departed * 3600.0 / now, 1) if now >= 1 else 0.0,
                "left_in_system": snap["vehicles"] + snap["entry_backlog"],
            }
        return {
            "sim_time_sec": round(now, 3),
            "controller_mode": self.controller_mode,
            "controller_mode_switches": self.controller_mode_switches,
            "seed": self.seed,
            "totals": self.totals(),
            "lanes": lanes,
            "phases": self.phase_green_stats(),
            "safety": self.safety(),
            "trajectory_digest": self._digest.hexdigest(),
        }
