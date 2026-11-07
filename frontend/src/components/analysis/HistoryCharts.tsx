import { useMemo } from 'react'
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { TrafficSnapshot } from '../../api/types'
import { formatDuration } from '../../lib/format'

const BIN_SEC = 10

export function HistoryCharts({
  history, selectedLaneId, selectedLaneColor, currentTime,
}: {
  history: TrafficSnapshot[]
  selectedLaneId: string | null
  selectedLaneColor: string
  currentTime: number | null
}) {
  const queueSeries = useMemo(() => {
    return history.map((snap) => {
      const lane = selectedLaneId ? snap.lanes.find((l) => l.lane_id === selectedLaneId) : null
      const queued = lane ? lane.queued : snap.lanes.reduce((s, l) => s + l.queued, 0)
      return { t: snap.timestamp_sec, queued }
    })
  }, [history, selectedLaneId])

  const crossingBins = useMemo(() => {
    const bins = new Map<number, number>()
    let prevTotals = new Map<string, number>()
    for (const snap of history) {
      const relevant = selectedLaneId ? snap.lanes.filter((l) => l.lane_id === selectedLaneId) : snap.lanes
      let deltaSum = 0
      for (const lane of relevant) {
        const prev = prevTotals.get(lane.lane_id) ?? 0
        deltaSum += Math.max(0, lane.total_crossings - prev)
      }
      for (const lane of snap.lanes) prevTotals.set(lane.lane_id, lane.total_crossings)
      const bin = Math.floor(snap.timestamp_sec / BIN_SEC) * BIN_SEC
      bins.set(bin, (bins.get(bin) ?? 0) + deltaSum)
    }
    return [...bins.entries()].sort((a, b) => a[0] - b[0]).map(([t, count]) => ({ t, count }))
  }, [history, selectedLaneId])

  return (
    <div className="grid grid-cols-2 gap-3 p-3 h-full">
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-3 flex flex-col">
        <div className="text-xs text-[var(--text-muted)] mb-1">
          История очереди {selectedLaneId ? '— выбранная полоса' : '— сумма по всем полосам'}
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={queueSeries} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="t" tickFormatter={formatDuration} stroke="var(--text-faint)" fontSize={11} tick={{ fill: 'var(--text-faint)' }} />
            <YAxis allowDecimals={false} stroke="var(--text-faint)" fontSize={11} tick={{ fill: 'var(--text-faint)' }} width={28} />
            <Tooltip
              labelFormatter={(t) => `t = ${formatDuration(Number(t))}`}
              contentStyle={{ background: 'var(--surface-raised)', border: '1px solid var(--border)', fontSize: 12 }}
            />
            <Line type="stepAfter" dataKey="queued" stroke={selectedLaneId ? selectedLaneColor : 'var(--accent-teal)'} dot={false} strokeWidth={2} isAnimationActive={false} />
            {currentTime !== null && (
              <Line
                data={[{ t: currentTime, queued: 0 }, { t: currentTime, queued: 999 }]}
                dataKey="queued" stroke="var(--text-faint)" strokeDasharray="3 3" dot={false} isAnimationActive={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-3 flex flex-col">
        <div className="text-xs text-[var(--text-muted)] mb-1">
          Пересечения по интервалам {BIN_SEC}с {selectedLaneId ? '— выбранная полоса' : '— все полосы'}
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={crossingBins} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="t" tickFormatter={formatDuration} stroke="var(--text-faint)" fontSize={11} tick={{ fill: 'var(--text-faint)' }} />
            <YAxis allowDecimals={false} stroke="var(--text-faint)" fontSize={11} tick={{ fill: 'var(--text-faint)' }} width={28} />
            <Tooltip
              labelFormatter={(t) => `интервал от ${formatDuration(Number(t))}`}
              contentStyle={{ background: 'var(--surface-raised)', border: '1px solid var(--border)', fontSize: 12 }}
            />
            <Bar dataKey="count" fill={selectedLaneId ? selectedLaneColor : 'var(--accent-sky)'} isAnimationActive={false} radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
