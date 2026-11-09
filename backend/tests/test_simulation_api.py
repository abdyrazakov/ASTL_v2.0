"""API этапа 2: CRUD профилей перекрёстка, запуск/управление прогоном, экспорт,
сравнение режимов. Приложение собирается только из роутеров этапа 2 — без
видео-пайплайна (torch/ultralytics не нужны)."""
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import intersections, simulations
from app.simulation.manager import SimulationManager


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.storage.OUTPUT_DIR", tmp_path / "output")
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(intersections, "INTERSECTIONS_DIR", tmp_path / "intersections")
    (tmp_path / "intersections").mkdir()
    mgr = SimulationManager()
    monkeypatch.setattr(simulations, "manager", mgr)
    app = FastAPI()
    app.include_router(intersections.router)
    app.include_router(simulations.router)
    c = TestClient(app)
    c.output_dir = tmp_path / "output"
    yield c
    for run in mgr.list_runs():
        run.stop()


def wait_status(c, run_id, statuses, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        pr = c.get(f"/api/simulations/{run_id}").json()
        if pr["status"] in statuses:
            return pr
        time.sleep(0.05)
    raise AssertionError(f"статус не достигнут: {statuses}")


def test_profile_crud_duplicate_and_validation(client):
    c = client
    templates = c.get("/api/intersections/templates").json()
    assert len(templates) == 11 and all(t["description"] for t in templates)
    assert {"four_way_simple", "four_way_protected_left", "t_junction", "four_way_three_lane",
            "t_junction_three_lane", "one_way_pair"} <= {t["key"] for t in templates}
    p = c.post("/api/intersections/from-template/four_way_simple").json()
    pid = p["profile_id"]
    assert [x["profile_id"] for x in c.get("/api/intersections").json()] == [pid]

    p["name"] = "Мой перекрёсток"
    p["timings"]["gap_out_sec"] = 2.5
    upd = c.put(f"/api/intersections/{pid}", json=p).json()
    assert upd["name"] == "Мой перекрёсток" and upd["timings"]["gap_out_sec"] == 2.5

    dup = c.post(f"/api/intersections/{pid}/duplicate").json()
    assert dup["profile_id"] != pid and dup["name"].endswith("(копия)")

    bad = dict(p)
    bad["conflicts"] = {**p["conflicts"], "g_n": ["g_e"]}  # g_w не взаимен
    r = c.put(f"/api/intersections/{pid}", json=bad)
    assert r.status_code == 422
    assert any("несимметрична" in e for e in r.json()["detail"]["errors"])
    v = c.post("/api/intersections/validate", json=bad).json()
    assert v["valid"] is False and v["errors"]

    ok = c.post("/api/intersections/validate", json=p).json()
    assert ok == {"valid": True, "errors": [], "warnings": []}

    assert c.delete(f"/api/intersections/{dup['profile_id']}").json() == {"ok": True}
    assert c.get(f"/api/intersections/{dup['profile_id']}").status_code == 404


def test_run_lifecycle_controls_and_export(client):
    c = client
    pid = c.post("/api/intersections/from-template/t_junction").json()["profile_id"]
    r = c.post("/api/simulations", json={"profile_id": pid, "controller_mode": "fixed",
                                         "duration_sec": 300, "speed": 20, "seed": 77})
    assert r.status_code == 200
    rid = r.json()["run_id"]
    # одновременно — только один прогон
    assert c.post("/api/simulations", json={"profile_id": pid}).status_code == 409
    assert c.get("/api/simulations/active").json()["run_id"] == rid

    wait_status(c, rid, {"running"})
    pr = c.patch(f"/api/simulations/{rid}/controller", json={"mode": "adaptive"}).json()
    assert pr["controller_mode"] == "adaptive" and pr["mode_switches"] == 1
    assert c.patch(f"/api/simulations/{rid}/speed", json={"speed": 100}).json()["speed"] == 100

    c.post(f"/api/simulations/{rid}/pause")
    time.sleep(0.1)
    t1 = c.get(f"/api/simulations/{rid}").json()["sim_time_sec"]
    time.sleep(0.4)
    assert c.get(f"/api/simulations/{rid}").json()["sim_time_sec"] == t1
    c.post(f"/api/simulations/{rid}/resume")

    scene = c.get(f"/api/simulations/{rid}/scene").json()
    assert {"t", "signals", "vehicles", "signal_state"} <= set(scene)
    pr = wait_status(c, rid, {"completed"})
    assert pr["sim_time_sec"] == 300

    out = c.output_dir / rid
    files = {p.name for p in out.iterdir()}
    assert {"traffic_state.json", "traffic_history.jsonl", "traffic_metrics.csv", "profile.json",
            "run_metadata.json", "summary.json", "phase_log.jsonl", "signal_log.jsonl",
            "events.jsonl"} <= files
    meta = json.loads((out / "run_metadata.json").read_text())
    assert meta["seed"] == 77 and meta["controller_mode"] == "fixed"
    assert meta["controller_mode_final"] == "adaptive"
    assert meta["schema_version"] == "2.0" and meta["kind"] == "simulation"
    assert meta["traffic_generator"]["arrival_rate_vph"]["s1"] == 200
    assert meta["safety"]["blocked_violations"] == 0
    prof = json.loads((out / "profile.json").read_text())
    assert prof["kind"] == "intersection" and prof["conflicts"]
    history = c.get(f"/api/simulations/{rid}/history").json()
    assert len(history) == 301 and history[-1]["timestamp_sec"] == 300
    assert c.get(f"/api/simulations/{rid}/history?since=299.5").json()[0]["timestamp_sec"] == 300
    header = (out / "traffic_metrics.csv").read_text().splitlines()[0].split(",")
    assert header[:18] == [
        "timestamp_sec", "run_id", "lane_id", "lane_name", "vehicles", "queued",
        "queue_truncated_by_frame", "avg_wait_sec", "max_wait_sec", "wait_sample_size",
        "flow_count_window", "flow_window_available_sec", "flow_window_target_sec",
        "total_crossings", "composition_car", "composition_bus", "composition_truck",
        "composition_motorcycle"]
    assert "avg_delay_sec" in header and "controller_mode" in header
    events = [json.loads(x) for x in (out / "events.jsonl").read_text().splitlines()]
    assert [e["event"] for e in events] == ["controller_mode", "speed", "pause", "resume"]
    assert c.get(f"/api/simulations/{rid}/phase-log").json()

    # прогон с переключением режима не участвует в сравнении
    cmp = c.get(f"/api/simulations/comparison?profile_id={pid}&seed=77").json()
    assert cmp["available"] is False and "запустите оба режима" in cmp["message"]


def test_stop_and_infinite_mode(client):
    c = client
    pid = c.post("/api/intersections/from-template/four_way_simple").json()["profile_id"]
    rid = c.post("/api/simulations", json={"profile_id": pid, "duration_sec": None, "speed": 50}).json()["run_id"]
    wait_status(c, rid, {"running"})
    time.sleep(0.3)
    c.post(f"/api/simulations/{rid}/stop")
    pr = wait_status(c, rid, {"stopped"})
    assert pr["duration_sec"] is None and pr["sim_time_sec"] > 0
    assert json.loads((c.output_dir / rid / "run_metadata.json").read_text())["final_status"] == "stopped"
    # слот освободился
    assert c.get("/api/simulations/active").json() == {"active": False}


def test_comparison_only_from_real_runs(client):
    c = client
    pid = c.post("/api/intersections/from-template/four_way_simple").json()["profile_id"]
    first = c.get(f"/api/simulations/comparison?profile_id={pid}").json()
    assert first["available"] is False

    res = c.post("/api/simulations/compare", json={"profile_id": pid, "duration_sec": 600}).json()
    assert res["available"] is True and res["duration_sec"] == 600 and res["seed"] == 42
    fx, ad = res["fixed"], res["adaptive"]
    assert fx["controller_mode"] == "fixed" and ad["controller_mode"] == "adaptive"
    for side in (fx, ad):
        summary = json.loads((c.output_dir / side["run_id"] / "summary.json").read_text())
        assert summary["totals"] == side["totals"]  # цифры — из сохранённых прогонов
    # повторный запрос сравнения находит ту же пару на диске
    again = c.get(f"/api/simulations/comparison?profile_id={pid}").json()
    assert again["fixed"]["run_id"] == fx["run_id"]

    # другой seed — другой сценарий, пары нет
    other = c.get(f"/api/simulations/comparison?profile_id={pid}&seed=43").json()
    assert other["available"] is False

    runs = c.get(f"/api/simulations/runs?profile_id={pid}").json()
    assert len(runs) == 2 and all(r["final_status"] == "completed" for r in runs)
