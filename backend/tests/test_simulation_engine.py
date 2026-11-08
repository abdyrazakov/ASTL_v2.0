"""Модель движения и аналитика этапа 2: детерминизм, пауза, очередь/ожидание,
формат снимка (совместимость с этапом 1), sanity-сравнение режимов, валидация профиля."""
import inspect
import time

import pytest

from app.simulation import engine as engine_module
from app.simulation.engine import Simulation
from app.simulation.models import IntersectionProfile, check_profile
from app.simulation.signals import GREEN
from app.simulation.templates import TEMPLATES, build_template
from app.simulation.worker import SimulationWorker

STAGE1_LANE_FIELDS = {
    "lane_id", "name", "color", "vehicles", "queued", "queue_truncated_by_frame",
    "avg_wait_sec", "max_wait_sec", "wait_sample_size", "flow_count_window",
    "flow_window_available_sec", "flow_window_target_sec", "total_crossings", "vehicle_types",
}


def with_scenario(key: str, lane: str, mult: float = 3.0) -> IntersectionProfile:
    d = build_template(key).model_dump(mode="json")
    d["traffic"]["scenario"] = [{"start_sec": 600, "end_sec": 1500, "lane_ids": [lane], "multiplier": mult}]
    return IntersectionProfile.model_validate(d)


def single_lane_profile(rate=0.0, **timings) -> IntersectionProfile:
    t = {"min_green_sec": 10, "max_green_sec": 30, "yellow_sec": 3, "all_red_clearance_sec": 2,
         "startup_all_red_sec": 3, "max_red_wait_sec": 120}
    t.update(timings)
    return IntersectionProfile.model_validate({
        "name": "single",
        "approaches": [{"id": "n", "name": "N", "heading": "N"}, {"id": "e", "name": "E", "heading": "E"}],
        "lanes": [
            {"id": "a", "approach_id": "n", "index": 0, "name": "A", "movements": ["straight"],
             "arrival_rate_vph": rate, "length_m": 150},
            {"id": "b", "approach_id": "e", "index": 0, "name": "B", "movements": ["straight"],
             "arrival_rate_vph": 0, "length_m": 150},
        ],
        "signal_groups": [
            {"id": "ga", "name": "A", "movements": [{"lane_id": "a", "movement": "straight"}]},
            {"id": "gb", "name": "B", "movements": [{"lane_id": "b", "movement": "straight"}]},
        ],
        "conflicts": {"ga": ["gb"], "gb": ["ga"]},
        "phases": [
            {"id": "pa", "name": "A", "signal_groups": ["ga"], "fixed_green_sec": 20},
            {"id": "pb", "name": "B", "signal_groups": ["gb"], "fixed_green_sec": 20},
        ],
        "phase_order": ["pb", "pa"],  # сначала зелёный B — машина A встретит красный
        "timings": t,
    })


# ---------------------------------------------------------------- детерминизм


@pytest.mark.parametrize("key", list(TEMPLATES))
@pytest.mark.parametrize("mode", ["fixed", "adaptive"])
def test_same_seed_gives_identical_trajectories_and_metrics(key, mode):
    p = build_template(key)
    a, b = Simulation(p, mode, seed=11), Simulation(p, mode, seed=11)
    for _ in range(6000):
        a.step()
        b.step()
        assert a.trajectory_state() == b.trajectory_state()
        assert a.machine.signals == b.machine.signals
    assert a.summary() == b.summary()
    assert a.snapshot() == b.snapshot()


def test_different_seed_gives_different_traffic():
    p = build_template("four_way_simple")
    a, b = Simulation(p, "fixed", seed=1), Simulation(p, "fixed", seed=2)
    a.run_until(600)
    b.run_until(600)
    assert a.trajectory_state() != b.trajectory_state()


def test_arrivals_identical_between_fixed_and_adaptive():
    """Генератор трафика не зависит от управления: при одном seed в обоих режимах
    приходят одни и те же машины (иначе сравнение режимов было бы нечестным)."""
    p = build_template("four_way_protected_left")
    runs = {}
    for mode in ("fixed", "adaptive"):
        sim = Simulation(p, mode, seed=9)
        arrivals = set()
        for _ in range(12_000):
            sim.step()
            for rt in sim.lanes.values():
                for v in rt.vehicles:
                    arrivals.add((rt.lane_id, round(v.arrival_time, 9), v.cls, v.movement))
        runs[mode] = {lid: (rt.arrivals, dict(rt.seen_classes)) for lid, rt in sim.lanes.items()}
        runs[mode + "_set"] = arrivals
    assert runs["fixed"] == runs["adaptive"]
    # каждое прибытие, успевшее въехать в обоих прогонах, совпадает по времени/классу/манёвру
    common = runs["fixed_set"] & runs["adaptive_set"]
    assert len(common) > 0.9 * min(len(runs["fixed_set"]), len(runs["adaptive_set"]))


def test_engine_uses_only_model_time():
    """Как в этапе 1: никаких обращений к системным часам в модели."""
    src = inspect.getsource(engine_module)
    for forbidden in ("time.time(", "datetime.now(", "time.monotonic(", "perf_counter("):
        assert forbidden not in src


# ---------------------------------------------------------------- пауза


def test_snapshot_without_steps_is_stable():
    sim = Simulation(build_template("t_junction"), "adaptive", seed=4)
    sim.run_until(300)
    s1 = sim.snapshot()
    s2 = sim.snapshot()
    assert s1 == s2


def test_worker_pause_freezes_model_time_and_waits(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.storage.OUTPUT_DIR", tmp_path)
    w = SimulationWorker("pause_test", build_template("four_way_protected_left"), "fixed",
                         seed=3, duration_sec=None, speed=50)
    w.start()
    try:
        deadline = time.time() + 10
        while w.sim.time_sec < 60 and time.time() < deadline:
            time.sleep(0.05)
        w.pause()
        time.sleep(0.1)  # дать текущей пачке тиков завершиться
        snap1 = w.snapshot()
        t1 = w.progress()["sim_time_sec"]
        time.sleep(1.0)  # = 50 с модельного времени при ×50, если бы пауза не работала
        snap2 = w.snapshot()
        assert w.progress()["sim_time_sec"] == t1
        assert snap1 == snap2  # в т.ч. avg/max ожидания не выросли
        assert any(lane["wait_sample_size"] > 0 for lane in snap1["lanes"])
        w.resume()
        time.sleep(0.5)
        assert w.progress()["sim_time_sec"] > t1
    finally:
        w.stop()
        w._thread.join(timeout=10)
    assert w.status.value == "stopped"


def test_result_independent_of_speed_and_pauses(tmp_path, monkeypatch):
    """Тот же seed: прогон «как можно быстрее» и прогон в реальном времени ×200
    с паузами дают одинаковые итоги и одинаковый отпечаток траекторий."""
    monkeypatch.setattr("app.core.storage.OUTPUT_DIR", tmp_path)
    p = build_template("t_junction")
    fast = SimulationWorker("fast", p, "adaptive", seed=21, duration_sec=120, headless=True)
    fast.run_blocking()
    rt = SimulationWorker("realtime", p, "adaptive", seed=21, duration_sec=120, speed=200)
    rt.start()
    for _ in range(3):
        time.sleep(0.12)
        rt.pause()
        time.sleep(0.1)
        rt.resume()
    rt._thread.join(timeout=20)
    assert rt.status.value == "completed"
    a, b = fast.sim.summary(), rt.sim.summary()
    assert a["totals"] == b["totals"]
    assert a["lanes"] == b["lanes"]
    assert a["trajectory_digest"] == b["trajectory_digest"]


# ---------------------------------------------------------------- очередь / ожидание


def test_single_vehicle_stops_on_red_waits_then_departs():
    p = single_lane_profile(rate=0.0)
    sim = Simulation(p, "fixed", seed=0)
    # подсовываем одно прибытие в t=1 с
    from app.simulation.engine import PendingArrival
    sim.lanes["a"].backlog.append(PendingArrival(1.0, "car", "straight"))
    sim.lanes["a"].arrivals = 1
    sim.lanes["a"].seen_classes["car"] = 1
    v = None
    stopped_at = None
    while sim.time_sec < 120:
        sim.step()
        if sim.lanes["a"].vehicles:
            v = sim.lanes["a"].vehicles[0]
        if v is not None and v.state == "waiting" and stopped_at is None:
            stopped_at = sim.time_sec
            assert sim.machine.signals["ga"] != GREEN
            assert v.pos == pytest.approx(150.0, abs=1.0)  # у стоп-линии
            snap = sim.lane_snapshot(sim.lanes["a"], sim.time_sec)
            assert snap["queued"] == 1 and snap["vehicles"] == 1
        if v is not None and not v.crossed:
            assert v.pos <= 150.0 or sim.machine.signals["ga"] != "red"
        if v is not None and v.crossed:
            break
    assert stopped_at is not None and v.crossed
    green_a = next(t["t"] for t in sim.machine.transitions if t["to"] == "GREEN" and t["phase"] == "pa")
    rt = sim.lanes["a"]
    assert rt.departed == 1 and rt.sum_stops == 1
    # ожидание = от остановки до проезда стоп-линии, полное (не «наблюдаемое»)
    assert rt.sum_wait_departed == pytest.approx(v.cross_time - v.queue_join_time)
    assert v.cross_time >= green_a
    free_flow = 150.0 / v.vmax
    assert rt.sum_delay == pytest.approx(v.cross_time - 1.0 - free_flow, abs=1e-6)
    snap = sim.lane_snapshot(rt, sim.time_sec)
    assert snap["departed_count"] == 1
    assert snap["stops_per_vehicle"] == 1.0
    assert snap["total_crossings"] == 1
    assert snap["queued"] == 0


def test_vehicle_on_green_does_not_stop_and_has_no_delay():
    p = single_lane_profile(rate=0.0)
    p = p.model_copy(update={"phase_order": ["pa", "pb"]})
    sim = Simulation(p, "fixed", seed=0)
    from app.simulation.engine import PendingArrival
    sim.run_until(3.5)  # зелёный A с 3.0 с
    sim.lanes["a"].backlog.append(PendingArrival(3.5, "car", "straight"))
    sim.run_until(20)
    rt = sim.lanes["a"]
    assert rt.departed == 1
    assert rt.sum_stops == 0
    assert rt.sum_delay < 0.2  # только дискретизация шага


def test_queue_waits_are_full_and_do_not_reset_when_creeping():
    """Ожидание в эпизоде очереди не обнуляется, когда очередь подползает."""
    sim = Simulation(with_scenario("four_way_simple", "e1", 3.0), "fixed", seed=1)
    joins: dict[int, float] = {}
    for _ in range(9000):
        sim.step()
        for rt in sim.lanes.values():
            for v in rt.vehicles:
                if v.queue_join_time is not None:
                    if v.vid in joins:
                        assert joins[v.vid] == v.queue_join_time
                    joins[v.vid] = v.queue_join_time
    assert len(joins) > 100


def test_snapshot_keeps_stage1_fields_and_adds_stage2_fields():
    sim = Simulation(build_template("four_way_protected_left"), "adaptive", seed=2)
    sim.run_until(600)
    snap = sim.snapshot()
    assert snap["schema_version"] == "1.1"
    for k in ("timestamp_sec", "lanes", "controller_mode", "active_phase", "phase_remaining_sec"):
        assert k in snap
    for lane in snap["lanes"]:
        assert STAGE1_LANE_FIELDS <= set(lane)
        for k in ("avg_delay_sec", "stops_per_vehicle", "throughput_per_hour"):
            assert k in lane
        assert lane["queued"] <= lane["vehicles"]
        assert lane["wait_sample_size"] >= lane["queued"]
        assert lane["max_wait_sec"] >= lane["avg_wait_sec"]
        assert set(lane["vehicle_types"]) <= {"car", "bus", "truck", "motorcycle"}
        assert lane["flow_count_window"] <= lane["total_crossings"]


def test_metrics_are_internally_consistent():
    sim = Simulation(build_template("t_junction"), "adaptive", seed=6)
    sim.run_until(1800)
    totals = sim.totals()
    lanes = [sim.lane_snapshot(rt, sim.time_sec) for rt in sim.lanes.values()]
    assert totals["departed"] == sum(lane["total_crossings"] for lane in lanes)
    for rt in sim.lanes.values():
        in_system = len([v for v in rt.vehicles if not v.crossed]) + len(rt.backlog)
        assert rt.arrivals == rt.departed + in_system
        assert sum(rt.seen_classes.values()) == rt.arrivals
    weighted = sum(rt.sum_delay for rt in sim.lanes.values()) / totals["departed"]
    assert totals["avg_delay_sec"] == pytest.approx(weighted, abs=0.01)


# ---------------------------------------------------------------- sanity: адаптивный vs фиксированный


@pytest.mark.parametrize(
    "key,lane", [("four_way_simple", "e1"), ("four_way_protected_left", "w2"), ("t_junction", "s1")]
)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_adaptive_not_worse_on_one_sided_burst(key, lane, seed):
    """Синтетический всплеск ×3 на одной полосе: адаптивный режим даёт не худшую
    среднюю задержку на этой полосе, чем фиксированный цикл на том же seed.
    Это sanity-проверка, а не доказательство оптимальности."""
    p = with_scenario(key, lane, 3.0)
    res = {}
    for mode in ("fixed", "adaptive"):
        sim = Simulation(p, mode, seed=seed)
        sim.run_until(2400)
        res[mode] = sim.summary()["lanes"][lane]["avg_delay_sec"]
    assert res["adaptive"] <= res["fixed"], res


# ---------------------------------------------------------------- валидация профиля


def _data(key="four_way_simple"):
    return build_template(key).model_dump(mode="json")


def _errors(d) -> str:
    with pytest.raises(ValueError) as exc:
        IntersectionProfile.model_validate(d)
    return str(exc.value)


def test_templates_are_valid():
    for key in TEMPLATES:
        errors, warnings = check_profile(build_template(key))
        assert errors == [] and warnings == []


def test_asymmetric_conflict_matrix_rejected():
    d = _data()
    d["conflicts"]["g_n"] = [g for g in d["conflicts"]["g_n"] if g != "g_e"]
    assert "несимметрична" in _errors(d)


def test_self_conflict_rejected():
    d = _data()
    d["conflicts"]["g_n"].append("g_n")
    assert "сама с собой" in _errors(d)


def test_phase_with_conflicting_groups_rejected():
    d = _data()
    d["phases"][0]["signal_groups"] = ["g_n", "g_e"]
    assert "конфликтующие группы" in _errors(d)


def test_group_not_in_any_phase_rejected():
    d = _data()
    d["phases"][1]["signal_groups"] = ["g_e"]
    assert "не входит ни в одну фазу" in _errors(d)


def test_lane_with_traffic_without_group_rejected_but_zero_rate_only_warns():
    d = _data()
    d["signal_groups"][0]["movements"] = [{"lane_id": "n1", "movement": "straight"}]  # без «направо»
    assert "никогда не проедут" in _errors(d)
    d["lanes"][0]["arrival_rate_vph"] = 0
    errors, warnings = check_profile(IntersectionProfile.model_validate(d))
    assert errors == [] and any("не привязан" in w for w in warnings)


def test_movement_controlled_by_two_groups_rejected():
    d = _data()
    d["signal_groups"][1]["movements"].append({"lane_id": "n1", "movement": "straight"})
    assert "сразу двумя" in _errors(d)


def test_timing_validation():
    d = _data()
    d["timings"]["min_green_sec"] = 30
    d["timings"]["max_green_sec"] = 20
    assert "больше max_green" in _errors(d)
    d = _data()
    d["phases"][0]["fixed_green_sec"] = 60
    assert "вне диапазона" in _errors(d)
    d = _data()
    d["timings"]["max_red_wait_sec"] = 15
    assert "max_red_wait_sec" in _errors(d)
    d = _data()
    d["timings"]["yellow_sec"] = -1
    with pytest.raises(ValueError):
        IntersectionProfile.model_validate(d)


def test_single_phase_rejected():
    d = _data()
    d["conflicts"] = {}
    d["phases"] = [{"id": "p", "name": "all", "signal_groups": ["g_n", "g_s", "g_e", "g_w"], "fixed_green_sec": 20}]
    d["phase_order"] = ["p"]
    assert "минимум две фазы" in _errors(d)


def test_transitions_must_allow_cycle_and_warn_if_incomplete():
    d = _data("four_way_protected_left")
    d["transitions"] = {"p_ns_t": ["p_ns_l"], "p_ns_l": ["p_ew_t"], "p_ew_t": ["p_ew_l"], "p_ew_l": ["p_ns_t"]}
    errors, warnings = check_profile(IntersectionProfile.model_validate(d))
    assert errors == [] and any("кратчайшему пути" in w for w in warnings)
    d["transitions"]["p_ew_t"] = ["p_ns_t"]
    assert "не разрешён" in _errors(d)


def test_restricted_transitions_respected_by_adaptive():
    d = _data("four_way_protected_left")
    d["transitions"] = {"p_ns_t": ["p_ns_l"], "p_ns_l": ["p_ew_t"], "p_ew_t": ["p_ew_l"], "p_ew_l": ["p_ns_t"]}
    p = IntersectionProfile.model_validate(d)
    sim = Simulation(p, "adaptive", seed=3)
    sim.run_until(3600)
    log = sim.machine.green_log
    assert len(log) > 20 and sim.machine.fault_count == 0
    for g in log:
        assert g["next_phase"] in d["transitions"][g["phase_id"]]


def test_durations_are_quantized_to_model_step():
    d = _data()
    d["timings"]["gap_out_sec"] = 2.34
    d["phases"][0]["fixed_green_sec"] = 25.06
    p = IntersectionProfile.model_validate(d)
    assert p.timings.gap_out_sec == 2.3
    assert p.phases[0].fixed_green_sec == 25.1
