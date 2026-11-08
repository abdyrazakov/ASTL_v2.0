"""Дополнительные шаблоны перекрёстков: 3-полосные и другие разнообразные схемы.

О матрицах конфликтов. Система по-прежнему НЕ выводит конфликты автоматически:
у профиля пользователя матрица — явные данные, которые редактируются вручную и
только валидируются. Здесь же матрицы ШАБЛОНОВ подготовлены по явной таблице правил
правостороннего движения (`movement_conflict`), чтобы не ошибиться при ручном
переборе десятков пар. Правила проверены тестом: на трёх исходных шаблонах, чьи
матрицы написаны вручную, они дают ровно те же матрицы. Результат сохраняется в
профиль как обычные явные данные.

Правила для двух манёвров (подход h — сторона, откуда едут; выезд — сторона,
куда уезжают):
- с одного подхода — не конфликтуют (параллельные полосы);
- выезд в одну сторону — конфликт (слияние);
- правый поворот — больше ни с чем (огибает угол перекрёстка);
- встречные подходы: конфликтуют только «налево» и «прямо» (встречные левые
  разъезжаются, встречные прямые параллельны);
- перпендикулярные подходы: любые два не-правых манёвра пересекаются — конфликт.
"""
from __future__ import annotations

from app.simulation.templates import APPROACH_NAMES, _approach, _lane

OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
# для подхода h: куда уходит правый / левый поворот (правостороннее движение)
RIGHT_EXIT = {"N": "W", "E": "N", "S": "E", "W": "S"}
LEFT_EXIT = {"N": "E", "E": "S", "S": "W", "W": "N"}


def exit_side(h: str, m: str) -> str:
    if m == "straight":
        return OPPOSITE[h]
    return RIGHT_EXIT[h] if m == "right" else LEFT_EXIT[h]


def movement_conflict(h1: str, m1: str, h2: str, m2: str) -> bool:
    if h1 == h2:
        return False
    if exit_side(h1, m1) == exit_side(h2, m2):
        return True
    if "right" in (m1, m2):
        return False
    if OPPOSITE[h1] == h2:
        return {m1, m2} == {"left", "straight"}
    return True


def derive_conflicts(profile: dict) -> dict[str, list[str]]:
    """Матрица конфликтов групп по таблице правил (для подготовки шаблонов)."""
    heading = {a["id"]: a["heading"] for a in profile["approaches"]}
    lane_h = {lane["id"]: heading[lane["approach_id"]] for lane in profile["lanes"]}
    groups = profile["signal_groups"]
    out: dict[str, list[str]] = {}
    for i, ga in enumerate(groups):
        for gb in groups[i + 1:]:
            clash = any(
                movement_conflict(lane_h[a["lane_id"]], a["movement"], lane_h[b["lane_id"]], b["movement"])
                for a in ga["movements"] for b in gb["movements"]
            )
            if clash:
                out.setdefault(ga["id"], []).append(gb["id"])
                out.setdefault(gb["id"], []).append(ga["id"])
    return {k: sorted(v) for k, v in out.items()}


def _g(gid: str, name: str, items: list[tuple[str, list[str]]]) -> dict:
    return {"id": gid, "name": name,
            "movements": [{"lane_id": lid, "movement": m} for lid, ms in items for m in ms]}


def _ph(pid: str, name: str, groups: list[str], fixed: float) -> dict:
    return {"id": pid, "name": name, "signal_groups": groups, "fixed_green_sec": fixed}


def _finish(d: dict) -> dict:
    d["conflicts"] = derive_conflicts(d)
    d.setdefault("phase_order", [p["id"] for p in d["phases"]])
    d.setdefault("transitions", None)
    return d


def _three_lane_approach(h: str, rates: tuple[float, float, float], length: float = 180.0) -> list[dict]:
    """3 полосы: левая — налево, средняя — прямо, правая — прямо+направо."""
    return [
        _lane(h, 0, ["left"], rates[0], length),
        _lane(h, 1, ["straight"], rates[1], length),
        _lane(h, 2, ["straight", "right"], rates[2], length),
    ]


def _through_left_groups(h: str, through_lanes: list[str], left_lanes: list[str]) -> list[dict]:
    H = APPROACH_NAMES[h.upper()]
    through = [(lid, ["straight"] if lid != through_lanes[-1] else ["straight", "right"]) for lid in through_lanes]
    return [
        _g(f"{h}_t", f"{H}: прямо+направо", through),
        _g(f"{h}_l", f"{H}: налево", [(lid, ["left"]) for lid in left_lanes]),
    ]


# ------------------------------------------------------------------ шаблоны


def four_way_three_lane(peaks: bool = False) -> dict:
    rates = {"N": (150, 430, 380), "S": (130, 400, 360), "E": (100, 300, 260), "W": (90, 280, 250)}
    lanes = [lane for h in "NSEW" for lane in _three_lane_approach(h, rates[h])]
    groups = [g for h in "nsew" for g in _through_left_groups(h, [f"{h}2", f"{h}3"], [f"{h}1"])]
    phases = [
        _ph("p_ns_t", "С–Ю прямо", ["n_t", "s_t"], 26),
        _ph("p_ns_l", "С–Ю налево", ["n_l", "s_l"], 11),
        _ph("p_ew_t", "З–В прямо", ["e_t", "w_t"], 20),
        _ph("p_ew_l", "З–В налево", ["e_l", "w_l"], 9),
    ]
    if peaks:
        name = "4-подходный, 3 полосы: утро / вечер / ночь"
        traffic = {
            "seed": 42,
            "scenario_name": "Сутки за час: утренний пик с севера, вечерний с юга, ночной спад",
            "scenario": [
                {"start_sec": 300, "end_sec": 1200, "lane_ids": ["n1", "n2", "n3"], "multiplier": 2.2,
                 "label": "утро: в центр с севера ×2.2"},
                {"start_sec": 1500, "end_sec": 2400, "lane_ids": ["s1", "s2", "s3"], "multiplier": 2.2,
                 "label": "вечер: из центра с юга ×2.2"},
                {"start_sec": 2550, "end_sec": 3000, "lane_ids": ["e1", "e2", "e3", "w1", "w2", "w3"],
                 "multiplier": 1.8, "label": "поперечная улица ×1.8"},
                {"start_sec": 3000, "end_sec": 3600, "lane_ids": [], "multiplier": 0.25,
                 "label": "ночь: всё ×0.25"},
            ],
        }
        key = "four_way_three_lane_peaks"
    else:
        name = "4-подходный, 3 полосы (4 фазы)"
        traffic = {
            "seed": 42,
            "scenario_name": "Пик на западном подходе",
            "scenario": [{"start_sec": 900, "end_sec": 1800, "lane_ids": ["w2", "w3"], "multiplier": 2.0,
                          "label": "пик: запад прямо ×2"}],
        }
        key = "four_way_three_lane"
    return _finish({
        "name": name, "template": key,
        "approaches": [_approach(h) for h in "NESW"],
        "lanes": lanes, "signal_groups": groups, "phases": phases, "traffic": traffic,
    })


def four_way_three_lane_peaks() -> dict:
    return four_way_three_lane(peaks=True)


def four_way_three_lane_split() -> dict:
    """Те же 3 полосы, но расщеплённые фазы: каждый подход едет один, всеми манёврами."""
    rates = {"N": (90, 300, 260), "S": (80, 280, 240), "E": (70, 220, 190), "W": (60, 200, 180)}
    lanes = [lane for h in "NSEW" for lane in _three_lane_approach(h, rates[h])]
    groups = [
        _g(f"g_{h}", f"{APPROACH_NAMES[h.upper()]}: все манёвры",
           [(f"{h}1", ["left"]), (f"{h}2", ["straight"]), (f"{h}3", ["straight", "right"])])
        for h in "nesw"
    ]
    phases = [
        _ph("p_n", "Север (все)", ["g_n"], 18),
        _ph("p_e", "Восток (все)", ["g_e"], 14),
        _ph("p_s", "Юг (все)", ["g_s"], 17),
        _ph("p_w", "Запад (все)", ["g_w"], 13),
    ]
    return _finish({
        "name": "4-подходный, 3 полосы, расщеплённые фазы (подход за подходом)",
        "template": "four_way_three_lane_split",
        "approaches": [_approach(h) for h in "NESW"],
        "lanes": lanes, "signal_groups": groups, "phases": phases,
        "traffic": {"seed": 42, "scenario_name": "Без сценария", "scenario": []},
    })


def arterial_minor() -> dict:
    """Магистраль З–В по 3 полосы × второстепенная С–Ю по одной общей полосе."""
    lanes = (_three_lane_approach("E", (110, 520, 440), 220) + _three_lane_approach("W", (100, 500, 420), 220)
             + [_lane("N", 0, ["left", "straight", "right"], 110, 120),
                _lane("S", 0, ["left", "straight", "right"], 90, 120)])
    groups = (_through_left_groups("e", ["e2", "e3"], ["e1"]) + _through_left_groups("w", ["w2", "w3"], ["w1"])
              + [_g("g_n", "Север: все манёвры", [("n1", ["left", "straight", "right"])]),
                 _g("g_s", "Юг: все манёвры", [("s1", ["left", "straight", "right"])])])
    phases = [
        _ph("p_main", "Магистраль прямо", ["e_t", "w_t"], 34),
        _ph("p_main_l", "Магистраль налево", ["e_l", "w_l"], 10),
        _ph("p_n", "Север", ["g_n"], 9),
        _ph("p_s", "Юг", ["g_s"], 8),
    ]
    return _finish({
        "name": "Магистраль 3 полосы × второстепенная улица",
        "template": "arterial_minor",
        "approaches": [_approach(h) for h in "NESW"],
        "lanes": lanes, "signal_groups": groups, "phases": phases,
        "traffic": {
            "seed": 42,
            "composition": {"car": 0.8, "bus": 0.1, "truck": 0.05, "motorcycle": 0.05},
            "scenario_name": "Окончание уроков: всплеск на второстепенной",
            "scenario": [{"start_sec": 1200, "end_sec": 1800, "lane_ids": ["n1"], "multiplier": 3.0,
                          "label": "школа: север ×3"}],
        },
    })


def t_junction_three_lane() -> dict:
    """T-образный с 3-полосной главной; правые повороты горят в двух фазах (перекрытия)."""
    lanes = [
        _lane("W", 0, ["straight"], 420, 200), _lane("W", 1, ["straight"], 380, 200),
        _lane("W", 2, ["right"], 180, 200),
        _lane("E", 0, ["left"], 150, 200), _lane("E", 1, ["straight"], 400, 200),
        _lane("E", 2, ["straight"], 380, 200),
        _lane("S", 0, ["left"], 160, 140), _lane("S", 1, ["right"], 200, 140),
    ]
    groups = [
        _g("w_t", "Запад: прямо", [("w1", ["straight"]), ("w2", ["straight"])]),
        _g("w_r", "Запад: направо (в примыкание)", [("w3", ["right"])]),
        _g("e_t", "Восток: прямо", [("e2", ["straight"]), ("e3", ["straight"])]),
        _g("e_l", "Восток: налево", [("e1", ["left"])]),
        _g("s_l", "Юг: налево", [("s1", ["left"])]),
        _g("s_r", "Юг: направо", [("s2", ["right"])]),
    ]
    phases = [
        _ph("p_main", "Главная прямо + правый с запада", ["w_t", "w_r", "e_t"], 28),
        _ph("p_left", "Восток прямо+налево + правый с юга", ["e_t", "e_l", "s_r"], 12),
        _ph("p_side", "Юг + правый с запада", ["s_l", "s_r", "w_r"], 14),
    ]
    return _finish({
        "name": "T-образный, главная 3 полосы (группы в нескольких фазах)",
        "template": "t_junction_three_lane",
        "approaches": [_approach(h) for h in "ESW"],
        "lanes": lanes, "signal_groups": groups, "phases": phases,
        "traffic": {
            "seed": 42,
            "composition": {"car": 0.65, "bus": 0.05, "truck": 0.25, "motorcycle": 0.05},
            "scenario_name": "Промзона: смена на заводе",
            "scenario": [{"start_sec": 1200, "end_sec": 2100, "lane_ids": ["s1", "s2"], "multiplier": 2.5,
                          "label": "выезд смены с юга ×2.5"}],
        },
    })


def one_way_pair() -> dict:
    """Пересечение двух односторонних улиц по 3 полосы: только два подхода и две фазы.

    С севера (на юг) — налево (на восток) и прямо; с запада (на восток) — прямо и
    направо (на юг). Повороты против одностороннего движения запрещены.
    """
    lanes = [
        _lane("N", 0, ["left"], 260, 200), _lane("N", 1, ["straight"], 560, 200),
        _lane("N", 2, ["straight"], 520, 200),
        _lane("W", 0, ["straight"], 540, 200), _lane("W", 1, ["straight"], 520, 200),
        _lane("W", 2, ["straight", "right"], 380, 200),
    ]
    groups = [
        _g("g_n", "Север: все полосы", [("n1", ["left"]), ("n2", ["straight"]), ("n3", ["straight"])]),
        _g("g_w", "Запад: все полосы", [("w1", ["straight"]), ("w2", ["straight"]), ("w3", ["straight", "right"])]),
    ]
    phases = [_ph("p_n", "Север→Юг", ["g_n"], 25), _ph("p_w", "Запад→Восток", ["g_w"], 25)]
    return _finish({
        "name": "Две односторонние улицы по 3 полосы (2 фазы)",
        "template": "one_way_pair",
        "approaches": [_approach("N"), _approach("W")],
        "lanes": lanes, "signal_groups": groups, "phases": phases,
        "traffic": {
            "seed": 42,
            "scenario_name": "Волна с запада",
            "scenario": [{"start_sec": 600, "end_sec": 1500, "lane_ids": ["w1", "w2", "w3"], "multiplier": 1.6,
                          "label": "запад ×1.6"}],
        },
    })


def asymmetric_short() -> dict:
    """Разное число полос на подходах (3/2/1/2) и короткие подходы — видно, как очередь
    выходит за пределы участка (spillback)."""
    lanes = [
        _lane("N", 0, ["left"], 120, 80), _lane("N", 1, ["straight"], 420, 80),
        _lane("N", 2, ["straight", "right"], 380, 80),
        _lane("S", 0, ["left"], 100, 150), _lane("S", 1, ["straight", "right"], 380, 150),
        _lane("E", 0, ["left", "straight", "right"], 200, 60),
        _lane("W", 0, ["left", "straight"], 180, 120), _lane("W", 1, ["straight", "right"], 230, 120),
    ]
    groups = [
        _g("n_t", "Север: прямо+направо", [("n2", ["straight"]), ("n3", ["straight", "right"])]),
        _g("n_l", "Север: налево", [("n1", ["left"])]),
        _g("s_t", "Юг: прямо+направо", [("s2", ["straight", "right"])]),
        _g("s_l", "Юг: налево", [("s1", ["left"])]),
        _g("g_e", "Восток: все манёвры", [("e1", ["left", "straight", "right"])]),
        _g("g_w", "Запад: все манёвры", [("w1", ["left", "straight"]), ("w2", ["straight", "right"])]),
    ]
    phases = [
        _ph("p_ns_t", "С–Ю прямо", ["n_t", "s_t"], 24),
        _ph("p_ns_l", "С–Ю налево", ["n_l", "s_l"], 10),
        _ph("p_e", "Восток", ["g_e"], 11),
        _ph("p_w", "Запад", ["g_w"], 14),
    ]
    return _finish({
        "name": "Асимметричный: 3/2/1/2 полосы, короткие подходы",
        "template": "asymmetric_short",
        "approaches": [_approach(h) for h in "NESW"],
        "lanes": lanes, "signal_groups": groups, "phases": phases,
        "traffic": {
            "seed": 42,
            "scenario_name": "Пик на коротком северном подходе",
            "scenario": [{"start_sec": 600, "end_sec": 1500, "lane_ids": ["n2", "n3"], "multiplier": 1.8,
                          "label": "север ×1.8"}],
        },
    })


def boulevard_dual_left() -> dict:
    """Бульвар С–Ю по 4 полосы со сдвоенными левыми × улица З–В по 2 полосы."""
    lanes = []
    for h, r in (("N", (200, 200, 480, 430)), ("S", (180, 180, 450, 400))):
        lanes += [_lane(h, 0, ["left"], r[0], 250), _lane(h, 1, ["left"], r[1], 250),
                  _lane(h, 2, ["straight"], r[2], 250), _lane(h, 3, ["straight", "right"], r[3], 250)]
    for h, r in (("E", (90, 340)), ("W", (80, 320))):
        lanes += [_lane(h, 0, ["left"], r[0], 150), _lane(h, 1, ["straight", "right"], r[1], 150)]
    groups = (_through_left_groups("n", ["n3", "n4"], ["n1", "n2"])
              + _through_left_groups("s", ["s3", "s4"], ["s1", "s2"])
              + _through_left_groups("e", ["e2"], ["e1"]) + _through_left_groups("w", ["w2"], ["w1"]))
    phases = [
        _ph("p_ns_l", "Бульвар налево (сдвоенные)", ["n_l", "s_l"], 14),
        _ph("p_ns_t", "Бульвар прямо", ["n_t", "s_t"], 28),
        _ph("p_ew_l", "Улица налево", ["e_l", "w_l"], 8),
        _ph("p_ew_t", "Улица прямо", ["e_t", "w_t"], 16),
    ]
    return _finish({
        "name": "Бульвар 4 полосы со сдвоенными левыми × улица 2 полосы",
        "template": "boulevard_dual_left",
        "approaches": [_approach(h) for h in "NESW"],
        "lanes": lanes, "signal_groups": groups, "phases": phases,
        "traffic": {
            "seed": 42,
            "scenario_name": "Всплеск левых поворотов с бульвара",
            "scenario": [{"start_sec": 900, "end_sec": 1800, "lane_ids": ["n1", "n2"], "multiplier": 2.0,
                          "label": "левые с севера ×2"}],
        },
    })


EXTRA_TEMPLATES = {
    "four_way_three_lane": (
        "4-подходный, 3 полосы", four_way_three_lane,
        "Классический городской перекрёсток: на каждом подходе левая (налево), средняя (прямо) "
        "и правая (прямо+направо) полосы; 4 фазы с защищёнными левыми."),
    "four_way_three_lane_split": (
        "4-подходный, 3 полосы, расщеплённые фазы", four_way_three_lane_split,
        "Каждый подход едет отдельно всеми манёврами (4 фазы). Конфликтов внутри фазы нет совсем, "
        "но цикл длинный — адаптивный режим выигрывает, сокращая фазы пустых подходов."),
    "four_way_three_lane_peaks": (
        "4-подходный, 3 полосы: утро / вечер / ночь", four_way_three_lane_peaks,
        "Та же геометрия, но сценарий на час: утренний пик с севера, вечерний с юга, всплеск на "
        "поперечной улице и ночной спад. Показывает, как адаптивный режим следует за спросом."),
    "arterial_minor": (
        "Магистраль × второстепенная", arterial_minor,
        "Магистраль З–В по 3 полосы с большим потоком и автобусами, второстепенная С–Ю по одной "
        "общей полосе (по фазе на каждый подход). Всплеск «окончание уроков»."),
    "t_junction_three_lane": (
        "T-образный, главная 3 полосы", t_junction_three_lane,
        "Примыкание к 3-полосной главной. Правые повороты горят сразу в двух фазах (группа входит "
        "в несколько фаз). Промзона: 25% грузовиков, выезд смены."),
    "one_way_pair": (
        "Две односторонние улицы", one_way_pair,
        "Только два подхода по 3 полосы и две фазы. Высокая интенсивность, повороты только по "
        "направлению одностороннего движения."),
    "asymmetric_short": (
        "Асимметричный, короткие подходы", asymmetric_short,
        "Подходы с 3, 2, 1 и 2 полосами, участки 60–150 м: при пике очередь выходит за пределы "
        "участка (на схеме — «+N»)."),
    "boulevard_dual_left": (
        "Бульвар со сдвоенными левыми", boulevard_dual_left,
        "Бульвар С–Ю по 4 полосы (две левоповоротные) × улица по 2 полосы; длинные подходы 250 м."),
}
