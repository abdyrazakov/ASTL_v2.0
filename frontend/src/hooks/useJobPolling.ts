import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { JobProgress, TrafficSnapshot } from '../api/types'

export function useJobPolling(runId: string | null) {
  const [progress, setProgress] = useState<JobProgress | null>(null)
  const [snapshot, setSnapshot] = useState<TrafficSnapshot | null>(null)
  const [history, setHistory] = useState<TrafficSnapshot[]>([])
  const lastTsRef = useRef(0)

  useEffect(() => {
    setProgress(null)
    setSnapshot(null)
    setHistory([])
    lastTsRef.current = 0
    if (!runId) return

    let stopped = false
    let timer: ReturnType<typeof setTimeout>

    async function tick() {
      try {
        const [p, s] = await Promise.all([api.getJob(runId as string), api.getSnapshot(runId as string).catch(() => null)])
        if (stopped) return
        setProgress(p)
        if (s) setSnapshot(s)
        const more = await api.getHistory(runId as string, lastTsRef.current)
        if (more.length) {
          setHistory((prev) => [...prev, ...more])
          lastTsRef.current = more[more.length - 1].timestamp_sec + 0.01
        }
      } catch {
        // игнорируем единичный сбой опроса — повторим на следующем тике
      }
      if (!stopped) timer = setTimeout(tick, 1000)
    }
    tick()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [runId])

  return { progress, snapshot, history }
}
