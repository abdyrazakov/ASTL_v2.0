import type { LaneSnapshot } from '../../api/types'

export function DemandRanking({ lanes }: { lanes: LaneSnapshot[] }) {
  const ranked = [...lanes].sort((a, b) => {
    const scoreA = a.queued * 10 + a.avg_wait_sec
    const scoreB = b.queued * 10 + b.avg_wait_sec
    return scoreB - scoreA
  })

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-3 h-full overflow-y-auto">
      <div className="text-xs text-[var(--text-muted)] mb-1.5">Спрос на обслуживание</div>
      <p className="text-[10px] text-[var(--text-faint)] mb-2 leading-relaxed">
        Ранжирование по наблюдаемой очереди и ожиданию. Это сводка текущей нагрузки, а не решение о
        переключении фаз светофора — подбор совместимых фаз относится к следующему этапу проекта.
      </p>
      <ol className="flex flex-col gap-1.5">
        {ranked.map((lane, i) => (
          <li key={lane.lane_id} className="flex items-center gap-2 text-xs">
            <span className="w-4 text-[var(--text-faint)] font-mono-tab">{i + 1}</span>
            <span className="w-2 h-2 rounded-sm shrink-0" style={{ background: lane.color }} />
            <span className="flex-1 truncate">{lane.name}</span>
            <span className="font-mono-tab text-[var(--text-muted)]">
              {lane.queued} оч. · {lane.avg_wait_sec.toFixed(0)}с
            </span>
          </li>
        ))}
        {ranked.length === 0 && <p className="text-xs text-[var(--text-faint)]">Нет данных.</p>}
      </ol>
    </div>
  )
}
