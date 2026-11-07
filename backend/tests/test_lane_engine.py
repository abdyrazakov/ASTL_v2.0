import pytest

from app.core.lane_engine import AnalyticsEngine, Detection
from app.models.profile import (
    AnalysisParams,
    CountDirection,
    CountLine,
    Lane,
    Point,
    Polygon,
    Profile,
    ReferencePointMode,
    SourceVideoInfo,
)

W, H = 1000, 1000


def make_profile(**param_overrides) -> Profile:
    lane = Lane(
        id="lane_1",
        name="Тестовая полоса",
        color="#14b8a6",
        observation_polygon=Polygon(
            points=[Point(x=0.1, y=0.1), Point(x=0.9, y=0.1), Point(x=0.9, y=0.9), Point(x=0.1, y=0.9)]
        ),
        queue_zone_polygon=Polygon(
            points=[Point(x=0.2, y=0.2), Point(x=0.8, y=0.2), Point(x=0.8, y=0.8), Point(x=0.2, y=0.8)]
        ),
        count_line=CountLine(
            p1=Point(x=0.5, y=0.1),
            p2=Point(x=0.5, y=0.9),
            positive_side_point=Point(x=0.9, y=0.5),
            direction=CountDirection.positive,
        ),
    )
    defaults = dict(
        stop_enter_speed=0.08,
        stop_duration_threshold_sec=2.0,
        stop_exit_speed=0.20,
        queue_exit_duration_sec=1.0,
        track_lost_grace_sec=1.0,
        lane_switch_hysteresis_sec=0.5,
        flow_window_sec=60.0,
    )
    defaults.update(param_overrides)
    params = AnalysisParams(**defaults)
    return Profile(
        name="test",
        source_video=SourceVideoInfo(filename="x.mp4", width=W, height=H, fps=30, duration_sec=10),
        reference_point_mode=ReferencePointMode.bottom_center,
        lanes=[lane],
        analysis_params=params,
    )


def det(track_id, bbox, cls="car"):
    return Detection(track_id=track_id, cls=cls, conf=0.9, bbox=bbox)


def test_vehicle_counted_as_present_in_lane():
    profile = make_profile()
    engine = AnalyticsEngine(profile, W, H)
    # bbox внутри полосы (center ~ (500,500) в px, bottom_center = (500, 550))
    engine.update(0.0, [det(1, (450, 450, 550, 550))])
    snap = engine.snapshot(0.0)
    assert snap["lanes"][0]["vehicles"] == 1


def test_moving_to_waiting_requires_sustained_stop_duration():
    profile = make_profile()
    engine = AnalyticsEngine(profile, W, H)
    # Машина стоит на месте (один и тот же bbox) в зоне очереди.
    bbox = (450, 450, 550, 550)
    for t in [0.0, 0.5, 1.0, 1.5]:
        engine.update(t, [det(1, bbox)])
    snap = engine.snapshot(1.5)
    # Ещё не набрался stop_duration_threshold_sec=2.0 непрерывного стояния
    assert snap["lanes"][0]["queued"] == 0

    for t in [2.0, 2.1]:
        engine.update(t, [det(1, bbox)])
    snap = engine.snapshot(2.1)
    assert snap["lanes"][0]["queued"] == 1


def test_short_creep_does_not_reset_accumulated_wait():
    """Короткое продвижение (скорость чуть выше stop_enter, но ниже stop_exit)
    не должно сбрасывать накопленное ожидание — машина остаётся waiting, и
    avg_wait_sec продолжает расти от исходного wait_start."""
    profile = make_profile()
    engine = AnalyticsEngine(profile, W, H)
    bbox_still = (450, 450, 550, 550)

    # Стоит достаточно долго, чтобы перейти в waiting.
    for t in [0.0, 0.5, 1.0, 1.5, 2.0, 2.1]:
        engine.update(t, [det(1, bbox_still)])
    assert engine.tracks[1].queue_state == "waiting"
    wait_start_before = engine.tracks[1].wait_start

    # Небольшой "подползание" — скорость между stop_enter(0.08) и stop_exit(0.20),
    # недостаточная и недостаточно долгая, чтобы считаться выходом из очереди.
    bbox_creep = (452, 450, 552, 550)  # смещение на 2px, кратковременно
    engine.update(2.3, [det(1, bbox_creep)])
    engine.update(2.5, [det(1, bbox_still)])  # снова остановился

    assert engine.tracks[1].queue_state == "waiting"
    assert engine.tracks[1].wait_start == wait_start_before


def test_waiting_exits_after_sustained_fast_movement():
    profile = make_profile()
    engine = AnalyticsEngine(profile, W, H)
    bbox_still = (450, 450, 550, 550)
    for t in [0.0, 0.5, 1.0, 1.5, 2.0, 2.1]:
        engine.update(t, [det(1, bbox_still)])
    assert engine.tracks[1].queue_state == "waiting"

    # Устойчивое быстрое движение >= queue_exit_duration_sec (1.0с), подтверждённое
    # на всём протяжении интервала (несколько кадров подряд).
    engine.update(2.3, [det(1, (600, 450, 700, 550))])
    engine.update(2.6, [det(1, (700, 450, 800, 550))])
    engine.update(3.0, [det(1, (850, 450, 950, 550))])
    engine.update(3.4, [det(1, (1000, 450, 1100, 550))])
    assert engine.tracks[1].queue_state == "moving"
    assert engine.tracks[1].wait_start is None


def test_wait_time_driven_by_video_time_not_wallclock():
    """Ключевое требование: время ожидания считается по video_time, которое
    передаётся явно — модуль не обращается к системным часам."""
    import inspect

    from app.core import lane_engine

    source = inspect.getsource(lane_engine)
    assert "time.time(" not in source
    assert "datetime.now(" not in source


def test_pause_does_not_increase_wait_no_update_calls():
    """Пауза обработки = отсутствие вызовов update(). Раз состояние меняется
    только внутри update(now, ...), отсутствие вызовов не меняет avg_wait_sec
    при повторном снимке с тем же video_time."""
    profile = make_profile()
    engine = AnalyticsEngine(profile, W, H)
    bbox_still = (450, 450, 550, 550)
    for t in [0.0, 0.5, 1.0, 1.5, 2.0, 2.1]:
        engine.update(t, [det(1, bbox_still)])
    snap1 = engine.snapshot(2.1)
    # "Пауза" — просто не вызываем update(). Повторный снимок на том же
    # video_time обязан совпадать (здесь video_time не продвинулся).
    snap2 = engine.snapshot(2.1)
    assert snap1["lanes"][0]["avg_wait_sec"] == snap2["lanes"][0]["avg_wait_sec"]


def test_crossing_counted_once_per_track():
    profile = make_profile()
    engine = AnalyticsEngine(profile, W, H)
    # Линия на x=0.5 (px 500). Машина идёт слева направо через линию, потом
    # туда-сюда дёргается около неё (дрожание) — должно засчитаться максимум
    # один раз для этого трека.
    positions = [
        (300, 450, 400, 550),  # слева от линии
        (480, 450, 580, 550),  # пересекла (center ~530 > 500)
        (470, 450, 570, 550),  # чуть назад (center ~520, всё ещё > 500 на самом деле)
        (430, 450, 530, 550),  # назад за линию (center ~480 < 500) — обратный переход, но direction=positive не считает
        (480, 450, 580, 550),  # снова вперёд — уже засчитан трек, повторно не считаем
    ]
    for i, bbox in enumerate(positions):
        engine.update(i * 0.3, [det(1, bbox)])
    snap = engine.snapshot(len(positions) * 0.3)
    assert snap["lanes"][0]["total_crossings"] == 1


def test_lane_assignment_hysteresis_prevents_flicker():
    """Полоса покрывает (0.1..0.9); вне полосы — unassigned. Короткий выход
    за границу на один кадр не должен мгновенно "сбрасывать" назначение —
    требуется lane_switch_hysteresis_sec непрерывного наблюдения снаружи."""
    profile = make_profile(lane_switch_hysteresis_sec=0.5)
    engine = AnalyticsEngine(profile, W, H)
    inside = (450, 450, 550, 550)
    outside = (-100, 450, -50, 550)  # вне полосы (x<0.1*W)

    engine.update(0.0, [det(1, inside)])
    assert engine.tracks[1].assigned_lane == "lane_1"

    # Кратковременно вышел на 0.1с — меньше порога гистерезиса.
    engine.update(0.1, [det(1, outside)])
    assert engine.tracks[1].assigned_lane == "lane_1"

    engine.update(0.2, [det(1, inside)])
    assert engine.tracks[1].assigned_lane == "lane_1"


def test_coordinate_scaling_consistent_across_resolutions():
    """Нормированные координаты профиля должны давать одинаковый результат
    привязки к полосе независимо от фактического разрешения кадра (при том
    же соотношении сторон) — разметка не должна "съезжать" при масштабировании."""
    profile = make_profile()
    engine_small = AnalyticsEngine(profile, 500, 500)
    engine_large = AnalyticsEngine(profile, 2000, 2000)

    # Одна и та же относительная позиция (50% ширины/высоты) в обоих масштабах.
    bbox_small = (240, 240, 260, 260)  # center ~ (250,250) из 500 = 50%
    bbox_large = (960, 960, 1040, 1040)  # center ~ (1000,1000) из 2000 = 50%

    engine_small.update(0.0, [det(1, bbox_small)])
    engine_large.update(0.0, [det(1, bbox_large)])

    assert engine_small.tracks[1].assigned_lane == "lane_1"
    assert engine_large.tracks[1].assigned_lane == "lane_1"


def test_queue_zone_polygon_must_be_inside_observation_polygon():
    with pytest.raises(Exception):
        Lane(
            id="bad",
            name="Плохая полоса",
            color="#ffffff",
            observation_polygon=Polygon(
                points=[Point(x=0.1, y=0.1), Point(x=0.3, y=0.1), Point(x=0.3, y=0.3), Point(x=0.1, y=0.3)]
            ),
            queue_zone_polygon=Polygon(
                # зона очереди снаружи полигона наблюдения
                points=[Point(x=0.5, y=0.5), Point(x=0.6, y=0.5), Point(x=0.6, y=0.6), Point(x=0.5, y=0.6)]
            ),
            count_line=CountLine(
                p1=Point(x=0.1, y=0.1), p2=Point(x=0.3, y=0.3), positive_side_point=Point(x=0.9, y=0.1)
            ),
        )


def test_stationary_jitter_does_not_block_queue_detection():
    """Регрессия на реальный баг, найденный на настоящем видео: детектор даёт
    небольшое дрожание рамки кадр к кадру даже у припаркованной машины. При
    коротком окне сглаживания (доли секунды) это дрожание, делённое на
    крошечный интервал времени, превращается в скорость, намного превышающую
    пороги — машина никогда не накапливает stop_duration_threshold_sec
    непрерывного "стояния" и не считается в очереди. Симулируем машину,
    которая реально стоит на месте (без тренда), но с шумом в несколько
    пикселей на кадр при 60 к/с — так же, как в реальном трекинге."""
    import random

    profile = make_profile()
    engine = AnalyticsEngine(profile, W, H)

    rng = random.Random(42)
    base_x, base_y = 500.0, 500.0
    box_w, box_h = 100.0, 100.0
    fps = 60.0

    for frame_idx in range(int(4.0 * fps)):  # 4 секунды видео, кадр за кадром
        t = frame_idx / fps
        jx = rng.uniform(-1.5, 1.5)  # дрожание рамки на несколько пикселей
        jy = rng.uniform(-1.5, 1.5)
        x1 = base_x - box_w / 2 + jx
        y1 = base_y - box_h / 2 + jy
        bbox = (x1, y1, x1 + box_w, y1 + box_h)
        engine.update(t, [det(1, bbox)])

    track = engine.tracks[1]
    assert track.queue_state == "waiting", (
        "Машина физически стоит на месте 4 секунды подряд (только дрожание "
        "детектора в пределах ±1.5px) — она обязана попасть в очередь, а не "
        "вечно считаться 'движущейся' из-за усиленного шума."
    )
    snap = engine.snapshot(4.0 * fps / fps)
    assert snap["lanes"][0]["queued"] == 1


def test_jitter_across_thin_zone_boundary_does_not_block_queue_detection():
    """Второй реальный баг, найденный на настоящем видео: машина стояла почти
    точно на границе (тонкой) зоны очереди. Проверка "внутри/снаружи" по сырой
    точке текущего кадра мигала true/false от обычного дрожания в 1-2px,
    хотя скорость уже была корректно около нуля — непрерывность "внутри зоны"
    никогда не набиралась. Симулируем машину чуть внутри границы (x=205 при
    границе зоны x=200), с дрожанием ±8px, пересекающим границу каждый
    второй кадр — но без тренда, то есть "истинная" позиция внутри зоны."""
    import random

    profile = make_profile()
    engine = AnalyticsEngine(profile, W, H)
    rng = random.Random(7)
    fps = 60.0
    box_w = box_h = 100.0

    for frame_idx in range(int(4.0 * fps)):
        t = frame_idx / fps
        jx = rng.uniform(-8, 8)  # дрожание, регулярно уводящее точку за x=200 (границу зоны)
        jy = rng.uniform(-1.5, 1.5)
        cx = 205 + jx
        cy = 500 + jy
        bbox = (cx - box_w / 2, cy - box_h / 2, cx + box_w / 2, cy + box_h / 2)
        engine.update(t, [det(1, bbox)])

    track = engine.tracks[1]
    assert track.queue_state == "waiting", (
        "Истинная позиция машины внутри зоны очереди (x=205 > границы x=200), "
        "дрожание детектора не должно мешать накоплению непрерывного 'внутри "
        "зоны' через усреднённую точку."
    )


def test_polygon_rejects_self_intersection():
    with pytest.raises(Exception):
        Polygon(
            points=[
                Point(x=0.0, y=0.0), Point(x=1.0, y=1.0),
                Point(x=1.0, y=0.0), Point(x=0.0, y=1.0),
            ]
        )
