import type { ReactNode } from 'react'
import clsx from 'clsx'
import type { LaneSnapshot } from '../../api/types'
import { LOAD_COLORS, LOAD_LABELS, laneLoadLevel } from '../../lib/format'

// `extra` (необязательно) — дополнительный блок внутри карточки; этап 2 выводит
// там новые показатели симуляции, не меняя общую часть карточки этапа 1.
export function LaneCards<T extends LaneSnapshot = LaneSnapshot>({
  lanes, selectedLaneId, onSelect, extra, emptyText,
}: {
  lanes: T[]
  selectedLaneId: string | null
  onSelect: (id: string | null) => void
  extra?: (lane: T) => ReactNode
  emptyText?: string
}) {
  return (
    <div className="flex flex-col gap-2 p-3 overflow-y-auto">
      {lanes.length === 0 && (
        <p className="text-sm text-[var(--text-faint)]">{emptyText ?? 'Данные появятся после начала анализа.'}</p>
      )}
      {lanes.map((lane) => {
        const level = laneLoadLevel(lane.queued, lane.avg_wait_sec)
        const selected = lane.lane_id === selectedLaneId
        return (
          <button
            key={lane.lane_id}
            onClick={() => onSelect(selected ? null : lane.lane_id)}
            className={clsx(
              'text-left rounded-md border bg-[var(--surface)] p-3 transition-colors',
              selected ? 'border-[var(--accent-teal)]' : 'border-[var(--border)] hover:border-[var(--border-strong)]',
            )}
            style={{ borderLeftWidth: 4, borderLeftColor: lane.color }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium truncate">{lane.name}</span>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                style={{ color: LOAD_COLORS[level], border: `1px solid ${LOAD_COLORS[level]}55` }}
              >
                нагрузка: {LOAD_LABELS[level]}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
              <Metric label="машин сейчас" value={lane.vehicles} />
              <Metric label="в очереди" value={lane.queued} />
              <Metric
                label="ожидание сред."
                value={`${lane.avg_wait_sec.toFixed(1)}с`}
                hint={lane.wait_sample_size > 0 ? `n=${lane.wait_sample_size}` : undefined}
              />
              <Metric label="ожидание макс." value={`${lane.max_wait_sec.toFixed(1)}с`} />
              <Metric
                label={`пересечения (${lane.flow_window_available_sec < lane.flow_window_target_sec
                  ? `${lane.flow_window_available_sec.toFixed(0)}с`
                  : `${lane.flow_window_target_sec.toFixed(0)}с`})`}
                value={lane.flow_count_window}
              />
              <Metric label="всего пересечений" value={lane.total_crossings} />
            </div>
            {lane.queue_truncated_by_frame && (
              <p className="text-[10px] text-[var(--accent-amber)] mt-1.5">очередь в зоне наблюдения (кадр обрезает её)</p>
            )}
            {extra?.(lane)}
          </button>
        )
      })}
    </div>
  )
}

function Metric({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div>
      <div className="text-[var(--text-faint)] leading-tight">{label}</div>
      <div className="font-mono-tab text-[var(--text)] text-[13px]">
        {value} {hint && <span className="text-[var(--text-faint)] text-[10px]">{hint}</span>}
      </div>
    </div>
  )
}
