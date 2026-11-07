import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { JobProgress, Profile, RenderOptions } from '../../api/types'

const DEFAULT_OPTS: RenderOptions = {
  show_boxes: true, show_ids: true, show_trajectories: true,
  show_lanes: true, show_queue_zones: true, show_lines: true,
}

const TOGGLE_LABELS: [keyof RenderOptions, string][] = [
  ['show_boxes', 'Рамки'],
  ['show_ids', 'ID'],
  ['show_trajectories', 'Траектории'],
  ['show_lanes', 'Полосы'],
  ['show_queue_zones', 'Зоны очереди'],
  ['show_lines', 'Линии'],
]

export function VideoPanel({
  progress, profile, onSelectLane, selectedLaneId, onTimeUpdate,
}: {
  progress: JobProgress | null
  profile: Profile | null
  onSelectLane: (id: string | null) => void
  selectedLaneId: string | null
  onTimeUpdate?: (t: number) => void
}) {
  const [opts, setOpts] = useState<RenderOptions>(DEFAULT_OPTS)
  const containerRef = useRef<HTMLDivElement>(null)
  const [, forceRerender] = useState(0)

  useEffect(() => {
    if (progress?.run_id) api.setRenderOptions(progress.run_id, opts).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts])

  useEffect(() => {
    const ro = new ResizeObserver(() => forceRerender((n) => n + 1))
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  const status = progress?.status
  const live = status === 'running' || status === 'paused' || status === 'queued'
  const finished = status === 'completed' || status === 'stopped'

  function toggle(key: keyof RenderOptions) {
    setOpts((o) => ({ ...o, [key]: !o[key] }))
  }

  return (
    <div className="flex-1 flex flex-col bg-black overflow-hidden">
      <div ref={containerRef} className="flex-1 relative flex items-center justify-center overflow-hidden">
        {!progress && (
          <div className="text-[var(--text-faint)] text-sm">Видео появится после запуска анализа</div>
        )}
        {progress && !progress.model_ready && live && (
          <div className="text-[var(--text-muted)] text-sm flex flex-col items-center gap-2">
            <div className="w-5 h-5 border-2 border-[var(--accent-teal)] border-t-transparent rounded-full animate-spin" />
            Загрузка модели распознавания…
          </div>
        )}
        {progress && progress.model_ready && live && (
          <img
            src={api.liveStreamUrl(progress.run_id)}
            alt="Обработанное видео (прямой просмотр)"
            className="max-w-full max-h-full object-contain"
          />
        )}
        {progress && finished && (
          <video
            src={api.exportFileUrl(progress.run_id, 'annotated_video.mp4')}
            controls
            className="max-w-full max-h-full object-contain"
            onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
          />
        )}

        {profile && (live || finished) && (
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none"
            viewBox={`0 0 ${profile.source_video.width} ${profile.source_video.height}`}
            preserveAspectRatio="xMidYMid meet"
          >
            {opts.show_lanes && profile.lanes.map((lane) => (
              <polygon
                key={lane.id}
                points={lane.observation_polygon.points
                  .map((p) => `${p.x * profile.source_video.width},${p.y * profile.source_video.height}`)
                  .join(' ')}
                fill={lane.id === selectedLaneId ? lane.color + '22' : 'transparent'}
                stroke="transparent"
                strokeWidth={3}
                className="pointer-events-auto cursor-pointer"
                onClick={() => onSelectLane(lane.id === selectedLaneId ? null : lane.id)}
              />
            ))}
          </svg>
        )}
      </div>

      <div className="flex items-center gap-1.5 px-3 py-2 border-t border-[var(--border)] bg-[var(--surface)] flex-wrap">
        <span className="text-xs text-[var(--text-faint)] mr-1">Слои:</span>
        {TOGGLE_LABELS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => toggle(key)}
            className={`px-2 py-1 rounded text-xs border transition-colors ${
              opts[key]
                ? 'bg-[var(--accent-teal-dim)]/40 border-[var(--accent-teal)] text-white'
                : 'border-[var(--border)] text-[var(--text-faint)]'
            }`}
          >
            {label}
          </button>
        ))}
        <span className="text-[10px] text-[var(--text-faint)] ml-2">
          переключение применяется к новым кадрам (не к уже записанным)
        </span>
      </div>
    </div>
  )
}
