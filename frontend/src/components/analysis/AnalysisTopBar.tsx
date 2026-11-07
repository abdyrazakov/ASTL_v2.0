import type { JobProgress, Profile, VideoInfo } from '../../api/types'
import { formatDuration } from '../../lib/format'

export function AnalysisTopBar({
  videos, profiles, videoId, profileId, onVideoChange, onProfileChange,
  progress, onStart, onPause, onResume, onStop, canStart, onFullscreen, starting,
}: {
  videos: VideoInfo[]
  profiles: Profile[]
  videoId: string | null
  profileId: string | null
  onVideoChange: (id: string | null) => void
  onProfileChange: (id: string | null) => void
  progress: JobProgress | null
  onStart: () => void
  onPause: () => void
  onResume: () => void
  onStop: () => void
  canStart: boolean
  onFullscreen: () => void
  starting: boolean
}) {
  const status = progress?.status
  const isRunning = status === 'running'
  const isPaused = status === 'paused'
  const isActive = isRunning || isPaused || status === 'queued'

  return (
    <div className="flex flex-col border-b border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-center gap-3 px-3 py-2 flex-wrap text-sm">
        <label className="text-[var(--text-muted)]">Видео:</label>
        <select
          value={videoId ?? ''}
          disabled={isActive}
          onChange={(e) => onVideoChange(e.target.value || null)}
          className="bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1 disabled:opacity-50"
        >
          <option value="">— выберите —</option>
          {videos.map((v) => <option key={v.video_id} value={v.video_id}>{v.filename}</option>)}
        </select>

        <label className="text-[var(--text-muted)]">Профиль:</label>
        <select
          value={profileId ?? ''}
          disabled={isActive}
          onChange={(e) => onProfileChange(e.target.value || null)}
          className="bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1 disabled:opacity-50"
        >
          <option value="">— выберите —</option>
          {profiles.map((p) => <option key={p.profile_id} value={p.profile_id}>{p.name}</option>)}
        </select>

        <div className="w-px h-5 bg-[var(--border)] mx-1" />

        <StatusBadge status={status} />

        {progress && (
          <span className="font-mono-tab text-xs text-[var(--text-muted)]">
            {formatDuration(progress.video_time_sec)} / {formatDuration(progress.source_duration_sec)}
          </span>
        )}
        {progress && progress.frames_total > 0 && (
          <div className="flex items-center gap-1.5">
            <div className="w-28 h-1.5 rounded-full bg-[var(--surface-sunken)] overflow-hidden">
              <div
                className="h-full bg-[var(--accent-teal)]"
                style={{ width: `${Math.min(100, (progress.video_time_sec / progress.source_duration_sec) * 100)}%` }}
              />
            </div>
          </div>
        )}
        {progress && progress.processing_fps > 0 && (
          <span className="text-xs text-[var(--text-faint)] font-mono-tab">
            {progress.processing_fps.toFixed(1)} к/с обработки · видео {progress.source_fps.toFixed(0)} к/с ·
            {' '}{progress.realtime_ratio >= 1
              ? `${progress.realtime_ratio.toFixed(2)}× реального времени`
              : `${progress.realtime_ratio.toFixed(2)}× (медленнее реального времени)`}
          </span>
        )}

        <div className="flex-1" />

        <div className="flex items-center gap-1.5">
          {!isActive && status !== 'completed' && (
            <button
              onClick={onStart}
              disabled={!canStart || starting}
              className="px-3 py-1.5 rounded-md bg-[var(--accent-teal-dim)] border border-[var(--accent-teal)] text-white disabled:opacity-40"
            >
              {starting ? 'Запуск…' : '▶ Запустить анализ'}
            </button>
          )}
          {isRunning && (
            <button onClick={onPause} className="px-3 py-1.5 rounded-md border border-[var(--border-strong)]">⏸ Пауза</button>
          )}
          {isPaused && (
            <button onClick={onResume} className="px-3 py-1.5 rounded-md border border-[var(--accent-teal)] text-[var(--accent-teal)]">▶ Продолжить</button>
          )}
          {(isRunning || isPaused) && (
            <button onClick={onStop} className="px-3 py-1.5 rounded-md border border-[var(--accent-red)]/50 text-[var(--accent-red)]">■ Остановить</button>
          )}
          {status === 'completed' && progress && (
            <a
              href={`/output/${progress.run_id}/annotated_video.mp4`} download
              className="px-3 py-1.5 rounded-md border border-[var(--border-strong)] text-sm"
            >
              ⬇ Экспорт
            </a>
          )}
          <button onClick={onFullscreen} title="Полноэкранный режим демонстрации" className="px-2.5 py-1.5 rounded-md border border-[var(--border)] text-[var(--text-muted)]">
            ⛶
          </button>
        </div>
      </div>
      {progress?.status === 'error' && progress.error_message && (
        <div className="px-3 py-1.5 bg-[var(--accent-red)]/15 border-t border-[var(--accent-red)]/30 text-xs text-[var(--accent-red)]">
          Ошибка задания: {progress.error_message}
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status?: string }) {
  const map: Record<string, { label: string; color: string; pulse?: boolean }> = {
    queued: { label: 'В очереди', color: 'var(--accent-amber)' },
    running: { label: 'Выполняется', color: 'var(--accent-teal)', pulse: true },
    paused: { label: 'Пауза', color: 'var(--accent-amber)' },
    completed: { label: 'Завершено', color: 'var(--accent-teal)' },
    stopped: { label: 'Остановлено', color: 'var(--text-faint)' },
    error: { label: 'Ошибка', color: 'var(--accent-red)' },
  }
  const info = status ? map[status] : { label: 'Нет задания', color: 'var(--text-faint)' }
  return (
    <span className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border border-[var(--border)]">
      <span className={`w-1.5 h-1.5 rounded-full ${info.pulse ? 'live-dot' : ''}`} style={{ background: info.color }} />
      {info.label}
    </span>
  )
}
