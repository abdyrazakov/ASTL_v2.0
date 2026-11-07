import clsx from 'clsx'
import type { LayerVisibility, Tool } from './EditorCanvas'

const HINTS: Record<Tool, string> = {
  select: 'Клик по полосе — выделить. Перетаскивайте точки. Двойной клик по вершине — удалить, по границе полигона — добавить вершину.',
  draw_observation: 'Кликайте, чтобы добавить вершины полигона полосы. Enter — завершить (от 3 точек). Esc — отменить.',
  draw_queue: 'Кликайте, чтобы задать зону очереди внутри полосы. Enter — завершить. Esc — отменить.',
  draw_line: 'Кликните дважды — концы линии подсчёта, затем один раз — точку направления («+» сторона). Enter — завершить.',
}

function IconBtn({
  active, onClick, title, disabled, children,
}: { active?: boolean; onClick: () => void; title: string; disabled?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={clsx(
        'px-2.5 py-1.5 rounded-md text-sm border transition-colors disabled:opacity-35 disabled:cursor-not-allowed',
        active
          ? 'bg-[var(--accent-teal-dim)] border-[var(--accent-teal)] text-white'
          : 'border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)] hover:border-[var(--border-strong)]',
      )}
    >
      {children}
    </button>
  )
}

export function Toolbar({
  tool,
  visibility,
  onToggleVisibility,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  onResetView,
}: {
  tool: Tool
  visibility: LayerVisibility
  onToggleVisibility: (key: keyof LayerVisibility) => void
  onUndo: () => void
  onRedo: () => void
  canUndo: boolean
  canRedo: boolean
  onResetView: () => void
}) {
  return (
    <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-3 py-2 flex-wrap">
      <div className="flex items-center gap-1.5">
        <IconBtn active={!canUndo ? false : undefined} onClick={onUndo} title="Отменить (Ctrl+Z)" disabled={!canUndo}>
          ↺ Отменить
        </IconBtn>
        <IconBtn onClick={onRedo} title="Повторить (Ctrl+Shift+Z)" disabled={!canRedo}>
          ↻ Повторить
        </IconBtn>
      </div>
      <div className="w-px h-5 bg-[var(--border)]" />
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-[var(--text-faint)] mr-1">Слои:</span>
        <IconBtn active={visibility.lanes} onClick={() => onToggleVisibility('lanes')} title="Полосы">
          Полосы
        </IconBtn>
        <IconBtn active={visibility.queueZones} onClick={() => onToggleVisibility('queueZones')} title="Зоны очереди">
          Очереди
        </IconBtn>
        <IconBtn active={visibility.lines} onClick={() => onToggleVisibility('lines')} title="Линии подсчёта">
          Линии
        </IconBtn>
      </div>
      <div className="w-px h-5 bg-[var(--border)]" />
      <IconBtn onClick={onResetView} title="Сбросить масштаб и положение">
        ⤢ По размеру
      </IconBtn>
      <div className="flex-1" />
      <div className="text-xs text-[var(--text-muted)] max-w-md text-right leading-snug">
        {HINTS[tool]}
      </div>
    </div>
  )
}
