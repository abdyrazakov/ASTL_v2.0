"""Шаблоны перекрёстков: валидность, корректность матриц конфликтов, безопасная работа."""
import pytest

from app.simulation.engine import Simulation
from app.simulation.models import check_profile
from app.simulation.templates import TEMPLATES, build_template, template_info
from app.simulation.templates_extra import EXTRA_TEMPLATES, derive_conflicts, exit_side, movement_conflict

HAND_WRITTEN = ["four_way_simple", "four_way_protected_left", "t_junction"]


@pytest.mark.parametrize("key", HAND_WRITTEN)
def test_rule_table_reproduces_hand_written_matrices(key):
    """Таблица правил, по которой подготовлены матрицы новых шаблонов, на трёх
    исходных шаблонах даёт ровно их матрицы, написанные вручную."""
    data = TEMPLATES[key][1]()
    assert derive_conflicts(data) == data["conflicts"]


def test_rule_table_basic_cases():
    assert exit_side("N", "straight") == "S" and exit_side("N", "left") == "E" and exit_side("N", "right") == "W"
    assert not movement_conflict("N", "straight", "N", "left")      # один подход
    assert not movement_conflict("N", "straight", "S", "straight")  # встречные прямые
    assert not movement_conflict("N", "left", "S", "left")          # встречные левые
    assert movement_conflict("N", "left", "S", "straight")          # левый через встречный прямой
    assert movement_conflict("N", "straight", "E", "straight")      # перпендикулярные пересекаются
    assert movement_conflict("N", "right", "E", "straight")         # слияние в западный выезд
    assert not movement_conflict("N", "right", "E", "left")         # правый огибает угол
    assert movement_conflict("N", "left", "S", "right")             # слияние в восточный выезд


@pytest.mark.parametrize("key", list(TEMPLATES))
def test_template_valid_and_described(key):
    p = build_template(key)
    errors, warnings = check_profile(p)
    assert errors == [] and warnings == []
    info = {t["key"]: t for t in template_info()}[key]
    assert info["name"] and len(info["description"]) > 20


@pytest.mark.parametrize("key", list(TEMPLATES))
def test_no_crossing_movements_inside_any_phase(key):
    """Независимая от матрицы проверка: внутри каждой фазы нет двух манёвров,
    которые по правилам правостороннего движения пересекаются или сливаются."""
    p = build_template(key)
    heading = {a.id: a.heading.value for a in p.approaches}
    lane_h = {lane.id: heading[lane.approach_id] for lane in p.lanes}
    groups = {g.id: g for g in p.signal_groups}
    for ph in p.phases:
        movs = [(lane_h[lm.lane_id], lm.movement.value) for gid in ph.signal_groups for lm in groups[gid].movements]
        for i, a in enumerate(movs):
            for b in movs[i + 1:]:
                assert not movement_conflict(*a, *b), f"{key}/{ph.id}: {a} × {b}"


def test_extra_templates_are_diverse():
    """Новые шаблоны действительно разные: число подходов, полос, фаз и групп."""
    shapes = set()
    for key in EXTRA_TEMPLATES:
        p = build_template(key)
        per_approach = tuple(sorted(len([l for l in p.lanes if l.approach_id == a.id]) for a in p.approaches))
        shapes.add((len(p.approaches), per_approach, len(p.phases), len(p.signal_groups)))
    assert len(shapes) >= 6
    assert any(max(per) >= 3 for _, per, _, _ in shapes)  # есть 3+ полосные подходы
    overlap = build_template("t_junction_three_lane")
    counts = {g.id: sum(g.id in ph.signal_groups for ph in overlap.phases) for g in overlap.signal_groups}
    assert max(counts.values()) >= 2  # группа входит в несколько фаз


@pytest.mark.parametrize("key", list(EXTRA_TEMPLATES))
@pytest.mark.parametrize("mode", ["fixed", "adaptive"])
def test_extra_templates_run_safely(key, mode):
    sim = Simulation(build_template(key), mode, seed=4)
    for _ in range(9000):
        sim.step()
        perm = {g for g, c in sim.machine.signals.items() if c in ("green", "yellow")}
        assert not any(pair <= perm for pair in sim.machine.conflicts)
    s = sim.safety()
    assert s["blocked_violations"] == 0 and s["faults"] == 0 and s["red_clamps"] == 0
    assert sim.departed_total > 100
