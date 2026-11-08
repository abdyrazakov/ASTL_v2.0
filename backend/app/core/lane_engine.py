"""Ядро аналитики по полосам: состояние треков, переходы очереди, подсчёт пересечений.

Все времена — ВРЕМЯ ВИДЕО В СЕКУНДАХ (video_time), а не время обработки на
компьютере. Пауза обработки не продвигает video_time, поэтому ожидание не
растёт во время паузы и не зависит от скорости CPU — это гарантируется тем,
что единственный источник времени здесь — номер кадра видео, делённый на fps
исходного ролика.

Правила перехода состояния очереди для одного трека:

    moving --(внутри queue_zone и не дальше stop_max_drift_bbox_h от места
               остановки, непрерывно stop_duration_threshold_sec)--> waiting

    waiting --(speed > stop_exit_speed ИЛИ вышел из queue_zone, непрерывно
                queue_exit_duration_sec)--> moving

Короткий провал ниже stop_exit_speed во время отсчёта выхода НЕ сбрасывает
накопленное wait_start — обнуляется только таймер подтверждения выхода
(moving_candidate_since), а не момент начала ожидания. Так единичный толчок
на 0.3 с в пробке не "обнуляет" накопленное ожидание машины. stop_exit_speed
выше скорости подтягивания в очереди, поэтому подтягивание за передней
машиной тоже не считается отъездом.

Стоящая машина, которую детектор временно потерял, удерживается
stationary_track_retention_sec и продолжает считаться в очереди. Если трекер
вернул её под новым ID рядом с прежним местом (или с рамкой, перекрывающей
прежнюю, — у частично закрытой машины), состояние (включая wait_start)
переходит к новому ID — иначе каждый сбой трекинга обнулял бы ожидание.

Скорость нормируется на высоту рамки машины (px/px в секунду), что частично
компенсирует перспективу: чем ближе к камере (крупнее рамка), тем больше
нужно пройти пикселей в секунду, чтобы считаться "движущимся".

Скорость считается по окну `speed_window_sec` СЕКУНД видео (не кадров): берётся
самая старая точка не старше этого окна и самая новая, разница позиций делится
на реальный интервал времени между ними. Слишком короткое окно (доли секунды)
усиливает обычное дрожание рамки детектора в скорость, в разы превышающую
пороги — тогда даже припаркованная машина никогда не "затихает" достаточно
надолго, чтобы попасть в очередь (это реальный баг, найденный и исправленный:
смотри backend/tests/test_lane_engine.py::test_stationary_jitter_does_not_block_queue_detection).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from app.core.geometry import CountLinePx
from app.models.profile import AnalysisParams, Lane, Profile, ReferencePointMode

Point = tuple[float, float]
BBox = tuple[float, float, float, float]  # x1, y1, x2, y2 в пикселях


# Нижний край рамки детектора часто проходит не по точке контакта колёс с
# дорогой, а чуть ниже (тень, блики, неточность рамки) — поэтому опорная
# точка "низ по центру" берётся не ровно на нижней стороне, а приподнятой
# на 2/5 расстояния от центра рамки до нижней стороны (= 0.3 высоты рамки
# выше нижнего края).
_BOTTOM_CENTER_RISE_FRACTION = 0.3


def reference_point(bbox: BBox, mode: ReferencePointMode) -> Point:
    x1, y1, x2, y2 = bbox
    if mode == ReferencePointMode.bottom_center:
        height = y2 - y1
        return ((x1 + x2) / 2, y2 - _BOTTOM_CENTER_RISE_FRACTION * height)
    if mode == ReferencePointMode.bottom_left:
        return (x1, y2)
    if mode == ReferencePointMode.bottom_right:
        return (x2, y2)
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _overlap_of_smaller(a: BBox, b: BBox) -> float:
    """Площадь пересечения рамок, делённая на площадь меньшей из них."""
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return iw * ih / smaller if smaller > 0 else 0.0


@dataclass
class Detection:
    track_id: int
    cls: str
    conf: float
    bbox: BBox


@dataclass
class TrackState:
    track_id: int
    cls: str
    last_seen_time: float
    last_raw_point: Point
    last_bbox: BBox
    first_seen_time: float = 0.0
    # (t, point, bbox_h); maxlen — лишь защита от неограниченного роста при
    # аномально высоком fps источника, реальная обрезка — по времени (см.
    # trim_point_history), не по количеству точек.
    point_history: deque = field(default_factory=lambda: deque(maxlen=2000))

    assigned_lane: str | None = None
    candidate_lane: str | None = "__unset__"
    candidate_since: float | None = None

    queue_state: str = "moving"  # moving | waiting
    stop_candidate_since: float | None = None
    stop_anchor: Point | None = None  # усреднённая точка в момент остановки
    wait_start: float | None = None
    moving_candidate_since: float | None = None

    crossed_lines: set = field(default_factory=set)
    visible_this_tick: bool = True


    def trim_point_history(self, speed_window_sec: float) -> None:
        """Обрезает историю точек по ВРЕМЕНИ, оставляя всегда минимум 2 точки.
        Старейшую точку удаляем, только если без неё история всё ещё
        покрывает как минимум speed_window_sec — иначе окно станет слишком
        коротким и дрожание детектора снова превратится в ложную скорость."""
        dq = self.point_history
        while len(dq) > 2 and (dq[-1][0] - dq[1][0]) >= speed_window_sec:
            dq.popleft()

    def smoothed_point(self) -> Point:
        """Усреднённая по окну сглаживания опорная точка. Используется там, где
        важна устойчивость к дрожанию в 1-2px у самой границы фигуры (попадание
        в зону очереди), а не сырая точка текущего кадра — иначе машина,
        стоящая почти точно на границе тонкого полигона, будет каждый кадр
        случайно "мигать" внутри/снаружи зоны и никогда не накопит нужную
        непрерывность, даже если скорость уже корректно близка к нулю."""
        if not self.point_history:
            return self.last_raw_point
        xs = sum(p[0] for (_, p, _) in self.point_history)
        ys = sum(p[1] for (_, p, _) in self.point_history)
        n = len(self.point_history)
        return (xs / n, ys / n)

    def smoothed_time(self) -> float:
        """Среднее время отсчётов, по которым считается smoothed_point()."""
        if not self.point_history:
            return self.last_seen_time
        return sum(t for (t, _, _) in self.point_history) / len(self.point_history)

    def smoothed_speed(self) -> float:
        """Нормированная скорость: смещение опорной точки / высота рамки / время.

        ВАЖНО: сравниваются не сырые первая/последняя точки окна, а СРЕДНИЕ
        позиции первой и второй половины окна. Если сравнивать только две
        сырые точки, дрожание детектора в каждой из них (шум в 1-3px) всё
        равно даёт шумную оценку скорости независимо от длины окна — удлинение
        окна уменьшает лишь знаменатель (время), но не шум в числителе
        (разница всего двух зашумлённых отсчётов). Усреднение нескольких
        точек по обе стороны окна дополнительно подавляет именно этот шум
        (примерно в sqrt(N/2) раз), а не только удлиняет базу времени."""
        n = len(self.point_history)
        if n < 2:
            return 0.0
        mid = max(n // 2, 1)
        first_half = list(self.point_history)[:mid]
        second_half = list(self.point_history)[mid:] or [self.point_history[-1]]

        def centroid(entries):
            t = sum(e[0] for e in entries) / len(entries)
            x = sum(e[1][0] for e in entries) / len(entries)
            y = sum(e[1][1] for e in entries) / len(entries)
            h = sum(e[2] for e in entries) / len(entries)
            return t, x, y, h

        t0, p0x, p0y, h0 = centroid(first_half)
        t1, p1x, p1y, h1 = centroid(second_half)

        dt = t1 - t0
        if dt <= 1e-6:
            return 0.0
        dist = ((p1x - p0x) ** 2 + (p1y - p0y) ** 2) ** 0.5
        avg_h = max((h0 + h1) / 2, 1.0)
        return (dist / avg_h) / dt


@dataclass
class CrossingEvent:
    timestamp_sec: float
    track_id: int
    cls: str
    direction: str


@dataclass
class LaneRuntime:
    lane: Lane
    line_px: CountLinePx
    crossings: list = field(default_factory=list)  # CrossingEvent
    seen_track_classes: dict = field(default_factory=dict)  # track_id -> cls (уникальные треки)

    @property
    def total_crossings(self) -> int:
        return len(self.crossings)

    def flow_count(self, now: float, window_sec: float) -> tuple[int, float]:
        window_start = max(0.0, now - window_sec)
        count = sum(1 for c in self.crossings if c.timestamp_sec >= window_start)
        available_window = min(window_sec, now)
        return count, available_window

    def vehicle_type_composition(self) -> dict:
        comp: dict[str, int] = {}
        for cls in self.seen_track_classes.values():
            comp[cls] = comp.get(cls, 0) + 1
        return comp


class AnalyticsEngine:
    """Держит состояние по всем активным трекам и агрегаты по полосам."""

    def __init__(self, profile: Profile, frame_w: int, frame_h: int):
        self.profile = profile
        self.params: AnalysisParams = profile.analysis_params
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.tracks: dict[int, TrackState] = {}
        self.lanes: dict[str, LaneRuntime] = {}
        for lane in profile.lanes:
            line = lane.count_line
            p1 = (line.p1.x * frame_w, line.p1.y * frame_h)
            p2 = (line.p2.x * frame_w, line.p2.y * frame_h)
            pos_pt = (
                line.positive_side_point.x * frame_w,
                line.positive_side_point.y * frame_h,
            )
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            sign = dx * (pos_pt[1] - p1[1]) - dy * (pos_pt[0] - p1[0])
            line_px = CountLinePx(p1=p1, p2=p2, positive_sign=sign, direction=line.direction.value)
            self.lanes[lane.id] = LaneRuntime(lane=lane, line_px=line_px)

    def _lane_for_point(self, point: Point) -> str | None:
        px_norm = (point[0] / self.frame_w, point[1] / self.frame_h)
        for lane_id, runtime in self.lanes.items():
            if runtime.lane.observation_polygon.contains(px_norm):
                return lane_id
        return None

    def _ref_mode_for_lane(self, lane_id: str | None) -> ReferencePointMode:
        if lane_id is not None:
            lane = self.lanes[lane_id].lane
            if lane.reference_point_mode is not None:
                return lane.reference_point_mode
        return self.profile.reference_point_mode

    def _is_stationary(self, track: TrackState) -> bool:
        """В очереди или стоит уже не меньше половины stop_duration_threshold_sec.
        Кандидат в остановку появляется у любой машины в зоне очереди, поэтому
        без выдержки удержание и перенос ID доставались бы и едущим машинам."""
        if track.queue_state == "waiting":
            return True
        since = track.stop_candidate_since
        return since is not None and (
            track.last_seen_time - since >= self.params.stop_duration_threshold_sec / 2
        )

    def _retention_sec(self, track: TrackState) -> float:
        if self._is_stationary(track):
            return max(self.params.stationary_track_retention_sec, self.params.track_lost_grace_sec)
        return self.params.track_lost_grace_sec

    def _is_present(self, track: TrackState, now: float) -> bool:
        return now - track.last_seen_time <= self._retention_sec(track)

    def _same_vehicle(self, lost: TrackState, new: TrackState) -> bool:
        params = self.params
        if new.first_seen_time < lost.last_seen_time - params.reid_new_track_window_sec:
            return False  # давно существующий трек — это соседняя машина
        h = max(lost.last_bbox[3] - lost.last_bbox[1], new.last_bbox[3] - new.last_bbox[1], 1.0)
        (lx, ly), (nx, ny) = lost.last_raw_point, new.last_raw_point
        if ((lx - nx) ** 2 + (ly - ny) ** 2) ** 0.5 <= params.reid_max_distance_bbox_h * h:
            return True
        return _overlap_of_smaller(lost.last_bbox, new.last_bbox) >= params.reid_min_box_overlap

    def _merge_reappeared(self, now: float, frame_ids: set) -> None:
        """Потерянная стоящая машина, на месте которой трекер завёл новый ID, —
        та же машина: новый трек получает её ожидание, старый удаляется (иначе
        машина ещё stationary_track_retention_sec считалась бы дважды)."""
        lost_ids = [
            tid for tid, t in self.tracks.items()
            if tid not in frame_ids and self._is_stationary(t)
        ]
        for lost_id in lost_ids:
            lost = self.tracks[lost_id]
            match = next(
                (
                    t for tid, t in self.tracks.items()
                    if tid in frame_ids and self._same_vehicle(lost, t)
                ),
                None,
            )
            if match is None:
                continue
            if lost.queue_state == "waiting" and (
                match.queue_state != "waiting" or lost.wait_start < match.wait_start
            ):
                match.queue_state = "waiting"
                match.wait_start = lost.wait_start
                match.moving_candidate_since = None
            elif match.queue_state == "moving" and lost.stop_candidate_since is not None and (
                match.stop_candidate_since is None
                or lost.stop_candidate_since < match.stop_candidate_since
            ):
                match.stop_candidate_since = lost.stop_candidate_since
                match.stop_anchor = match.smoothed_point()
            match.crossed_lines |= lost.crossed_lines
            for runtime in self.lanes.values():
                # Состав считается по уникальным машинам, а не по ID трекера.
                runtime.seen_track_classes.pop(lost_id, None)
            del self.tracks[lost_id]

    def update(self, now: float, detections: list[Detection]) -> None:
        params = self.params
        seen_ids = set()
        frame_ids = {d.track_id for d in detections}

        for det in detections:
            seen_ids.add(det.track_id)
            track = self.tracks.get(det.track_id)
            # Опорная точка зависит от режима полосы, в которую трек ранее
            # был назначен (двухпроходная оценка: сперва считаем bottom_center
            # как первичную гипотезу для привязки к полосе).
            provisional_mode = self._ref_mode_for_lane(
                track.assigned_lane if track else None
            )
            point = reference_point(det.bbox, provisional_mode)
            bbox_h = max(det.bbox[3] - det.bbox[1], 1.0)

            if track is None:
                track = TrackState(
                    track_id=det.track_id,
                    cls=det.cls,
                    last_seen_time=now,
                    last_raw_point=point,
                    last_bbox=det.bbox,
                    first_seen_time=now,
                )
                track.point_history.append((now, point, bbox_h))
                self.tracks[det.track_id] = track
            else:
                track.point_history.append((now, point, bbox_h))
            track.trim_point_history(params.speed_window_sec)

            track.visible_this_tick = True
            track.cls = det.cls
            track.last_bbox = det.bbox

            # --- Привязка к полосе с гистерезисом ---
            # Гистерезис защищает от дрожания ТОЛЬКО при смене/потере уже
            # имеющейся привязки. Первое появление трека в какой-либо полосе
            # назначается сразу — переходу "из ниоткуда" дрожать не из чего.
            raw_lane = self._lane_for_point(point)
            if raw_lane == track.assigned_lane:
                track.candidate_lane = "__unset__"
                track.candidate_since = None
            elif track.assigned_lane is None:
                track.assigned_lane = raw_lane
                track.candidate_lane = "__unset__"
                track.candidate_since = None
            else:
                if track.candidate_lane != raw_lane:
                    track.candidate_lane = raw_lane
                    track.candidate_since = now
                elif now - (track.candidate_since or now) >= params.lane_switch_hysteresis_sec:
                    track.assigned_lane = raw_lane
                    track.candidate_lane = "__unset__"
                    track.candidate_since = None

            # --- Состояние очереди ---
            lane_id = track.assigned_lane
            in_queue_zone = False
            smoothed = track.smoothed_point()
            if lane_id is not None:
                lane_runtime = self.lanes[lane_id]
                px_norm = (smoothed[0] / self.frame_w, smoothed[1] / self.frame_h)
                in_queue_zone = lane_runtime.lane.queue_zone_polygon.contains(px_norm)
                lane_runtime.seen_track_classes[track.track_id] = track.cls

            speed = track.smoothed_speed()

            if track.queue_state == "moving":
                if in_queue_zone:
                    anchor = track.stop_anchor
                    drift = (
                        ((smoothed[0] - anchor[0]) ** 2 + (smoothed[1] - anchor[1]) ** 2) ** 0.5 / bbox_h
                        if anchor is not None
                        else None
                    )
                    smoothed_t = track.smoothed_time()
                    if drift is None or drift > params.stop_max_drift_bbox_h:
                        # Ещё едет: отсчёт стояния начинается заново с текущего места.
                        # Время якоря — среднее время тех же отсчётов, что и точка:
                        # у нового трека в истории одна точка без запаздывания, и
                        # сравнение с now укоротило бы окно (на реальном видео так в
                        # очередь попала машина, ехавшая издалека прямо на камеру).
                        track.stop_anchor = smoothed
                        track.stop_candidate_since = smoothed_t
                    elif smoothed_t - track.stop_candidate_since >= params.stop_duration_threshold_sec:
                        track.queue_state = "waiting"
                        track.wait_start = track.stop_candidate_since
                        track.moving_candidate_since = None
                else:
                    track.stop_candidate_since = None
                    track.stop_anchor = None
            else:  # waiting
                left_zone = not in_queue_zone
                fast_enough = speed > params.stop_exit_speed
                if fast_enough or left_zone:
                    if track.moving_candidate_since is None:
                        track.moving_candidate_since = now
                    elif now - track.moving_candidate_since >= params.queue_exit_duration_sec:
                        track.queue_state = "moving"
                        track.wait_start = None
                        track.stop_candidate_since = None
                        track.stop_anchor = None
                        track.moving_candidate_since = None
                else:
                    track.moving_candidate_since = None

            # --- Подсчёт пересечений линии (по "сырой" точке кадр-к-кадру) ---
            prev_point = track.last_raw_point
            if prev_point != point:
                for lid, lane_runtime in self.lanes.items():
                    if lid in track.crossed_lines:
                        continue
                    if lane_runtime.line_px.counts(prev_point, point):
                        direction = lane_runtime.line_px.crossing_direction(prev_point, point)
                        lane_runtime.crossings.append(
                            CrossingEvent(
                                timestamp_sec=now,
                                track_id=track.track_id,
                                cls=track.cls,
                                direction=direction or "positive",
                            )
                        )
                        track.crossed_lines.add(lid)

            track.last_raw_point = point
            track.last_seen_time = now

        self._merge_reappeared(now, frame_ids)

        # --- Треки, не замеченные на этом тике: проверка периода удержания ---
        to_delete = []
        for tid, track in self.tracks.items():
            if tid in seen_ids:
                continue
            track.visible_this_tick = False
            if not self._is_present(track, now):
                to_delete.append(tid)
        for tid in to_delete:
            del self.tracks[tid]

    def snapshot(self, now: float) -> dict:
        lanes_out = []
        for lane_id, runtime in self.lanes.items():
            lane = runtime.lane
            current_tracks = [
                t
                for t in self.tracks.values()
                if t.assigned_lane == lane_id and self._is_present(t, now)
            ]
            waiting_tracks = [t for t in current_tracks if t.queue_state == "waiting"]
            waits = [now - t.wait_start for t in waiting_tracks if t.wait_start is not None]
            flow_count, window_avail = runtime.flow_count(now, self.params.flow_window_sec)

            lanes_out.append(
                {
                    "lane_id": lane_id,
                    "name": lane.name,
                    "color": lane.color,
                    "vehicles": len(current_tracks),
                    "queued": len(waiting_tracks),
                    "queue_truncated_by_frame": lane.queue_zone_polygon.touches_frame_border(),
                    "avg_wait_sec": round(sum(waits) / len(waits), 2) if waits else 0.0,
                    "max_wait_sec": round(max(waits), 2) if waits else 0.0,
                    "wait_sample_size": len(waits),
                    "flow_count_window": flow_count,
                    "flow_window_available_sec": round(window_avail, 2),
                    "flow_window_target_sec": self.params.flow_window_sec,
                    "total_crossings": runtime.total_crossings,
                    "vehicle_types": runtime.vehicle_type_composition(),
                }
            )
        return {
            "schema_version": "1.0",
            "timestamp_sec": round(now, 3),
            "lanes": lanes_out,
        }
