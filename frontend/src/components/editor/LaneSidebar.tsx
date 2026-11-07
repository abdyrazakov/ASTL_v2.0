import clsx from 'clsx'
import type { CountDirection, Lane, ReferencePointMode } from '../../api/types'

const REF_MODE_LABELS: Record<ReferencePointMode, string> = {
  bottom_center: 'низ по центру',
  bottom_left: 'низ слева',
  bottom_right: 'низ справа',
  center: 'центр рамки',
}

const DIR_LABELS: Record<CountDirection, string> = {
  positive: 'только в сторону стрелки',
  negative: 'только против стрелки',
  both: 'в обе стороны',
}

export function LaneSidebar({
  lanes,
  selectedLaneId,
  onSelect,
  onAddLane,
  addingLane,
  onDeleteLane,
  onRenameLane,
  onRecolorLane,
  onChangeDirection,
  onChangeRefMode,
}: {
  lanes: Lane[]
  selectedLaneId: string | null
  onSelect: (id: string | null) => void
  onAddLane: () => void
  addingLane: boolean
  onDeleteLane: (id: string) => void
  onRenameLane: (id: string, name: string) => void
  onRecolorLane: (id: string, color: string) => void
  onChangeDirection: (id: string, dir: CountDirection) => void
  onChangeRefMode: (id: string, mode: ReferencePointMode | null) => void
}) {
  const selected = lanes.find((l) => l.id === selectedLaneId) || null

  return (
    <div className="w-72 shrink-0 border-l border-[var(--border)] bg-[var(--surface)] flex flex-col overflow-hidden">
      <div className="p-3 border-b border-[var(--border)]">
        <button
          type="button"
          onClick={onAddLane}
          disabled={addingLane}
          className="w-full rounded-md bg-[var(--accent-teal-dim)] border border-[var(--accent-teal)] text-white text-sm py-2 font-medium disabled:opacity-50"
        >
          + Добавить полосу
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {lanes.length === 0 && (
          <p className="text-sm text-[var(--text-faint)] p-4 leading-relaxed">
            Полос пока нет. Нажмите «Добавить полосу» и обведите область наблюдения на кадре.
          </p>
        )}
        {lanes.map((lane) => (
          <button
            key={lane.id}
            onClick={() => onSelect(lane.id)}
            className={clsx(
              'w-full text-left px-3 py-2.5 border-b border-[var(--border)] flex items-center gap-2.5 transition-colors',
              lane.id === selectedLaneId ? 'bg-[var(--surface-raised)]' : 'hover:bg-[var(--surface-raised)]/50',
            )}
          >
            <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: lane.color }} />
            <span className="text-sm truncate flex-1">{lane.name}</span>
            <span className="text-[10px] text-[var(--text-faint)] font-mono-tab">{lane.id}</span>
          </button>
        ))}
      </div>

      {selected && (
        <div className="border-t border-[var(--border)] p-3 flex flex-col gap-3 bg-[var(--surface-raised)]">
          <div>
            <label className="text-xs text-[var(--text-muted)] block mb-1">Название полосы</label>
            <input
              value={selected.name}
              onChange={(e) => onRenameLane(selected.id, e.target.value)}
              className="w-full bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1.5 text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-[var(--text-muted)]">Цвет</label>
            <input
              type="color"
              value={selected.color}
              onChange={(e) => onRecolorLane(selected.id, e.target.value)}
              className="w-9 h-7 rounded border border-[var(--border)] bg-transparent"
            />
          </div>
          <div>
            <label className="text-xs text-[var(--text-muted)] block mb-1">Направление подсчёта</label>
            <select
              value={selected.count_line.direction}
              onChange={(e) => onChangeDirection(selected.id, e.target.value as CountDirection)}
              className="w-full bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1.5 text-sm"
            >
              {(Object.keys(DIR_LABELS) as CountDirection[]).map((d) => (
                <option key={d} value={d}>{DIR_LABELS[d]}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-[var(--text-muted)] block mb-1">Опорная точка (переопределение)</label>
            <select
              value={selected.reference_point_mode ?? ''}
              onChange={(e) => onChangeRefMode(selected.id, (e.target.value || null) as ReferencePointMode | null)}
              className="w-full bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1.5 text-sm"
            >
              <option value="">как в профиле по умолчанию</option>
              {(Object.keys(REF_MODE_LABELS) as ReferencePointMode[]).map((m) => (
                <option key={m} value={m}>{REF_MODE_LABELS[m]}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => onDeleteLane(selected.id)}
            className="mt-1 text-sm text-[var(--accent-red)] border border-[var(--accent-red)]/40 rounded py-1.5 hover:bg-[var(--accent-red)]/10"
          >
            Удалить полосу
          </button>
        </div>
      )}
    </div>
  )
}
