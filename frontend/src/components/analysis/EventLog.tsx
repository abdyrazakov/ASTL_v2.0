import { useMemo } from 'react'
import type { TrafficSnapshot } from '../../api/types'
import { formatDuration } from '../../lib/format'

interface LogEntry {
  t: number
  text: string
  color: string
}

const MAX_EVENTS = 40

export function EventLog({ history }: { history: TrafficSnapshot[] }) {
  const events = useMemo(() => {
    const out: LogEntry[] = []
    let prevCrossings = new Map<string, number>()
    let prevQueued = new Map<string, number>()
    let prevNames = new Map<string, { name: string; color: string }>()

    for (const snap of history) {
      for (const lane of snap.lanes) {
        prevNames.set(lane.lane_id, { name: lane.name, color: lane.color })
        const prevC = prevCrossings.get(lane.lane_id) ?? 0
        const deltaC = lane.total_crossings - prevC
        if (deltaC > 0) {
          out.push({ t: snap.timestamp_sec, text: `${lane.name}: +${deltaC} пересечение линии`, color: lane.color })
        }
        prevCrossings.set(lane.lane_id, lane.total_crossings)

        const prevQ = prevQueued.get(lane.lane_id) ?? 0
        if (lane.queued > prevQ) {
          out.push({ t: snap.timestamp_sec, text: `${lane.name}: машина встала в очередь (${lane.queued})`, color: lane.color })
        } else if (lane.queued < prevQ) {
          out.push({ t: snap.timestamp_sec, text: `${lane.name}: очередь продвинулась (${lane.queued})`, color: lane.color })
        }
        prevQueued.set(lane.lane_id, lane.queued)
      }
    }
    return out.slice(-MAX_EVENTS).reverse()
  }, [history])

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-3 flex flex-col overflow-hidden h-full">
      <div className="text-xs text-[var(--text-muted)] mb-1.5 shrink-0">
        События (последние {MAX_EVENTS})
      </div>
      <div className="flex-1 overflow-y-auto flex flex-col gap-1">
        {events.length === 0 && <p className="text-xs text-[var(--text-faint)]">Пока нет событий.</p>}
        {events.map((e, i) => (
          <div key={i} className="flex items-baseline gap-2 text-xs">
            <span className="font-mono-tab text-[var(--text-faint)] shrink-0">{formatDuration(e.t)}</span>
            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: e.color }} />
            <span className="text-[var(--text-muted)] truncate">{e.text}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
