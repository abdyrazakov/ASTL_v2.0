export function formatDuration(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) sec = 0
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export type LoadLevel = 'low' | 'medium' | 'high'

/** Простая эвристика нагрузки полосы для цветового индикатора: сочетает
 * длину очереди и среднее наблюдаемое ожидание. Не является рекомендацией
 * по переключению фаз — только визуальная сводка текущего состояния. */
export function laneLoadLevel(queued: number, avgWaitSec: number): LoadLevel {
  if (queued >= 4 || avgWaitSec >= 25) return 'high'
  if (queued >= 2 || avgWaitSec >= 10) return 'medium'
  return 'low'
}

export const LOAD_COLORS: Record<LoadLevel, string> = {
  low: 'var(--accent-teal)',
  medium: 'var(--accent-amber)',
  high: 'var(--accent-red)',
}

export const LOAD_LABELS: Record<LoadLevel, string> = {
  low: 'низкая',
  medium: 'средняя',
  high: 'высокая',
}
