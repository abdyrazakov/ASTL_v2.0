"""Выгрузка реальной записи симуляции для презентации → public/replay.json.

Запуск из корня репозитория:
    backend/.venv/bin/python presentation/scripts/export_replay.py

Оба режима на одном seed и одном профиле: машины одни и те же, отличается только
управление. Записывается окно в середине пика (кадр каждые 0.2 с) и полный журнал
зелёных фаз за час.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.simulation.engine import Simulation  # noqa: E402
from app.simulation.templates import build_template  # noqa: E402

TEMPLATE, SEED = "four_way_protected_left", 42
START, DURATION, FRAME_DT, HOUR = 1080.0, 180.0, 0.2, 3600.0
CLASSES = ["car", "bus", "truck", "motorcycle"]
MOVES = ["straight", "left", "right"]
SIG = {"red": "R", "yellow": "Y", "green": "G"}

profile = build_template(TEMPLATE)
groups = [g.id for g in profile.signal_groups]
lanes = [lane.id for lane in profile.lanes]
phases = [p.id for p in profile.phases]


def record(mode: str) -> dict:
    sim = Simulation(profile, mode, seed=SEED)
    sim.run_until(START)
    frames = []
    for k in range(int(DURATION / FRAME_DT) + 1):
        sim.run_until(START + k * FRAME_DT)
        sc = sim.scene()
        tot = sim.totals()
        frames.append({
            "sig": "".join(SIG[sc["signals"][g]] for g in groups),
            "q": sum(1 for v in sc["vehicles"] if v["state"] == "waiting" and not v["crossed"]) + sum(sc["backlog"].values()),
            "d": tot["avg_delay_sec"],
            "v": [
                [v["id"], lanes.index(v["lane_id"]), round(v["s"] * 10),
                 round(v["progress"] * 100) if v["crossed"] else -1,
                 MOVES.index(v["movement"]), CLASSES.index(v["cls"]), 1 if v["state"] == "waiting" else 0]
                for v in sc["vehicles"]
            ],
        })
    sim.run_until(HOUR)
    s = sim.summary()
    assert s["safety"]["blocked_violations"] == 0 and s["safety"]["faults"] == 0
    return {
        "frames": frames,
        "greens": [[phases.index(g["phase_id"]), g["start_sec"], g["duration_sec"]] for g in sim.machine.green_log],
        "hour": s["totals"],
    }


out = {
    "template": TEMPLATE,
    "seed": SEED,
    "start": START,
    "frameDt": FRAME_DT,
    "groups": groups,
    "groupNames": [g.name for g in profile.signal_groups],
    "conflicts": profile.conflicts,
    "lanes": lanes,
    "phases": [p.name for p in profile.phases],
    "profile": json.loads(profile.model_dump_json()),
    "runs": {mode: record(mode) for mode in ("fixed", "adaptive")},
}
path = ROOT / "presentation" / "public" / "replay.json"
path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"{path} {path.stat().st_size / 1e6:.1f} МБ; за час: "
      f"фикс. {out['runs']['fixed']['hour']['avg_delay_sec']} с, адапт. {out['runs']['adaptive']['hour']['avg_delay_sec']} с")
