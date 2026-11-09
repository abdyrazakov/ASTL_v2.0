import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { simApi } from '../api/simClient'
import type { ControllerMode, IntersectionProfile, SimLaneSnapshot, SimSnapshot } from '../api/simTypes'
import { TopNav } from '../components/layout/TopNav'
import { LaneCards } from '../components/analysis/LaneCards'
import { HistoryCharts } from '../components/analysis/HistoryCharts'
import { EventLog } from '../components/analysis/EventLog'
import { SimTopBar } from '../components/sim/SimTopBar'
import { IntersectionScene } from '../components/sim/IntersectionScene'
import { PhaseGreenChart } from '../components/sim/PhaseGreenChart'
import { DelayComparison } from '../components/sim/DelayComparison'
import { useSimulationPolling } from '../hooks/useSimulationPolling'
import { useAppState } from '../state/AppState'
import { CLASS_COLORS, CLASS_LABELS, MOVEMENT_GLYPH, SIGNAL_COLORS } from '../lib/intersectionGeometry'

export function SimulationPage() {
  const { intersectionId, setIntersectionId } = useAppState()
  const [profiles, setProfiles] = useState<IntersectionProfile[]>([])
  const [profile, setProfile] = useState<IntersectionProfile | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [selectedLaneId, setSelectedLaneId] = useState<string | null>(null)
  const [mode, setMode] = useState<ControllerMode>('adaptive')
  const [speed, setSpeed] = useState(5)
  const [seed, setSeed] = useState(42)
  const [duration, setDuration] = useState<number | null>(3600)
  const [starting, setStarting] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const { progress, snapshot, history, greens, scene } = useSimulationPolling(runId)
  const status = progress?.status
  const active = status === 'running' || status === 'paused' || status === 'queued'

  useEffect(() => {
    simApi.listProfiles().then(setProfiles).catch(() => {})
    simApi.getActive().then((a) => {
      if (a.active && a.run_id) {
        // восстановление после обновления страницы во время прогона
        setRunId(a.run_id)
        if (a.profile_id) setIntersectionId(a.profile_id)
        if (a.speed) setSpeed(a.speed)
        if (a.seed != null) setSeed(a.seed)
        if (a.controller_mode) setMode(a.controller_mode)
        if (a.duration_sec !== undefined) setDuration(a.duration_sec)
      }
    }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!intersectionId) { setProfile(null); return }
    simApi.getProfile(intersectionId).then((p) => {
      setProfile(p)
      if (!active) setSeed(p.traffic.seed)
    }).catch(() => setProfile(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intersectionId])

  // режим и скорость на сервере — источник истины, пока прогон активен
  useEffect(() => {
    if (progress && active) {
      setMode(progress.controller_mode)
      setSpeed(progress.speed)
    }
  }, [progress, active])

  async function handleStart() {
    if (!intersectionId) return
    setStarting(true)
    try {
      const p = await simApi.start({ profile_id: intersectionId, controller_mode: mode, seed, duration_sec: duration, speed })
      setSelectedLaneId(null)
      setRunId(p.run_id)
    } catch (e) {
      alert('Не удалось запустить симуляцию: ' + (e as Error).message)
    } finally {
      setStarting(false)
    }
  }

  async function handleMode(m: ControllerMode) {
    setMode(m)
    if (runId && active) await simApi.setMode(runId, m).catch((e) => alert((e as Error).message))
  }
  async function handleSpeed(s: number) {
    setSpeed(s)
    if (runId && active) await simApi.setSpeed(runId, s).catch(() => {})
  }

  function handleFullscreen() {
    if (!document.fullscreenElement) rootRef.current?.requestFullscreen()
    else document.exitFullscreen()
  }

  // Статус опрашивается раз в секунду, сцена — ~7 раз в секунду. На ×50 секунда
  // опроса = 50 с модели, поэтому время/фазу для строки состояния берём из более
  // свежего источника, чтобы они совпадали с тем, что нарисовано на схеме.
  const liveProgress = useMemo(() => {
    if (!progress || !scene || scene.t < progress.sim_time_sec) return progress
    return {
      ...progress,
      sim_time_sec: scene.t,
      signal_state: scene.signal_state,
      active_phase: scene.active_phase,
      next_phase: scene.next_phase,
      phase_remaining_sec: scene.phase_remaining_sec,
      phase_remaining_is_estimate: scene.phase_remaining_is_estimate,
    }
  }, [progress, scene])

  const lanes = snapshot?.lanes ?? []
  const selectedLane = lanes.find((l) => l.lane_id === selectedLaneId)
  // сцена и карточки должны соответствовать профилю прогона, а не текущему выбору
  const runMatchesProfile = !progress || progress.profile_id === profile?.profile_id
  const comparisonKey = `${runId}-${status}`
  const highlight = useMemo(() => (selectedLaneId ? new Set([selectedLaneId]) : undefined), [selectedLaneId])

  return (
    <div ref={rootRef} className="h-full flex flex-col bg-[var(--bg)]">
      <TopNav />
      <SimTopBar
        profiles={profiles}
        profileId={intersectionId}
        onProfileChange={(id) => { setIntersectionId(id); if (!active) setRunId(null) }}
        profile={profile}
        progress={liveProgress}
        mode={mode}
        onModeChange={handleMode}
        speed={speed}
        onSpeedChange={handleSpeed}
        seed={seed}
        onSeedChange={setSeed}
        duration={duration}
        onDurationChange={setDuration}
        onStart={handleStart}
        onPause={() => { if (runId) simApi.pause(runId) }}
        onResume={() => { if (runId) simApi.resume(runId) }}
        onStop={() => { if (runId) simApi.stop(runId) }}
        canStart={!!profile}
        starting={starting}
        onFullscreen={handleFullscreen}
      />

      {!profile && (
        <div className="flex-1 flex items-center justify-center text-[var(--text-faint)] text-sm">
          {profiles.length === 0
            ? <span>Профилей перекрёстка пока нет — создайте его на вкладке <Link className="text-[var(--accent-teal)] underline" to="/intersection">«Настройка перекрёстка»</Link>.</span>
            : 'Выберите перекрёсток вверху.'}
        </div>
      )}

      {profile && runMatchesProfile && (
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 flex flex-col overflow-hidden min-w-0">
            <div className="flex-1 min-h-0 relative">
              <div className="absolute inset-0 flex items-center justify-center p-2">
                <div className="h-full aspect-square max-w-full">
                  <IntersectionScene profile={profile} scene={scene} highlightLaneIds={highlight}
                    selectedLaneId={selectedLaneId}
                    onLaneClick={(id) => setSelectedLaneId(id === selectedLaneId ? null : id)} />
                </div>
              </div>
              <SceneLegend />
              {snapshot && <SafetyBadge snapshot={snapshot} />}
            </div>
            <div className="h-64 border-t border-[var(--border)] shrink-0 grid grid-cols-4">
              <div className="col-span-2 min-w-0">
                <HistoryCharts history={history} selectedLaneId={selectedLaneId}
                  selectedLaneColor={selectedLane?.color ?? 'var(--accent-teal)'} currentTime={null} />
              </div>
              <div className="py-3 pr-3 min-w-0">
                <PhaseGreenChart greens={greens} profile={profile} history={history} />
              </div>
              <div className="py-3 pr-3 min-w-0">
                {/* во время прогона — его сценарий; иначе — то, что выбрано в селекторах */}
                <DelayComparison profileId={profile.profile_id}
                  seed={active && progress ? progress.seed : seed}
                  durationSec={active && progress ? progress.duration_sec : duration}
                  refreshKey={comparisonKey} busy={active} />
              </div>
            </div>
          </div>

          <div className="w-80 shrink-0 border-l border-[var(--border)] bg-[var(--surface)] flex flex-col overflow-hidden">
            <TotalsPanel snapshot={snapshot} />
            <div className="flex-1 overflow-y-auto">
              <LaneCards<SimLaneSnapshot>
                lanes={lanes}
                selectedLaneId={selectedLaneId}
                onSelect={setSelectedLaneId}
                emptyText="Данные появятся после запуска симуляции."
                extra={(lane) => <SimLaneExtra lane={lane} />}
              />
            </div>
            <div className="h-44 border-t border-[var(--border)] shrink-0">
              <EventLog history={history} />
            </div>
          </div>
        </div>
      )}
      {profile && !runMatchesProfile && (
        <div className="flex-1 flex items-center justify-center text-[var(--text-faint)] text-sm">
          Показанный прогон относится к другому перекрёстку — запустите новый прогон.
        </div>
      )}
    </div>
  )
}

function SimLaneExtra({ lane }: { lane: SimLaneSnapshot }) {
  return (
    <div className="mt-2 pt-2 border-t border-[var(--border)]">
      <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
        {Object.entries(lane.signals).map(([m, c]) => (
          <span key={m} className="flex items-center gap-1 text-[10px] text-[var(--text-muted)]">
            <span className="w-2 h-2 rounded-full" style={{ background: SIGNAL_COLORS[c as string] }} />
            {MOVEMENT_GLYPH[m as keyof typeof MOVEMENT_GLYPH]}
          </span>
        ))}
        <span className="text-[10px] text-[var(--text-faint)] ml-auto">поток {lane.arrival_rate_vph_now.toFixed(0)} маш/ч</span>
      </div>
      <div className="grid grid-cols-3 gap-x-2 text-xs">
        <Metric label="задержка сред." value={`${lane.avg_delay_sec.toFixed(1)}с`} />
        <Metric label="остановок/маш." value={lane.stops_per_vehicle.toFixed(2)} />
        <Metric label="пропускная" value={`${lane.throughput_per_hour.toFixed(0)}/ч`} />
      </div>
      <p className="text-[10px] text-[var(--text-faint)] mt-1">
        по выбывшим (проехавшим стоп-линию): n={lane.departed_count}
      </p>
      {lane.queue_spillback && (
        <p className="text-[10px] text-[var(--accent-red)] mt-1">
          очередь вышла за начало участка: ещё {lane.entry_backlog} маш. ждут въезда (учтены в ожидании)
        </p>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[var(--text-faint)] leading-tight text-[10px]">{label}</div>
      <div className="font-mono-tab text-[var(--text)] text-[13px]">{value}</div>
    </div>
  )
}

function TotalsPanel({ snapshot }: { snapshot: SimSnapshot | null }) {
  const t = snapshot?.totals
  return (
    <div className="p-3 border-b border-[var(--border)] shrink-0">
      <div className="text-xs text-[var(--text-muted)] mb-1.5">Итог по перекрёстку</div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
        <Metric label="задержка сред." value={t ? `${t.avg_delay_sec.toFixed(1)} с` : '—'} />
        <Metric label="остановок на машину" value={t ? t.stops_per_vehicle.toFixed(2) : '—'} />
        <Metric label="пропускная (за прогон)" value={t ? `${t.throughput_per_hour.toFixed(0)} маш/ч` : '—'} />
        <Metric label="выбыло / в системе" value={t ? `${t.departed} / ${t.vehicles_in_system}` : '—'} />
      </div>
      <p className="text-[10px] text-[var(--text-faint)] mt-1.5 leading-snug">
        Задержка, остановки и пропускная — агрегаты по <b>выбывшим</b> машинам (проехавшим стоп-линию).
        «Ожидание» в карточках — по машинам, стоящим в очереди сейчас (полное время с момента остановки).
      </p>
    </div>
  )
}

function SceneLegend() {
  return (
    <div className="absolute left-3 bottom-3 bg-[var(--surface)]/90 border border-[var(--border)] rounded-md px-2.5 py-2 text-[10px] text-[var(--text-muted)] flex flex-col gap-1">
      {Object.entries(CLASS_LABELS).map(([k, label]) => (
        <span key={k} className="flex items-center gap-1.5">
          <span className="w-3 h-1.5 rounded-sm" style={{ background: CLASS_COLORS[k] }} /> {label}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <span className="w-3 h-1.5 rounded-sm border border-[#ef4444]" /> стоит в очереди
      </span>
      <span className="text-[var(--text-faint)]">стоп-линия = сигнал группы</span>
    </div>
  )
}

function SafetyBadge({ snapshot }: { snapshot: SimSnapshot }) {
  const s = snapshot.safety
  const ok = s.blocked_violations === 0 && s.faults === 0 && s.conflict_invariant_ok_now
  return (
    <div className="absolute right-3 top-3 text-[10px] px-2 py-1 rounded-md border"
      title="Предохранитель автомата проверяет матрицу конфликтов при каждой смене сигналов"
      style={{ borderColor: ok ? 'var(--accent-teal)' : 'var(--accent-red)', color: ok ? 'var(--accent-teal)' : 'var(--accent-red)' }}>
      {ok ? '✓ конфликтов сигналов нет' : `⚠ заблокировано: ${s.blocked_violations}, FAULT: ${s.faults}`}
    </div>
  )
}
