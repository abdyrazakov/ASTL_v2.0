import { useMemo } from 'react'
import {
  CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { GreenRecord, IntersectionProfile, SimSnapshot } from '../../api/simTypes'
import { formatDuration } from '../../lib/format'
import { PALETTE } from '../../lib/intersectionGeometry'

const REASONS: Record<string, string> = {
  fixed: 'по расписанию',
  gap_out: 'gap-out (поток иссяк)',
  queue_clear: 'очередь разъехалась',
  max_out: 'max_green',
  starvation: 'защита от голодания',
  chaos: 'тест',
}

/** Длительность каждого завершённого зелёного по фазам во времени — главный
 * демонстрационный график этапа: в фиксированном режиме точки лежат на
 * горизонтальных линиях, в адаптивном — следуют за спросом. */
export function PhaseGreenChart({ greens, profile, history }: {
  greens: GreenRecord[]
  profile: IntersectionProfile
  history: SimSnapshot[]
}) {
  const series = useMemo(() => profile.phases.map((p, i) => ({
    id: p.id,
    name: p.name,
    color: PALETTE[i % PALETTE.length],
    data: greens.filter((g) => g.phase_id === p.id).map((g) => ({ t: g.start_sec, d: g.duration_sec, reason: g.reason })),
  })), [greens, profile])

  // моменты переключения режима — из истории снимков (поле controller_mode)
  const switches = useMemo(() => {
    const out: { t: number; mode: string }[] = []
    let prev: string | null = null
    for (const s of history) {
      if (prev !== null && s.controller_mode !== prev) out.push({ t: s.timestamp_sec, mode: s.controller_mode })
      prev = s.controller_mode
    }
    return out
  }, [history])

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-3 flex flex-col h-full">
      <div className="text-xs text-[var(--text-muted)] mb-1">Длительность зелёного по фазам (каждая точка — один зелёный)</div>
      {greens.length === 0 ? (
        <p className="text-xs text-[var(--text-faint)] mt-2">Появится после первого завершённого зелёного.</p>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" />
            <XAxis type="number" dataKey="t" tickFormatter={formatDuration} stroke="var(--text-faint)" fontSize={11}
              tick={{ fill: 'var(--text-faint)' }} domain={['dataMin', 'dataMax']} />
            <YAxis type="number" dataKey="d" unit="с" stroke="var(--text-faint)" fontSize={11}
              tick={{ fill: 'var(--text-faint)' }} width={44} domain={[0, 'auto']} />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              contentStyle={{ background: 'var(--surface-raised)', border: '1px solid var(--border)', fontSize: 12 }}
              formatter={(value, name, item) => {
                if (name === 't') return [formatDuration(Number(value)), 'начало']
                const reason = (item?.payload as { reason?: string })?.reason
                return [`${Number(value).toFixed(1)} с${reason ? ` · ${REASONS[reason] ?? reason}` : ''}`, 'зелёный']
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {switches.map((s) => (
              <ReferenceLine key={s.t} x={s.t} stroke="var(--accent-amber)" strokeDasharray="4 3"
                label={{ value: s.mode === 'adaptive' ? '→ адапт.' : '→ фикс.', fill: 'var(--accent-amber)', fontSize: 10, position: 'insideTopLeft' }} />
            ))}
            {series.map((s) => (
              <Scatter key={s.id} name={s.name} data={s.data} fill={s.color} line={{ stroke: s.color, strokeOpacity: 0.4 }}
                isAnimationActive={false} />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
