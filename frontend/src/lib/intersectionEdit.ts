// Операции редактирования профиля перекрёстка на клиенте. Окончательная
// (жёсткая) валидация — на сервере; здесь только поддержание ссылочной
// целостности, чтобы удаление полосы/группы/фазы не оставляло «висячих» ссылок.
import type { Heading, IntersectionProfile, Movement } from '../api/simTypes'
import { HEADING_LABEL } from './intersectionGeometry'

export const APPROACH_COLORS: Record<Heading, string> = { N: '#2dd4bf', E: '#38bdf8', S: '#f5a623', W: '#a78bfa' }
export const ALL_MOVEMENTS: Movement[] = ['left', 'straight', 'right']

export function clone<T>(x: T): T {
  return structuredClone(x)
}

export function uniqueId(prefix: string, taken: Iterable<string>): string {
  const set = new Set(taken)
  for (let i = 1; ; i++) {
    const id = `${prefix}${i}`
    if (!set.has(id)) return id
  }
}

/** Удаляет ссылки на несуществующие полосы/манёвры/группы/фазы. */
export function normalize(p: IntersectionProfile): IntersectionProfile {
  const lanes = new Map(p.lanes.map((l) => [l.id, l]))
  for (const g of p.signal_groups) {
    g.movements = g.movements.filter((lm) => lanes.get(lm.lane_id)?.movements.includes(lm.movement))
  }
  const groupIds = new Set(p.signal_groups.map((g) => g.id))
  const conflicts: Record<string, string[]> = {}
  for (const [a, bs] of Object.entries(p.conflicts)) {
    if (!groupIds.has(a)) continue
    const list = bs.filter((b) => groupIds.has(b) && b !== a)
    if (list.length) conflicts[a] = list
  }
  p.conflicts = conflicts
  for (const ph of p.phases) ph.signal_groups = ph.signal_groups.filter((g) => groupIds.has(g))
  const phaseIds = new Set(p.phases.map((ph) => ph.id))
  p.phase_order = [
    ...p.phase_order.filter((id) => phaseIds.has(id)),
    ...p.phases.map((ph) => ph.id).filter((id) => !p.phase_order.includes(id)),
  ]
  if (p.transitions) {
    const t: Record<string, string[]> = {}
    for (const [a, bs] of Object.entries(p.transitions)) {
      if (phaseIds.has(a)) t[a] = bs.filter((b) => phaseIds.has(b) && b !== a)
    }
    p.transitions = t
  }
  for (const seg of p.traffic.scenario) seg.lane_ids = seg.lane_ids.filter((id) => lanes.has(id))
  return p
}

export function addApproach(p: IntersectionProfile, h: Heading) {
  if (p.approaches.some((a) => a.heading === h)) return
  const taken = p.approaches.map((a) => a.id)
  const aid = taken.includes(h.toLowerCase()) ? uniqueId(h.toLowerCase(), taken) : h.toLowerCase()
  p.approaches.push({ id: aid, name: HEADING_LABEL[h], heading: h })
  addLane(p, aid)
}

export function removeApproach(p: IntersectionProfile, approachId: string) {
  p.approaches = p.approaches.filter((a) => a.id !== approachId)
  p.lanes = p.lanes.filter((l) => l.approach_id !== approachId)
  normalize(p)
}

export function addLane(p: IntersectionProfile, approachId: string) {
  const a = p.approaches.find((x) => x.id === approachId)
  if (!a) return
  const used = p.lanes.filter((l) => l.approach_id === approachId).map((l) => l.index)
  const index = used.length ? Math.max(...used) + 1 : 0
  if (index > 5) return
  const id = uniqueId(approachId, p.lanes.map((l) => l.id))
  p.lanes.push({
    id,
    approach_id: approachId,
    index,
    name: `${a.name}-${index + 1}`,
    color: APPROACH_COLORS[a.heading],
    movements: ['straight'],
    length_m: 150,
    speed_limit_mps: 13.9,
    arrival_rate_vph: 300,
  })
}

export function removeLane(p: IntersectionProfile, laneId: string) {
  const lane = p.lanes.find((l) => l.id === laneId)
  p.lanes = p.lanes.filter((l) => l.id !== laneId)
  if (lane) {
    // сдвигаем номера оставшихся полос подхода, чтобы не было «дыр»
    p.lanes
      .filter((l) => l.approach_id === lane.approach_id)
      .sort((x, y) => x.index - y.index)
      .forEach((l, i) => { l.index = i })
  }
  normalize(p)
}

export function toggleConflict(p: IntersectionProfile, a: string, b: string, on: boolean) {
  const set = (x: string, y: string) => {
    const list = new Set(p.conflicts[x] ?? [])
    if (on) list.add(y)
    else list.delete(y)
    p.conflicts[x] = [...list].sort()
    if (!p.conflicts[x].length) delete p.conflicts[x]
  }
  set(a, b)
  set(b, a) // матрица всегда симметрична
}

export function conflicts(p: IntersectionProfile, a: string, b: string): boolean {
  return (p.conflicts[a] ?? []).includes(b)
}

export function cycleTransitions(p: IntersectionProfile): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  p.phase_order.forEach((id, i) => {
    out[id] = [p.phase_order[(i + 1) % p.phase_order.length]].filter((x) => x !== id)
  })
  return out
}
