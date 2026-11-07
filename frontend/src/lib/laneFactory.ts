import type { Lane, Point } from '../api/types'

const PALETTE = ['#2dd4bf', '#38bdf8', '#f59e0b', '#ef4444', '#a78bfa', '#4ade80', '#f472b6', '#fb923c']

export function colorForIndex(i: number): string {
  return PALETTE[i % PALETTE.length]
}

export function makeLaneId(existing: Lane[]): string {
  let n = existing.length + 1
  const used = new Set(existing.map((l) => l.id))
  while (used.has(`lane_${n}`)) n++
  return `lane_${n}`
}

export function defaultLaneName(existing: Lane[]): string {
  let n = existing.length + 1
  const used = new Set(existing.map((l) => l.name))
  while (used.has(`Полоса ${n}`)) n++
  return `Полоса ${n}`
}

export function insetPolygon(points: Point[], factor: number): Point[] {
  const cx = points.reduce((s, p) => s + p.x, 0) / points.length
  const cy = points.reduce((s, p) => s + p.y, 0) / points.length
  return points.map((p) => ({ x: (p.x - cx) * factor + cx, y: (p.y - cy) * factor + cy }))
}

export function polygonArea(points: Point[]): number {
  let area = 0
  for (let i = 0; i < points.length; i++) {
    const a = points[i]
    const b = points[(i + 1) % points.length]
    area += a.x * b.y - b.x * a.y
  }
  return Math.abs(area / 2)
}

export function segmentsSelfIntersect(points: Point[]): boolean {
  const n = points.length
  if (n < 4) return false
  const ccw = (p: Point, q: Point, r: Point) => (r.y - p.y) * (q.x - p.x) - (q.y - p.y) * (r.x - p.x)
  const intersects = (a1: Point, a2: Point, b1: Point, b2: Point) => {
    const d1 = ccw(b1, b2, a1)
    const d2 = ccw(b1, b2, a2)
    const d3 = ccw(a1, a2, b1)
    const d4 = ccw(a1, a2, b2)
    return (d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)
      ? (d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0)
      : false
  }
  const edges: [Point, Point][] = points.map((p, i) => [p, points[(i + 1) % n]])
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (Math.abs(i - j) === 0 || Math.abs(i - j) === 1 || Math.abs(i - j) === n - 1) continue
      if (intersects(edges[i][0], edges[i][1], edges[j][0], edges[j][1])) return true
    }
  }
  return false
}

export function pointInPolygon(point: Point, polygon: Point[]): boolean {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x, yi = polygon[i].y
    const xj = polygon[j].x, yj = polygon[j].y
    const intersect = yi > point.y !== yj > point.y &&
      point.x < ((xj - xi) * (point.y - yi)) / (yj - yi || 1e-12) + xi
    if (intersect) inside = !inside
  }
  return inside
}

export function newDraftLane(existing: Lane[]): Pick<Lane, 'id' | 'name' | 'color' | 'reference_point_mode'> {
  return {
    id: makeLaneId(existing),
    name: defaultLaneName(existing),
    color: colorForIndex(existing.length),
    reference_point_mode: null,
  }
}
