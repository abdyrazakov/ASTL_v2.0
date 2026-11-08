import { useEffect, useRef, useState } from 'react'
import { simApi } from '../api/simClient'
import type { GreenRecord, Scene, SimProgress, SimSnapshot } from '../api/simTypes'

const ACTIVE = new Set(['queued', 'running', 'paused'])

/** Опрос прогона: статус/снимок/история/журнал фаз — раз в секунду (как
 * useJobPolling этапа 1), 2D-сцена — ~7 раз в секунду, пока прогон идёт. */
export function useSimulationPolling(runId: string | null) {
  const [progress, setProgress] = useState<SimProgress | null>(null)
  const [snapshot, setSnapshot] = useState<SimSnapshot | null>(null)
  const [history, setHistory] = useState<SimSnapshot[]>([])
  const [greens, setGreens] = useState<GreenRecord[]>([])
  const [scene, setScene] = useState<Scene | null>(null)
  const lastTsRef = useRef(0)
  const lastGreenRef = useRef(0)
  const statusRef = useRef<string | null>(null)

  useEffect(() => {
    setProgress(null)
    setSnapshot(null)
    setHistory([])
    setGreens([])
    setScene(null)
    lastTsRef.current = 0
    lastGreenRef.current = 0
    statusRef.current = null
    if (!runId) return
    const id = runId

    let stopped = false
    let slowTimer: ReturnType<typeof setTimeout>
    let fastTimer: ReturnType<typeof setTimeout>

    async function slow() {
      try {
        const [p, s] = await Promise.all([simApi.get(id), simApi.snapshot(id).catch(() => null)])
        if (stopped) return
        setProgress(p)
        statusRef.current = p.status
        if (s) setSnapshot(s)
        const more = await simApi.history(id, lastTsRef.current)
        if (!stopped && more.length) {
          setHistory((prev) => [...prev, ...more])
          lastTsRef.current = more[more.length - 1].timestamp_sec + 0.01
        }
        const g = await simApi.phaseLog(id, lastGreenRef.current)
        if (!stopped && g.length) {
          setGreens((prev) => [...prev, ...g])
          lastGreenRef.current = g[g.length - 1].end_sec + 0.001
        }
      } catch {
        // единичный сбой опроса — повторим на следующем тике
      }
      if (!stopped) slowTimer = setTimeout(slow, 1000)
    }

    async function fast() {
      const active = statusRef.current === null || ACTIVE.has(statusRef.current)
      if (active) {
        try {
          const sc = await simApi.scene(id)
          if (!stopped) setScene(sc)
        } catch {
          // прогон мог исчезнуть после перезапуска сервера
        }
      }
      if (!stopped) fastTimer = setTimeout(fast, active && statusRef.current !== 'paused' ? 140 : 600)
    }

    slow()
    fast()
    return () => {
      stopped = true
      clearTimeout(slowTimer)
      clearTimeout(fastTimer)
    }
  }, [runId])

  return { progress, snapshot, history, greens, scene }
}
