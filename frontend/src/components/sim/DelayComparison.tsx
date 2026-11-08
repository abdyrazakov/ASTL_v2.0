import { useCallback, useEffect, useState } from 'react'
import { simApi } from '../../api/simClient'
import type { Comparison, SimTotals } from '../../api/simTypes'
import { formatDuration } from '../../lib/format'

/**
 * Сравнение «фиксированный vs адаптивный» — только из реально выполненных
 * прогонов на одном сценарии (тот же профиль, seed и длительность, без
 * переключения режима). Если пары нет, так и пишем — вторую цифру не придумываем.
 */
export function DelayComparison({ profileId, seed, durationSec, refreshKey, busy }: {
  profileId: string
  seed: number
  durationSec: number | null
  refreshKey: string
  busy: boolean
}) {
  const [cmp, setCmp] = useState<Comparison | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    simApi.comparison(profileId, seed, durationSec).then(setCmp).catch(() => setCmp(null))
  }, [profileId, seed, durationSec])

  useEffect(() => { load() }, [load, refreshKey])

  async function runBoth() {
    if (!durationSec) return
    setRunning(true)
    setError(null)
    try {
      setCmp(await simApi.compare(profileId, seed, durationSec))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-md p-3 flex flex-col h-full overflow-hidden">
      <div className="text-xs text-[var(--text-muted)] mb-1">
        Средняя задержка: фиксированный vs адаптивный
      </div>
      <p className="text-[10px] text-[var(--text-faint)] leading-snug mb-2">
        seed {seed} · {durationSec ? formatDuration(durationSec) : '∞'} модельного времени · по выбывшим машинам
      </p>
      {cmp?.available ? (
        <ComparisonBody fixed={cmp.fixed.totals} adaptive={cmp.adaptive.totals} />
      ) : (
        <div className="flex-1 flex flex-col gap-2">
          <p className="text-xs text-[var(--text-muted)] leading-relaxed">
            {durationSec
              ? 'Для сравнения запустите оба режима на одном сценарии (тот же перекрёсток, seed и длительность, без переключения режима во время прогона).'
              : 'Сравнение доступно только для прогонов с конечной длительностью.'}
          </p>
          {cmp && !cmp.available && cmp.have_modes.length > 0 && (
            <p className="text-[11px] text-[var(--text-faint)]">
              Уже есть: {cmp.have_modes.map((m) => (m === 'fixed' ? 'фиксированный' : 'адаптивный')).join(', ')}.
            </p>
          )}
        </div>
      )}
      <button type="button" onClick={runBoth} disabled={running || busy || !durationSec}
        title={busy ? 'Сначала остановите текущий прогон' : 'Оба режима на этом seed, как можно быстрее, с сохранением результатов в output/'}
        className="mt-2 shrink-0 px-2.5 py-1.5 rounded-md border border-[var(--accent-teal)] text-[var(--accent-teal)] text-xs disabled:opacity-40">
        {running ? 'Считаю оба режима…' : '⇄ Прогнать оба режима (быстро)'}
      </button>
      {error && <p className="text-[11px] text-[var(--accent-red)] mt-1">{error}</p>}
    </div>
  )
}

function ComparisonBody({ fixed, adaptive }: { fixed: SimTotals; adaptive: SimTotals }) {
  const rows: { label: string; f: number; a: number; unit: string; better: 'lower' | 'higher'; digits: number }[] = [
    { label: 'задержка сред.', f: fixed.avg_delay_sec, a: adaptive.avg_delay_sec, unit: 'с', better: 'lower', digits: 1 },
    { label: 'остановок/машину', f: fixed.stops_per_vehicle, a: adaptive.stops_per_vehicle, unit: '', better: 'lower', digits: 2 },
    { label: 'пропускная', f: fixed.throughput_per_hour, a: adaptive.throughput_per_hour, unit: 'маш/ч', better: 'higher', digits: 0 },
  ]
  const maxDelay = Math.max(fixed.avg_delay_sec, adaptive.avg_delay_sec, 0.001)
  return (
    <div className="flex-1 flex flex-col gap-2 overflow-y-auto">
      {(['fixed', 'adaptive'] as const).map((m) => {
        const v = m === 'fixed' ? fixed.avg_delay_sec : adaptive.avg_delay_sec
        return (
          <div key={m} className="flex items-center gap-2 text-xs">
            <span className="w-24 text-[var(--text-muted)]">{m === 'fixed' ? 'фиксированный' : 'адаптивный'}</span>
            <div className="flex-1 h-3 rounded bg-[var(--surface-sunken)] overflow-hidden">
              <div className="h-full rounded" style={{
                width: `${(v / maxDelay) * 100}%`,
                background: m === 'fixed' ? 'var(--text-faint)' : 'var(--accent-teal)',
              }} />
            </div>
            <span className="w-14 text-right font-mono-tab">{v.toFixed(1)} с</span>
          </div>
        )
      })}
      <table className="text-[11px] w-full mt-1">
        <thead>
          <tr className="text-[var(--text-faint)]">
            <th className="text-left font-normal">показатель</th>
            <th className="text-right font-normal">фикс.</th>
            <th className="text-right font-normal">адапт.</th>
            <th className="text-right font-normal">Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const delta = r.f !== 0 ? ((r.a - r.f) / r.f) * 100 : 0
            const good = r.better === 'lower' ? delta <= 0 : delta >= 0
            return (
              <tr key={r.label}>
                <td className="text-[var(--text-muted)]">{r.label}</td>
                <td className="text-right font-mono-tab">{r.f.toFixed(r.digits)}</td>
                <td className="text-right font-mono-tab">{r.a.toFixed(r.digits)}</td>
                <td className="text-right font-mono-tab" style={{ color: good ? 'var(--accent-teal)' : 'var(--accent-red)' }}>
                  {delta > 0 ? '+' : ''}{delta.toFixed(0)}%
                </td>
              </tr>
            )
          })}
          <tr>
            <td className="text-[var(--text-muted)]">выбыло машин</td>
            <td className="text-right font-mono-tab">{fixed.departed}</td>
            <td className="text-right font-mono-tab">{adaptive.departed}</td>
            <td />
          </tr>
        </tbody>
      </table>
    </div>
  )
}
