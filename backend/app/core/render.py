"""Отрисовка аннотаций на кадре: рамки, ID, траектории, полосы, зоны очереди, линии."""
from __future__ import annotations

import cv2
import numpy as np

from app.core.lane_engine import AnalyticsEngine, Detection
from app.models.profile import Profile

DEFAULT_RENDER_OPTIONS = {
    "show_boxes": True,
    "show_ids": True,
    "show_trajectories": True,
    "show_lanes": True,
    "show_queue_zones": True,
    "show_lines": True,
}

STATE_COLORS = {
    "moving": (255, 255, 255),
    "waiting": (0, 165, 255),  # янтарный (BGR)
}


def _hex_to_bgr(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    return (b, g, r)


def _poly_px(polygon, w: int, h: int) -> np.ndarray:
    return np.array([[p.x * w, p.y * h] for p in polygon.points], dtype=np.int32)


def draw_static_layers(frame: np.ndarray, profile: Profile, options: dict) -> None:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    for lane in profile.lanes:
        color = _hex_to_bgr(lane.color)
        if options.get("show_lanes", True):
            pts = _poly_px(lane.observation_polygon, w, h)
            cv2.polylines(overlay, [pts], True, color, 2, cv2.LINE_AA)
        if options.get("show_queue_zones", True):
            pts = _poly_px(lane.queue_zone_polygon, w, h)
            cv2.fillPoly(overlay, [pts], color)
        if options.get("show_lines", True):
            line = lane.count_line
            p1 = (int(line.p1.x * w), int(line.p1.y * h))
            p2 = (int(line.p2.x * w), int(line.p2.y * h))
            cv2.line(overlay, p1, p2, color, 3, cv2.LINE_AA)
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            pos = (int(line.positive_side_point.x * w), int(line.positive_side_point.y * h))
            direction = np.array(pos) - np.array(mid)
            norm = np.linalg.norm(direction)
            if norm > 1e-3:
                direction = (direction / norm * 28).astype(int)
                arrow_end = (mid[0] + direction[0], mid[1] + direction[1])
                cv2.arrowedLine(overlay, mid, arrow_end, color, 3, cv2.LINE_AA, tipLength=0.4)
    cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, dst=frame)

    # Контуры полос поверх (без альфы, чётче)
    for lane in profile.lanes:
        color = _hex_to_bgr(lane.color)
        if options.get("show_lanes", True):
            pts = _poly_px(lane.observation_polygon, w, h)
            cv2.polylines(frame, [pts], True, color, 2, cv2.LINE_AA)
            label_pt = pts[0]
            cv2.putText(
                frame, lane.name, (int(label_pt[0]), max(int(label_pt[1]) - 8, 14)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA,
            )


def draw_dynamic_layers(
    frame: np.ndarray,
    detections: list[Detection],
    engine: AnalyticsEngine,
    options: dict,
) -> None:
    for det in detections:
        track = engine.tracks.get(det.track_id)
        x1, y1, x2, y2 = (int(v) for v in det.bbox)
        lane_color = (255, 255, 255)
        if track and track.assigned_lane and track.assigned_lane in engine.lanes:
            lane_color = _hex_to_bgr(engine.lanes[track.assigned_lane].lane.color)
        state = track.queue_state if track else "moving"
        box_color = STATE_COLORS.get(state, lane_color)

        if options.get("show_boxes", True):
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

        if options.get("show_trajectories", True) and track is not None:
            pts = [p for (_, p, _) in track.point_history]
            for i in range(1, len(pts)):
                a = (int(pts[i - 1][0]), int(pts[i - 1][1]))
                b = (int(pts[i][0]), int(pts[i][1]))
                cv2.line(frame, a, b, lane_color, 2, cv2.LINE_AA)

        if options.get("show_ids", True):
            label = f"#{det.track_id} {det.cls}"
            if state == "waiting":
                label += " ожид."
            cv2.putText(
                frame, label, (x1, max(y1 - 6, 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 1, cv2.LINE_AA,
            )
