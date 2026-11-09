// Схематичная геометрия перекрёстка для 2D-отрисовки. Служит ТОЛЬКО визуализации:
// аналитика считается на бэкенде по одномерной модели полос, а не по этим пикселям.
import type { Heading, IntersectionProfile, Movement, SimLane } from '../api/simTypes'

export const VIEW = 1000
export const C = VIEW / 2
export const LANE_W = 26

export type Vec = { x: number; y: number }

// Направление движения транспорта подхода (подход назван по стороне, откуда едут).
const TRAVEL: Record<Heading, Vec> = {
  N: { x: 0, y: 1 },
  E: { x: -1, y: 0 },
  S: { x: 0, y: -1 },
  W: { x: 1, y: 0 },
}

const add = (a: Vec, b: Vec): Vec => ({ x: a.x + b.x, y: a.y + b.y })
const mul = (a: Vec, k: number): Vec => ({ x: a.x * k, y: a.y * k })
// правая нормаль водителя (экранные координаты, y вниз)
const right = (d: Vec): Vec => ({ x: -d.y, y: d.x })

export interface Layout {
  half: number // половина стороны квадрата перекрёстка
  scale: number // пикселей на метр вдоль полосы
  lanesPerSide: number
}

export function computeLayout(p: IntersectionProfile): Layout {
  const per = p.approaches.map((a) => p.lanes.filter((l) => l.approach_id === a.id).length)
  const lanesPerSide = Math.max(1, ...per)
  const half = lanesPerSide * LANE_W + 14
  const maxLen = Math.max(50, ...p.lanes.map((l) => l.length_m))
  const scale = (C - half - 18) / maxLen
  return { half, scale, lanesPerSide }
}

export function headingOf(p: IntersectionProfile, lane: SimLane): Heading {
  return p.approaches.find((a) => a.id === lane.approach_id)?.heading ?? 'N'
}

export function travelDir(h: Heading): Vec {
  return TRAVEL[h]
}

const OPPOSITE: Record<Heading, Heading> = { N: 'S', S: 'N', E: 'W', W: 'E' }
const RIGHT_EXIT: Record<Heading, Heading> = { N: 'W', E: 'N', S: 'E', W: 'S' }
const LEFT_EXIT: Record<Heading, Heading> = { N: 'E', E: 'S', S: 'W', W: 'N' }

/** Сторона перекрёстка, куда уезжает манёвр m с подхода h (правостороннее движение). */
export function exitSide(h: Heading, m: Movement): Heading {
  return m === 'straight' ? OPPOSITE[h] : m === 'right' ? RIGHT_EXIT[h] : LEFT_EXIT[h]
}

/** Стороны, где нужно нарисовать дорогу: подходы + стороны выезда (например, у
 * односторонних улиц выезды есть там, где подходов нет). */
export function armSides(p: IntersectionProfile): Heading[] {
  const set = new Set<Heading>(p.approaches.map((a) => a.heading))
  for (const lane of p.lanes) for (const m of lane.movements) set.add(exitSide(headingOf(p, lane), m))
  return (['N', 'E', 'S', 'W'] as Heading[]).filter((h) => set.has(h))
}

export function laneFrame(p: IntersectionProfile, lane: SimLane, L: Layout) {
  const d = TRAVEL[headingOf(p, lane)]
  const r = right(d)
  const stop = add(add({ x: C, y: C }, mul(d, -L.half)), mul(r, (lane.index + 0.5) * LANE_W))
  const start = add(stop, mul(d, -lane.length_m * L.scale))
  return { d, r, stop, start }
}

/** Точка на полосе: s — метры относительно стоп-линии (< 0 — до неё). */
export function pointOnLane(p: IntersectionProfile, lane: SimLane, L: Layout, s: number) {
  const f = laneFrame(p, lane, L)
  return { pos: add(f.stop, mul(f.d, s * L.scale)), dir: f.d }
}

function exitDir(d: Vec, m: Movement): Vec {
  if (m === 'straight') return d
  const r = right(d)
  return m === 'right' ? r : mul(r, -1)
}

/** Траектория через перекрёсток: квадратичная кривая от стоп-линии к выезду. */
export function turnPath(p: IntersectionProfile, lane: SimLane, L: Layout, m: Movement) {
  const f = laneFrame(p, lane, L)
  const d2 = exitDir(f.d, m)
  const r2 = right(d2)
  const outIdx = m === 'left' ? 0 : m === 'right' ? L.lanesPerSide - 1 : Math.min(lane.index, L.lanesPerSide - 1)
  const exit = add(add({ x: C, y: C }, mul(d2, L.half)), mul(r2, (outIdx + 0.5) * LANE_W))
  let ctrl: Vec
  if (m === 'straight') ctrl = { x: (f.stop.x + exit.x) / 2, y: (f.stop.y + exit.y) / 2 }
  else ctrl = f.d.x === 0 ? { x: f.stop.x, y: exit.y } : { x: exit.x, y: f.stop.y }
  return { p0: f.stop, p1: ctrl, p2: exit }
}

export function bezier(path: { p0: Vec; p1: Vec; p2: Vec }, t: number) {
  const u = 1 - t
  const pos = {
    x: u * u * path.p0.x + 2 * u * t * path.p1.x + t * t * path.p2.x,
    y: u * u * path.p0.y + 2 * u * t * path.p1.y + t * t * path.p2.y,
  }
  const dir = {
    x: 2 * u * (path.p1.x - path.p0.x) + 2 * t * (path.p2.x - path.p1.x),
    y: 2 * u * (path.p1.y - path.p0.y) + 2 * t * (path.p2.y - path.p1.y),
  }
  const n = Math.hypot(dir.x, dir.y) || 1
  return { pos, dir: { x: dir.x / n, y: dir.y / n } }
}

export const angleDeg = (d: Vec) => (Math.atan2(d.y, d.x) * 180) / Math.PI

export const MOVEMENT_GLYPH: Record<Movement, string> = { left: '↰', straight: '↑', right: '↱' }
export const MOVEMENT_LABEL: Record<Movement, string> = { left: 'налево', straight: 'прямо', right: 'направо' }
export const HEADING_LABEL: Record<Heading, string> = { N: 'Север', E: 'Восток', S: 'Юг', W: 'Запад' }

export const CLASS_COLORS: Record<string, string> = {
  car: '#dfe7ea',
  bus: '#f5a623',
  truck: '#a78bfa',
  motorcycle: '#38bdf8',
}
export const CLASS_LABELS: Record<string, string> = {
  car: 'легковой',
  bus: 'автобус',
  truck: 'грузовик',
  motorcycle: 'мотоцикл',
}

export const SIGNAL_COLORS: Record<string, string> = {
  red: '#ef4444',
  yellow: '#f5c518',
  green: '#22c55e',
}

// Палитра фаз/групп для графиков и подсветки.
export const PALETTE = ['#2dd4bf', '#f5a623', '#a78bfa', '#38bdf8', '#f472b6', '#84cc16', '#fb923c', '#e879f9']
