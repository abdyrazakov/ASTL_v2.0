"""Стандартные шаблоны перекрёстков для редактора.

Матрицы конфликтов в шаблонах заданы вручную (как и требует этап 2 — автоматический
вывод конфликтов по геометрии намеренно не делается). Правостороннее движение.
Подход назван по стороне, С КОТОРОЙ приходит транспорт.
"""
from __future__ import annotations

from app.simulation.models import IntersectionProfile

APPROACH_COLORS = {"N": "#2dd4bf", "E": "#38bdf8", "S": "#f5a623", "W": "#a78bfa"}
APPROACH_NAMES = {"N": "Север", "E": "Восток", "S": "Юг", "W": "Запад"}


def _approach(h: str) -> dict:
    return {"id": h.lower(), "name": APPROACH_NAMES[h], "heading": h}


def _lane(h: str, index: int, movements: list[str], rate: float, length: float = 150.0) -> dict:
    return {
        "id": f"{h.lower()}{index + 1}",
        "approach_id": h.lower(),
        "index": index,
        "name": f"{APPROACH_NAMES[h]}-{index + 1}",
        "color": APPROACH_COLORS[h],
        "movements": movements,
        "length_m": length,
        "arrival_rate_vph": rate,
    }


def _conflicts(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for a, b in pairs:
        out.setdefault(a, []).append(b)
        out.setdefault(b, []).append(a)
    return {k: sorted(v) for k, v in out.items()}


def four_way_simple() -> dict:
    """4 подхода, по одной полосе «прямо+направо», две фазы (С–Ю и З–В).

    Левых поворотов нет — поэтому встречные подходы не конфликтуют, и двухфазная
    схема безопасна без моделирования уступания дороги.
    """
    lanes = [
        _lane("N", 0, ["straight", "right"], 420),
        _lane("S", 0, ["straight", "right"], 380),
        _lane("E", 0, ["straight", "right"], 260),
        _lane("W", 0, ["straight", "right"], 240),
    ]
    groups = [
        {"id": f"g_{h}", "name": f"{APPROACH_NAMES[h.upper()]}: прямо+направо",
         "movements": [{"lane_id": f"{h}1", "movement": m} for m in ("straight", "right")]}
        for h in ("n", "s", "e", "w")
    ]
    conflicts = _conflicts([("g_n", "g_e"), ("g_n", "g_w"), ("g_s", "g_e"), ("g_s", "g_w")])
    phases = [
        {"id": "p_ns", "name": "С–Ю", "signal_groups": ["g_n", "g_s"], "fixed_green_sec": 25},
        {"id": "p_ew", "name": "З–В", "signal_groups": ["g_e", "g_w"], "fixed_green_sec": 20},
    ]
    return {
        "name": "4-подходный простой (2 фазы)",
        "template": "four_way_simple",
        "approaches": [_approach(h) for h in "NESW"],
        "lanes": lanes,
        "signal_groups": groups,
        "conflicts": conflicts,
        "phases": phases,
        "phase_order": ["p_ns", "p_ew"],
        "transitions": None,
        "traffic": {
            "seed": 42,
            "scenario_name": "Пик на северном подходе",
            "scenario": [
                {"start_sec": 900, "end_sec": 1800, "lane_ids": ["n1"], "multiplier": 2.0,
                 "label": "пик: север ×2"},
            ],
        },
    }


def four_way_protected_left() -> dict:
    """4 подхода × 2 полосы: левая — только налево, правая — прямо+направо.

    Четыре фазы: С–Ю прямо, С–Ю налево (встречные левые не конфликтуют между собой),
    З–В прямо, З–В налево.
    """
    lanes = []
    rates = {"N": (130, 480), "S": (110, 440), "E": (90, 300), "W": (80, 280)}
    for h in "NSEW":
        left_rate, thru_rate = rates[h]
        lanes.append(_lane(h, 0, ["left"], left_rate))
        lanes.append(_lane(h, 1, ["straight", "right"], thru_rate))
    groups = []
    for h in "nsew":
        H = h.upper()
        groups.append({"id": f"{h}_t", "name": f"{APPROACH_NAMES[H]}: прямо+направо",
                       "movements": [{"lane_id": f"{h}2", "movement": "straight"},
                                     {"lane_id": f"{h}2", "movement": "right"}]})
        groups.append({"id": f"{h}_l", "name": f"{APPROACH_NAMES[H]}: налево",
                       "movements": [{"lane_id": f"{h}1", "movement": "left"}]})
    pairs = []
    for x in ("n", "s"):
        for y in ("e", "w"):
            for a in ("t", "l"):
                for b in ("t", "l"):
                    pairs.append((f"{x}_{a}", f"{y}_{b}"))
    # левый поворот пересекает встречный прямой поток
    pairs += [("n_l", "s_t"), ("s_l", "n_t"), ("e_l", "w_t"), ("w_l", "e_t")]
    phases = [
        {"id": "p_ns_t", "name": "С–Ю прямо", "signal_groups": ["n_t", "s_t"], "fixed_green_sec": 24},
        {"id": "p_ns_l", "name": "С–Ю налево", "signal_groups": ["n_l", "s_l"], "fixed_green_sec": 10},
        {"id": "p_ew_t", "name": "З–В прямо", "signal_groups": ["e_t", "w_t"], "fixed_green_sec": 18},
        {"id": "p_ew_l", "name": "З–В налево", "signal_groups": ["e_l", "w_l"], "fixed_green_sec": 8},
    ]
    return {
        "name": "4-подходный с выделенными левыми (4 фазы)",
        "template": "four_way_protected_left",
        "approaches": [_approach(h) for h in "NESW"],
        "lanes": lanes,
        "signal_groups": groups,
        "conflicts": _conflicts(pairs),
        "phases": phases,
        "phase_order": ["p_ns_t", "p_ns_l", "p_ew_t", "p_ew_l"],
        "transitions": None,
        "traffic": {
            "seed": 42,
            "scenario_name": "Пик на восточном подходе",
            "scenario": [
                {"start_sec": 900, "end_sec": 1800, "lane_ids": ["e2"], "multiplier": 2.5,
                 "label": "пик: восток прямо ×2.5"},
            ],
        },
    }


def t_junction() -> dict:
    """T-образный: главная дорога З–В, второстепенная примыкает с юга.

    Запад: прямо+направо (на юг). Восток: прямо и отдельная полоса налево (на юг).
    Юг: налево+направо. Фазы: главная прямо; восток прямо+налево; юг.
    """
    lanes = [
        _lane("W", 0, ["straight", "right"], 450),
        _lane("E", 0, ["left"], 120),
        _lane("E", 1, ["straight"], 420),
        _lane("S", 0, ["left", "right"], 200),
    ]
    groups = [
        {"id": "g_w", "name": "Запад: прямо+направо",
         "movements": [{"lane_id": "w1", "movement": "straight"}, {"lane_id": "w1", "movement": "right"}]},
        {"id": "g_e", "name": "Восток: прямо", "movements": [{"lane_id": "e2", "movement": "straight"}]},
        {"id": "g_el", "name": "Восток: налево", "movements": [{"lane_id": "e1", "movement": "left"}]},
        {"id": "g_s", "name": "Юг: налево+направо",
         "movements": [{"lane_id": "s1", "movement": "left"}, {"lane_id": "s1", "movement": "right"}]},
    ]
    conflicts = _conflicts([("g_w", "g_el"), ("g_w", "g_s"), ("g_e", "g_s"), ("g_el", "g_s")])
    phases = [
        {"id": "p_main", "name": "Главная прямо", "signal_groups": ["g_w", "g_e"], "fixed_green_sec": 25},
        {"id": "p_left", "name": "Восток прямо+налево", "signal_groups": ["g_e", "g_el"], "fixed_green_sec": 10},
        {"id": "p_side", "name": "Юг", "signal_groups": ["g_s"], "fixed_green_sec": 14},
    ]
    return {
        "name": "T-образный (3 фазы)",
        "template": "t_junction",
        "approaches": [_approach(h) for h in "ESW"],
        "lanes": lanes,
        "signal_groups": groups,
        "conflicts": conflicts,
        "phases": phases,
        "phase_order": ["p_main", "p_left", "p_side"],
        "transitions": None,
        "traffic": {
            "seed": 42,
            "scenario_name": "Пик на второстепенной дороге",
            "scenario": [
                {"start_sec": 900, "end_sec": 1800, "lane_ids": ["s1"], "multiplier": 2.5,
                 "label": "пик: юг ×2.5"},
            ],
        },
    }


# key -> (название, построитель, описание: что шаблон демонстрирует)
TEMPLATES = {
    "four_way_simple": (
        "4-подходный простой", four_way_simple,
        "По одной полосе прямо+направо на подход, без левых поворотов; 2 фазы. Самая простая схема."),
    "four_way_protected_left": (
        "4-подходный с выделенными левыми", four_way_protected_left,
        "Две полосы на подход (налево / прямо+направо), 4 фазы с защищёнными левыми."),
    "t_junction": (
        "T-образный", t_junction,
        "Примыкание второстепенной дороги с юга; отдельная полоса левого поворота с востока; 3 фазы."),
}

# Импорт в конце модуля: дополнительные шаблоны используют помощники выше.
from app.simulation.templates_extra import EXTRA_TEMPLATES  # noqa: E402

TEMPLATES.update(EXTRA_TEMPLATES)


def build_template(key: str) -> IntersectionProfile:
    if key not in TEMPLATES:
        raise KeyError(key)
    return IntersectionProfile.model_validate(TEMPLATES[key][1]())


def template_info() -> list[dict]:
    return [{"key": k, "name": name, "description": desc} for k, (name, _, desc) in TEMPLATES.items()]
