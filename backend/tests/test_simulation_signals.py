"""Автомат сигналов этапа 2: безопасность конфликтов, точность таймингов,
защита от голодания, реакция на ошибки (FAULT)."""
import random

import pytest

from app.simulation.controllers import (
    AdaptiveController,
    BaseController,
    Decision,
    DemandView,
    FixedTimeController,
)
from app.simulation.engine import Simulation
from app.simulation.models import IntersectionProfile
from app.simulation.signals import ALLOWED_TRANSITIONS, GREEN, RED, YELLOW, SignalMachine, SignalState
from app.simulation.templates import TEMPLATES, build_template

HEADINGS = ["N", "E", "S", "W"]


# ---------------------------------------------------------------- генераторы


def random_profile(rng: random.Random) -> IntersectionProfile:
    """Случайный валидный профиль: случайная симметричная матрица конфликтов,
    фазы — случайные независимые множества групп, покрывающие все группы."""
    n_groups = rng.randint(2, 8)
    approaches = [{"id": h.lower(), "name": h, "heading": h} for h in HEADINGS]
    lanes, groups = [], []
    for i in range(n_groups):
        h = HEADINGS[i % 4]
        lid = f"l{i}"
        lanes.append({"id": lid, "approach_id": h.lower(), "index": i // 4, "name": lid,
                      "movements": ["straight"], "length_m": 120,
                      "arrival_rate_vph": rng.choice([0, 100, 300, 600, 900])})
        groups.append({"id": f"g{i}", "name": f"g{i}", "movements": [{"lane_id": lid, "movement": "straight"}]})
    gids = [g["id"] for g in groups]
    conflicts: dict[str, list[str]] = {g: [] for g in gids}
    for i in range(n_groups):
        for j in range(i + 1, n_groups):
            if rng.random() < 0.5:
                conflicts[gids[i]].append(gids[j])
                conflicts[gids[j]].append(gids[i])
    # жадно строим фазы — независимые множества, пока все группы не покрыты
    uncovered = list(gids)
    phases = []
    while uncovered:
        seed_g = rng.choice(uncovered)
        members = [seed_g]
        for g in rng.sample(gids, len(gids)):
            if g not in members and all(g not in conflicts[m] for m in members) and rng.random() < 0.7:
                members.append(g)
        phases.append(members)
        uncovered = [g for g in uncovered if g not in members]
    if len(phases) == 1:  # профиль обязан иметь ≥ 2 фаз — отделяем одну группу
        phases = [phases[0][1:], [phases[0][0]]]
    t_min =rng.choice([3.0, 5.0, 7.0])
    t_max = t_min + rng.choice([0.0, 5.0, 20.0, 40.0])
    yellow = rng.choice([3.0, 3.5, 4.0])
    all_red = rng.choice([0.5, 1.0, 2.0])
    phase_objs = [
        {"id": f"p{k}", "name": f"p{k}", "signal_groups": m,
         "fixed_green_sec": round(rng.uniform(t_min, t_max), 1)}
        for k, m in enumerate(phases)
    ]
    return IntersectionProfile.model_validate({
        "name": "random",
        "approaches": approaches,
        "lanes": lanes,
        "signal_groups": groups,
        "conflicts": conflicts,
        "phases": phase_objs,
        "phase_order": [p["id"] for p in phase_objs],
        "timings": {"min_green_sec": t_min, "max_green_sec": t_max, "yellow_sec": yellow,
                    "all_red_clearance_sec": all_red, "startup_all_red_sec": rng.choice([1.0, 3.0]),
                    "gap_out_sec": rng.choice([1.0, 2.5, 4.0]),
                    "max_red_wait_sec": t_min + 2 * (yellow + all_red) + rng.choice([0.0, 10.0, 60.0])},
        "traffic": {"seed": rng.randint(0, 10_000)},
    })


class ChaosController(BaseController):
    """Случайные решения: автомат обязан быть безопасным при ЛЮБОМ поведении
    контроллера, а не только при «правильном»."""

    mode = "chaos"

    def __init__(self, profile, rng):
        super().__init__(profile)
        self.rng = rng

    def initial_phase(self, demand):
        return self.rng.choice(self.profile.phase_order)

    def decide(self, m, demand):
        if self.rng.random() < 0.2:
            return Decision(True, "chaos", self.rng.choice(self.profile.allowed_next(m.phase)))
        return Decision(False)

    def choose_next(self, m, demand):
        return self.rng.choice(self.profile.allowed_next(m.phase)), "chaos"


def assert_safe(machine: SignalMachine):
    perm = {g for g, c in machine.signals.items() if c in (GREEN, YELLOW)}
    for pair in machine.conflicts:
        assert not pair <= perm, f"конфликт {set(pair)} одновременно разрешён в {machine.state}"


def assert_signals_match_state(machine: SignalMachine):
    s = machine.state
    if s in (SignalState.GREEN, SignalState.YELLOW):
        expected = GREEN if s == SignalState.GREEN else YELLOW
        phase_groups = set(machine.profile.phase(machine.phase).signal_groups)
        for g, c in machine.signals.items():
            assert c == (expected if g in phase_groups else RED)
    else:
        assert all(c == RED for c in machine.signals.values())


def transition_durations(machine: SignalMachine) -> list[tuple[str, str | None, int]]:
    """(состояние, фаза, длительность в тиках) для всех завершённых интервалов."""
    tr = machine.transitions
    return [(a["to"], a["phase"], b["tick"] - a["tick"]) for a, b in zip(tr, tr[1:])]


# ---------------------------------------------------------------- безопасность


@pytest.mark.parametrize("seed", range(150))
def test_conflict_safety_random_profiles_chaos_controller(seed):
    """Случайный профиль + случайный контроллер: ни на одном тике две
    конфликтующие группы не разрешены одновременно, переходы — только по таблице."""
    rng = random.Random(seed)
    profile = random_profile(rng)
    m = SignalMachine(profile, ChaosController(profile, rng))
    prev_state = m.state
    for _ in range(3000):
        m.step(DemandView())
        assert_safe(m)
        assert_signals_match_state(m)
        if m.state != prev_state:
            assert m.state in ALLOWED_TRANSITIONS[prev_state]
            prev_state = m.state
    assert m.fault_count == 0  # хаотичный, но допустимый контроллер не вызывает FAULT
    assert m.blocked_violations == 0


@pytest.mark.parametrize("seed", range(30))
@pytest.mark.parametrize("mode", ["fixed", "adaptive"])
def test_conflict_safety_full_simulation_random_profiles(seed, mode):
    """Полная симуляция (трафик + реальные контроллеры) на случайных профилях."""
    rng = random.Random(10_000 + seed)
    profile = random_profile(rng)
    sim = Simulation(profile, mode, seed=seed)
    for _ in range(4000):
        sim.step()
        assert_safe(sim.machine)
        assert_signals_match_state(sim.machine)
        for rt in sim.lanes.values():  # машины не накладываются друг на друга
            for a, b in zip(rt.vehicles, rt.vehicles[1:]):
                assert b.pos <= a.pos - a.length - sim.min_gap + 1e-6
    assert sim.red_clamps == 0
    assert sim.machine.fault_count == 0


@pytest.mark.parametrize("key", list(TEMPLATES))
@pytest.mark.parametrize("seed", range(5))
def test_conflict_safety_templates_with_mode_switching(key, seed):
    """Шаблоны, оба контроллера и переключение режима на лету каждые 5 мин."""
    sim = Simulation(build_template(key), "adaptive", seed=seed)
    rng = random.Random(seed)
    for i in range(12_000):
        if i % 3000 == 1500:
            sim.set_controller_mode(rng.choice(["fixed", "adaptive"]))
        sim.step()
        assert_safe(sim.machine)
    assert sim.machine.fault_count == 0
    assert sim.red_clamps == 0


def _template_with_bad_phase() -> IntersectionProfile:
    p = build_template("t_junction")
    phases = [ph.model_copy() for ph in p.phases]
    # g_s конфликтует с g_w — такую фазу валидация не пропускает; собираем в обход
    phases[0] = phases[0].model_copy(update={"signal_groups": ["g_w", "g_e", "g_s"]})
    return p.model_copy(update={"phases": phases})


def test_safety_guard_blocks_conflicting_phase_built_around_validation():
    with pytest.raises(ValueError):
        IntersectionProfile.model_validate(_template_with_bad_phase().model_dump())
    bad = _template_with_bad_phase()
    m = SignalMachine(bad, FixedTimeController(bad))
    for _ in range(2000):
        m.step(DemandView())
        assert_safe(m)
    assert m.blocked_violations > 0  # попытка была, но сигналы не выставлены
    assert m.fault_count > 0
    assert any(t["to"] == "FAULT" for t in m.transitions)


class BrokenController(FixedTimeController):
    def __init__(self, profile, fail_at_tick):
        super().__init__(profile)
        self.fail_at = fail_at_tick

    def decide(self, m, demand):
        if m.tick == self.fail_at:
            raise RuntimeError("сбой контроллера")
        if m.tick == self.fail_at + 1000:
            return Decision(True, "bad", "нет_такой_фазы")
        return super().decide(m, demand)


def test_controller_error_goes_to_fault_then_all_red_restart():
    p = build_template("four_way_simple")
    # fail_at попадает в зелёный: startup 3 с + первые 25 с зелёного
    m = SignalMachine(p, BrokenController(p, fail_at_tick=200))
    states, signals = [], []
    for _ in range(3000):
        m.step(DemandView())
        assert_safe(m)
        states.append(m.state)
        signals.append(dict(m.signals))
    assert m.fault_count >= 1
    i = states.index(SignalState.FAULT)
    assert all(c == RED for c in signals[i].values())
    assert states[i + 1] == SignalState.STARTUP_ALL_RED
    # перезапуск: STARTUP_ALL_RED держится ровно startup_all_red_sec, затем снова GREEN
    n_startup = m.ticks(p.timings.startup_all_red_sec)
    assert states[i + 1:i + 1 + n_startup] == [SignalState.STARTUP_ALL_RED] * n_startup
    assert states[i + 1 + n_startup] == SignalState.GREEN


# ---------------------------------------------------------------- тайминги


@pytest.mark.parametrize("key", list(TEMPLATES))
@pytest.mark.parametrize("mode", ["fixed", "adaptive"])
def test_timings_respected_exactly(key, mode):
    p = build_template(key)
    sim = Simulation(p, mode, seed=3)
    sim.run_until(3600)
    m = sim.machine
    t = p.timings
    durs = transition_durations(m)
    assert durs[0] == ("STARTUP_ALL_RED", None, m.ticks(t.startup_all_red_sec))
    greens = [(ph, d) for s, ph, d in durs if s == "GREEN"]
    assert len(greens) > 20
    for s, ph, d in durs:
        if s == "YELLOW":
            assert d == m.ticks(t.yellow_sec)
        elif s == "ALL_RED":
            assert d == m.ticks(t.all_red_clearance_sec)
    for ph, d in greens:
        assert m.ticks(p.min_green(ph)) <= d <= m.ticks(p.max_green(ph))
        if mode == "fixed":
            assert d == m.ticks(p.phase(ph).fixed_green_sec)
    # между зелёными всегда ровно жёлтый, затем all-red
    seq = [s for s, _, _ in durs]
    for i, s in enumerate(seq[:-2]):
        if s == "GREEN":
            assert seq[i + 1:i + 3] == ["YELLOW", "ALL_RED"]
    if mode == "fixed":  # строго циклический порядок
        order = p.phase_order
        phases = [ph for ph, _ in greens]
        for a, b in zip(phases, phases[1:]):
            assert order.index(b) == (order.index(a) + 1) % len(order)


def test_per_phase_min_max_override_respected():
    data = build_template("four_way_simple").model_dump(mode="json")
    data["phases"][1]["min_green_sec"] = 12
    data["phases"][1]["max_green_sec"] = 15
    data["phases"][1]["fixed_green_sec"] = 13
    p = IntersectionProfile.model_validate(data)
    sim = Simulation(p, "adaptive", seed=1)
    sim.run_until(3600)
    seen = 0
    for s, ph, d in transition_durations(sim.machine):
        if s == "GREEN" and ph == "p_ew":
            assert 120 <= d <= 150
            seen += 1
    assert seen > 10


# ---------------------------------------------------------------- голодание


def _two_phase_profile(max_red_wait=40.0, max_green=120.0) -> IntersectionProfile:
    return IntersectionProfile.model_validate({
        "name": "starvation",
        "approaches": [{"id": "n", "name": "N", "heading": "N"}, {"id": "e", "name": "E", "heading": "E"}],
        "lanes": [
            {"id": "a", "approach_id": "n", "index": 0, "name": "A", "movements": ["straight"],
             "arrival_rate_vph": 1900, "length_m": 300},
            {"id": "b", "approach_id": "e", "index": 0, "name": "B", "movements": ["straight"],
             "arrival_rate_vph": 40, "length_m": 150},
        ],
        "signal_groups": [
            {"id": "ga", "name": "A", "movements": [{"lane_id": "a", "movement": "straight"}]},
            {"id": "gb", "name": "B", "movements": [{"lane_id": "b", "movement": "straight"}]},
        ],
        "conflicts": {"ga": ["gb"], "gb": ["ga"]},
        "phases": [
            {"id": "pa", "name": "A", "signal_groups": ["ga"], "fixed_green_sec": 30},
            {"id": "pb", "name": "B", "signal_groups": ["gb"], "fixed_green_sec": 10},
        ],
        "phase_order": ["pa", "pb"],
        "timings": {"min_green_sec": 7, "max_green_sec": max_green, "yellow_sec": 3,
                    "all_red_clearance_sec": 2, "gap_out_sec": 3, "max_red_wait_sec": max_red_wait},
    })


@pytest.mark.parametrize("wait_start_sec", [round(x * 0.7, 1) for x in range(200)])
def test_starvation_guarantee_with_continuous_demand(wait_start_sec):
    """У фазы A непрерывный спрос (детектор срабатывает каждый тик, gap-out
    невозможен, max_green = 120 с). Одна машина группы B встаёт в очередь в
    момент wait_start_sec (перебираем все точки цикла, включая жёлтый/all-red).
    Фаза B обязана получить зелёный не позже max_red_wait_sec с этого момента."""
    p = _two_phase_profile(max_red_wait=40.0, max_green=120.0)
    m = SignalMachine(p, AdaptiveController(p))
    dt = m.dt
    t_wait0 = None
    for _ in range(int(400 / dt)):
        t = m.tick * dt
        demand = DemandView(group_demand={"ga": 50.0}, group_max_wait={"ga": 1.0},
                            group_last_actuation={"ga": m.tick}, group_queue_count={"ga": 40})
        if t >= wait_start_sec and m.signals["gb"] != GREEN:
            if t_wait0 is None:
                t_wait0 = t
            demand.group_demand["gb"] = 1.0
            demand.group_max_wait["gb"] = t - t_wait0
        m.step(demand)  # сигналы, выставленные на интервал, начинающийся в t
        if t_wait0 is not None and m.signals["gb"] == GREEN:
            waited = t - t_wait0
            assert waited <= p.timings.max_red_wait_sec + 1e-9
            return
    pytest.fail("фаза B так и не получила зелёный")


def test_starvation_engine_level_no_red_wait_exceeds_limit():
    """Полная симуляция: пока сигнал группы B не зелёный, ни одна машина B не
    ждёт дольше max_red_wait_sec — при перегруженной фазе A (1900 машин/ч)."""
    p = _two_phase_profile(max_red_wait=40.0, max_green=120.0)
    sim = Simulation(p, "adaptive", seed=5)
    limit = p.timings.max_red_wait_sec
    worst = 0.0
    for _ in range(int(3600 / sim.dt)):
        sim.step()
        now = sim.time_sec
        if sim.machine.signals["gb"] != GREEN:
            for v in sim.lanes["b"].vehicles:
                if not v.crossed and v.queue_join_time is not None:
                    worst = max(worst, now - v.queue_join_time)
                    assert now - v.queue_join_time <= limit + 1e-6
    assert sim.lanes["b"].departed > 10
    assert worst > limit * 0.5  # сценарий действительно доводит до срабатывания защиты


def test_without_starvation_rule_minor_phase_would_wait_too_long():
    """Контроль: при огромном max_red_wait та же фаза B ждёт дольше 40 с —
    значит, предыдущий тест проверяет именно защиту от голодания."""
    p = _two_phase_profile(max_red_wait=600.0, max_green=120.0)
    sim = Simulation(p, "adaptive", seed=5)
    worst = 0.0
    for _ in range(int(1800 / sim.dt)):
        sim.step()
        if sim.machine.signals["gb"] != GREEN:
            for v in sim.lanes["b"].vehicles:
                if not v.crossed and v.queue_join_time is not None:
                    worst = max(worst, sim.time_sec - v.queue_join_time)
    assert worst > 40.0


# ---------------------------------------------------------------- адаптивные правила


def test_adaptive_gap_out_switches_before_max_green_when_no_demand():
    """Активной фазе нечего пропускать, у другой есть спрос — зелёный
    заканчивается сразу после min_green (gap-out), а не по max_green."""
    p = _two_phase_profile(max_red_wait=90.0, max_green=60.0)
    m = SignalMachine(p, AdaptiveController(p))
    while m.state != SignalState.GREEN:
        m.step(DemandView(group_demand={"ga": 1.0}, group_max_wait={"ga": 1.0}))
    assert m.phase == "pa"
    demand = DemandView(group_demand={"gb": 3.0}, group_max_wait={"gb": 5.0})
    while m.state == SignalState.GREEN:
        m.step(demand)
    g = m.green_log[-1]
    assert g["reason"] == "gap_out"
    assert g["duration_sec"] == pytest.approx(max(p.timings.min_green_sec, p.timings.gap_out_sec))
    assert g["next_phase"] == "pb"


def test_adaptive_rests_while_no_other_demand_until_max_green():
    p = _two_phase_profile(max_red_wait=90.0, max_green=30.0)
    m = SignalMachine(p, AdaptiveController(p))
    while m.state != SignalState.YELLOW:
        m.step(DemandView())
    assert m.green_log[-1]["reason"] == "max_out"
    assert m.green_log[-1]["duration_sec"] == pytest.approx(30.0)


def test_adaptive_picks_highest_demand_phase():
    p = build_template("four_way_protected_left")
    m = SignalMachine(p, AdaptiveController(p))
    demand = DemandView(group_demand={"e_l": 2.0, "w_l": 2.0, "n_l": 1.0, "e_t": 0.5},
                        group_max_wait={"e_l": 3.0, "w_l": 3.0, "n_l": 2.0, "e_t": 1.0})
    while m.state != SignalState.GREEN:
        m.step(demand)
    assert m.phase == "p_ew_l"  # после старта — фаза с наибольшим спросом (2 + 2)
    while m.state != SignalState.YELLOW:
        m.step(demand)
    assert m.next_phase == "p_ns_l"  # следующая по спросу среди остальных (1.0 > 0.5)


def test_mode_switch_on_the_fly_keeps_running_interval():
    p = build_template("four_way_simple")
    sim = Simulation(p, "fixed", seed=2)
    sim.run_until(100)
    state_before, phase_before = sim.machine.state, sim.machine.phase
    sim.set_controller_mode("adaptive")
    assert sim.machine.state == state_before and sim.machine.phase == phase_before
    sim.run_until(1000)
    assert sim.controller_mode_switches == [{"t": 100.0, "from": "fixed", "to": "adaptive"}]
    assert sim.machine.fault_count == 0


@pytest.mark.parametrize("threshold,expect_reason", [(2.0, "queue_clear"), (None, "max_out")])
def test_adaptive_queue_clear_rule(threshold, expect_reason):
    """Машины фазы A подъезжают непрерывно (детектор каждый тик — gap-out
    невозможен), но очереди у A нет, а у B ждут 3 машины. С правилом «очистка
    очереди» A уступает сразу после min_green; без него — держит до max_green."""
    data = _two_phase_profile(max_red_wait=600.0, max_green=60.0).model_dump(mode="json")
    data["adaptive"]["queue_clear_min_demand"] = threshold
    p = IntersectionProfile.model_validate(data)
    m = SignalMachine(p, AdaptiveController(p))
    while m.state != SignalState.GREEN:
        m.step(DemandView(group_demand={"ga": 1.0}, group_queue_count={"ga": 1}))
    while m.state == SignalState.GREEN:
        m.step(DemandView(group_demand={"gb": 3.0}, group_max_wait={"gb": 2.0}, group_queue_count={"gb": 3},
                          group_last_actuation={"ga": m.tick}))
    g = m.green_log[-1]
    assert g["reason"] == expect_reason
    expected = p.timings.min_green_sec if threshold else 60.0
    assert g["duration_sec"] == pytest.approx(expected)
