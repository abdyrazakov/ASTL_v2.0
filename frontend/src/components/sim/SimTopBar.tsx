import clsx from 'clsx'
import type { ControllerMode, IntersectionProfile, SimProgress } from '../../api/simTypes'
import { EXPORT_FILES, simApi } from '../../api/simClient'
import { formatDuration } from '../../lib/format'

const SPEEDS = [1, 5, 50]
const DURATIONS: { label: string; value: number | null }[] = [
  { label: '10 мин', value: 600 },
  { label: '30 мин', value: 1800 },
  { label: '1 ч', value: 3600 },
  { label: '2 ч', value: 7200 },
  { label: '∞', value: null },
]

const STATE_LABELS: Record<string, string> = {
  STARTUP_ALL_RED: 'старт: всё красное',
  GREEN: 'зелёный',
  YELLOW: 'жёлтый',
  ALL_RED: 'all-red (освобождение)',
  FAULT: 'FAULT — всё красное',
}

export function SimTopBar({
  profiles, profileId, onProfileChange, profile, progress,
  mode, onModeChange, speed, onSpeedChange, seed, onSeedChange, duration, onDurationChange,
  onStart, onPause, onResume, onStop, canStart, starting, onFullscreen,
}: {
  profiles: IntersectionProfile[]
  profileId: string | null
  onProfileChange: (id: string | null) => void
  profile: IntersectionProfile | null
  progress: SimProgress | null
  mode: ControllerMode
  onModeChange: (m: ControllerMode) => void
  speed: number
  onSpeedChange: (s: number) => void
  seed: number
  onSeedChange: (s: number) => void
  duration: number | null
  onDurationChange: (d: number | null) => void
  onStart: () => void
  onPause: () => void
  onResume: () => void
  onStop: () => void
  canStart: boolean
  starting: boolean
  onFullscreen: () => void
}) {
  const status = progress?.status
  const isRunning = status === 'running'
  const isPaused = status === 'paused'
  const isActive = isRunning || isPaused || status === 'queued'
  const finished = status === 'completed' || status === 'stopped' || status === 'error'
  const phaseName = (id: string | null | undefined) =>
    (id && profile?.phases.find((p) => p.id === id)?.name) || id || '—'

  return (
    <div className="flex flex-col border-b border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-center gap-3 px-3 py-2 flex-wrap text-sm">
        <label className="text-[var(--text-muted)]">Перекрёсток:</label>
        <select value={profileId ?? ''} disabled={isActive}
          onChange={(e) => onProfileChange(e.target.value || null)}
          className="bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1 disabled:opacity-50 max-w-[16rem]">
          <option value="">— выберите —</option>
          {profiles.map((p) => <option key={p.profile_id} value={p.profile_id}>{p.name}</option>)}
        </select>

        <label className="text-[var(--text-muted)]" title="Одинаковый seed = одинаковый трафик">seed:</label>
        <input type="number" value={seed} disabled={isActive}
          onChange={(e) => onSeedChange(Number(e.target.value) || 0)}
          className="w-20 bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1 font-mono-tab disabled:opacity-50" />

        <label className="text-[var(--text-muted)]">длительность:</label>
        <select value={duration ?? 'inf'} disabled={isActive}
          onChange={(e) => onDurationChange(e.target.value === 'inf' ? null : Number(e.target.value))}
          className="bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1 disabled:opacity-50">
          {DURATIONS.map((d) => <option key={d.label} value={d.value ?? 'inf'}>{d.label}</option>)}
        </select>

        <div className="w-px h-5 bg-[var(--border)] mx-1" />

        <Segmented
          label="Контроллер"
          value={mode}
          options={[{ v: 'fixed', label: 'фиксированный' }, { v: 'adaptive', label: 'адаптивный' }]}
          onChange={(v) => onModeChange(v as ControllerMode)}
        />
        <Segmented
          label="Скорость"
          value={String(speed)}
          options={SPEEDS.map((s) => ({ v: String(s), label: `×${s}` }))}
          onChange={(v) => onSpeedChange(Number(v))}
        />

        <div className="flex-1" />

        <div className="flex items-center gap-1.5">
          {!isActive && (
            <button onClick={onStart} disabled={!canStart || starting}
              className="px-3 py-1.5 rounded-md bg-[var(--accent-teal-dim)] border border-[var(--accent-teal)] text-white disabled:opacity-40">
              {starting ? 'Запуск…' : finished ? '▶ Новый прогон' : '▶ Запустить'}
            </button>
          )}
          {isRunning && <button onClick={onPause} className="px-3 py-1.5 rounded-md border border-[var(--border-strong)]">⏸ Пауза</button>}
          {isPaused && <button onClick={onResume} className="px-3 py-1.5 rounded-md border border-[var(--accent-teal)] text-[var(--accent-teal)]">▶ Продолжить</button>}
          {(isRunning || isPaused) && (
            <button onClick={onStop} className="px-3 py-1.5 rounded-md border border-[var(--accent-red)]/50 text-[var(--accent-red)]">■ Остановить</button>
          )}
          {progress && (
            <details className="relative">
              <summary className="list-none cursor-pointer px-3 py-1.5 rounded-md border border-[var(--border-strong)] text-sm">⬇ Экспорт</summary>
              <div className="absolute right-0 mt-1 z-20 w-64 rounded-md border border-[var(--border-strong)] bg-[var(--surface-raised)] p-2 flex flex-col gap-0.5 shadow-xl">
                <p className="text-[10px] text-[var(--text-faint)] px-1 pb-1">output/{progress.run_id.slice(0, 8)}…/</p>
                {EXPORT_FILES.map((f) => (
                  <a key={f} href={simApi.exportUrl(progress.run_id, f)} download
                    className="text-xs px-1.5 py-1 rounded hover:bg-[var(--surface)] font-mono-tab text-[var(--text-muted)] hover:text-[var(--text)]">
                    {f}
                  </a>
                ))}
              </div>
            </details>
          )}
          <button onClick={onFullscreen} title="Полноэкранный режим" className="px-2.5 py-1.5 rounded-md border border-[var(--border)] text-[var(--text-muted)]">⛶</button>
        </div>
      </div>

      {/* строка состояния прогона */}
      <div className="flex items-center gap-4 px-3 py-1.5 border-t border-[var(--border)] text-xs flex-wrap min-h-[34px]">
        <StatusBadge status={status} />
        {progress ? (
          <>
            <span className="font-mono-tab text-[var(--text-muted)]">
              модельное время {formatDuration(progress.sim_time_sec)}
              {progress.duration_sec ? ` / ${formatDuration(progress.duration_sec)}` : ' (бесконечный режим)'}
            </span>
            {progress.duration_sec ? (
              <div className="w-28 h-1.5 rounded-full bg-[var(--surface-sunken)] overflow-hidden">
                <div className="h-full bg-[var(--accent-teal)]"
                  style={{ width: `${Math.min(100, (progress.sim_time_sec / progress.duration_sec) * 100)}%` }} />
              </div>
            ) : null}
            {isActive && (
              <span className="text-[var(--text-faint)] font-mono-tab">
                фактически ×{progress.realtime_ratio.toFixed(1)}
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <span className="text-[var(--text-faint)]">сигналы:</span>
              <span className={clsx(progress.signal_state === 'FAULT' && 'text-[var(--accent-red)] font-semibold')}>
                {STATE_LABELS[progress.signal_state] ?? progress.signal_state}
              </span>
            </span>
            <span>
              <span className="text-[var(--text-faint)]">фаза: </span>
              <span className="font-medium">
                {progress.active_phase ? phaseName(progress.active_phase)
                  : progress.next_phase ? `→ ${phaseName(progress.next_phase)}` : '—'}
              </span>
              {progress.phase_remaining_sec != null && (
                <span className="font-mono-tab text-[var(--text-muted)]">
                  {' '}· осталось {progress.phase_remaining_is_estimate ? '≈' : ''}{progress.phase_remaining_sec.toFixed(1)} с
                  {progress.phase_remaining_is_estimate && <span className="text-[var(--text-faint)]"> (расчётное)</span>}
                </span>
              )}
            </span>
            <span className="text-[var(--text-faint)]">
              режим: <span className="text-[var(--text)]">{progress.controller_mode === 'adaptive' ? 'адаптивный' : 'фиксированный'}</span>
              {progress.mode_switches > 0 && ` (переключений: ${progress.mode_switches})`}
              {' '}· seed {progress.seed}
            </span>
          </>
        ) : (
          <span className="text-[var(--text-faint)]">Прогон не запущен. Выберите перекрёсток, режим и нажмите «Запустить».</span>
        )}
      </div>
      {progress?.status === 'error' && progress.error_message && (
        <div className="px-3 py-1.5 bg-[var(--accent-red)]/15 border-t border-[var(--accent-red)]/30 text-xs text-[var(--accent-red)]">
          Ошибка прогона: {progress.error_message}
        </div>
      )}
    </div>
  )
}

function Segmented({ label, value, options, onChange }: {
  label: string
  value: string
  options: { v: string; label: string }[]
  onChange: (v: string) => void
}) {
  return (
    <div className="flex items-center gap-1.5" role="group" aria-label={label}>
      <span className="text-[var(--text-muted)]">{label}:</span>
      <div className="flex rounded-md border border-[var(--border)] overflow-hidden">
        {options.map((o) => (
          <button key={o.v} type="button" onClick={() => onChange(o.v)} aria-pressed={value === o.v}
            className={clsx('px-2.5 py-1 text-xs transition-colors',
              value === o.v ? 'bg-[var(--accent-teal-dim)] text-white' : 'text-[var(--text-muted)] hover:text-[var(--text)]')}>
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status?: string }) {
  const map: Record<string, { label: string; color: string; pulse?: boolean }> = {
    queued: { label: 'В очереди', color: 'var(--accent-amber)' },
    running: { label: 'Выполняется', color: 'var(--accent-teal)', pulse: true },
    paused: { label: 'Пауза (время модели стоит)', color: 'var(--accent-amber)' },
    completed: { label: 'Завершено', color: 'var(--accent-teal)' },
    stopped: { label: 'Остановлено', color: 'var(--text-faint)' },
    error: { label: 'Ошибка', color: 'var(--accent-red)' },
  }
  const info = status ? map[status] : { label: 'Нет прогона', color: 'var(--text-faint)' }
  return (
    <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-[var(--border)]">
      <span className={`w-1.5 h-1.5 rounded-full ${info.pulse ? 'live-dot' : ''}`} style={{ background: info.color }} />
      {info.label}
    </span>
  )
}
