import { createContext, useContext, useEffect, useState } from 'react'
import type { IntersectionProfile } from '../../../frontend/src/api/simTypes'

/** Кадр записи: сигналы групп одной строкой (G/Y/R), машин в очереди, средняя задержка
 *  с начала прогона и машины [id, полоса, s×10 м, прогресс×100 (−1 — до стоп-линии), манёвр, класс, стоит]. */
export interface Frame {
  sig: string
  q: number
  d: number
  v: [number, number, number, number, number, number, number][]
}

export interface Run {
  frames: Frame[]
  greens: [number, number, number][] // [фаза, начало, длительность]
  hour: { avg_delay_sec: number; stops_per_vehicle: number; throughput_per_hour: number }
}

export interface Replay {
  seed: number
  start: number
  frameDt: number
  groups: string[]
  groupNames: string[]
  conflicts: Record<string, string[]>
  lanes: string[]
  phases: string[]
  profile: IntersectionProfile
  runs: { fixed: Run; adaptive: Run }
}

export type Mode = 'fixed' | 'adaptive'

export const ReplayContext = createContext<Replay | null>(null)

export function useReplay(): Replay {
  const r = useContext(ReplayContext)
  if (!r) throw new Error('replay is not loaded')
  return r
}

export function useLoadReplay() {
  const [data, setData] = useState<Replay | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    fetch('/replay.json')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`replay.json: HTTP ${r.status}`))))
      .then(setData)
      .catch((e: Error) => setError(`${e.message}. Создайте запись: backend/.venv/bin/python presentation/scripts/export_replay.py`))
  }, [])
  return { data, error }
}

// Одни часы на все холсты: оба режима проигрываются синхронно, как в эксперименте.
const SPEED = 1.6
const t0 = performance.now()
const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches

export function replayTime(r: Replay): number {
  const dur = (r.runs.fixed.frames.length - 1) * r.frameDt
  if (reduced) return dur / 2
  return (((performance.now() - t0) / 1000) * SPEED) % dur
}

export function frameAt(r: Replay, mode: Mode, t: number): Frame {
  const frames = r.runs[mode].frames
  return frames[Math.min(frames.length - 1, Math.floor(t / r.frameDt))]
}

/** Текущий кадр для подписей и счётчиков (≈ 8 обновлений в секунду, не на каждый кадр анимации). */
export function useLiveFrame(mode: Mode): Frame {
  const r = useReplay()
  const [f, setF] = useState(() => frameAt(r, mode, replayTime(r)))
  useEffect(() => {
    const id = setInterval(() => setF(frameAt(r, mode, replayTime(r))), 125)
    return () => clearInterval(id)
  }, [r, mode])
  return f
}
