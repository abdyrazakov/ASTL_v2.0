import clsx from 'clsx'
import type { IntersectionProfile, Timings } from '../../api/simTypes'
import { CLASS_LABELS } from '../../lib/intersectionGeometry'
import { NumField, Row, Section, SmallButton, Toggle, inputCls } from './ui'
import type { Edit } from './StructureTabs'

const TIMING_FIELDS: { key: keyof Timings; label: string; hint: string; unit: string; step?: number }[] = [
  { key: 'min_green_sec', label: 'Минимальный зелёный', unit: 'с', hint: 'Раньше этого фаза не может закончиться ни в каком режиме.' },
  { key: 'max_green_sec', label: 'Максимальный зелёный', unit: 'с', hint: 'Жёсткий предел зелёного в обоих режимах.' },
  { key: 'yellow_sec', label: 'Жёлтый', unit: 'с', step: 0.5, hint: 'Фиксированный, ≥ 3 с.' },
  { key: 'all_red_clearance_sec', label: 'All-red (освобождение)', unit: 'с', step: 0.5, hint: 'Всё красное между жёлтым одной фазы и зелёным следующей.' },
  { key: 'startup_all_red_sec', label: 'All-red при запуске', unit: 'с', step: 0.5, hint: 'При старте и после FAULT все сигналы красные не меньше этого.' },
  { key: 'gap_out_sec', label: 'Gap-out (адаптивный)', unit: 'с', step: 0.5, hint: 'Зелёный продлевается, пока машины фазы проезжают детектор/стоп-линию чаще, чем раз в это время.' },
  { key: 'max_red_wait_sec', label: 'Защита от голодания', unit: 'с', hint: 'Машина, ждущая дольше, получает зелёный первой. Должно быть ≥ min_green + 2·(жёлтый + all-red).' },
  { key: 'detector_distance_m', label: 'Детектор до стоп-линии', unit: 'м', hint: 'Виртуальный детектор адаптивного режима.' },
]

export function TimingsTab({ profile, edit }: { profile: IntersectionProfile; edit: Edit }) {
  const t = profile.timings
  return (
    <div>
      <Section title="Тайминги (общие для всех фаз; фаза может переопределить min/max)">
        {TIMING_FIELDS.map((f) => (
          <Row key={f.key} label={f.label} hint={f.hint}>
            <NumField value={t[f.key]} step={f.step ?? 1} min={0}
              onChange={(v) => edit((p) => { if (v != null) p.timings[f.key] = v })} />
            <span className="text-xs text-[var(--text-faint)]">{f.unit}</span>
          </Row>
        ))}
        <p className="text-[11px] text-[var(--text-faint)]">Все длительности округляются до шага модели 0.1 с.</p>
      </Section>
      <Section title="Адаптивный контроллер">
        <Row label="Вес ожидания w" hint="Спрос фазы D = Σ по ждущим машинам (1 + w·ожидание, с). 0.1 — машина, ждущая 10 с, весит как две.">
          <NumField value={profile.adaptive.wait_weight_per_sec} step={0.05} min={0}
            onChange={(v) => edit((p) => { if (v != null) p.adaptive.wait_weight_per_sec = v })} />
          <span className="text-xs text-[var(--text-faint)]">1/с</span>
        </Row>
        <Row label="Очистка очереди: порог" hint="После min_green зелёный уступает, когда у фазы не осталось машин в очереди, а спрос другой фазы ≥ порога (≈ число ждущих машин). Пусто — правило выключено.">
          <NumField value={profile.adaptive.queue_clear_min_demand} step={0.5} min={0} allowEmpty placeholder="выкл."
            onChange={(v) => edit((p) => { p.adaptive.queue_clear_min_demand = v != null && v > 0 ? v : null })} />
        </Row>
        <p className="text-[11px] text-[var(--text-faint)] leading-relaxed">
          Это простое правило по наибольшему спросу с защитой от голодания — эвристика, а не
          оптимизация (не max-pressure и не RL). Подробности в STAGE2_README.md.
        </p>
      </Section>
    </div>
  )
}

export function TrafficTab({ profile, edit, selectedLaneId }: {
  profile: IntersectionProfile
  edit: Edit
  selectedLaneId: string | null
}) {
  const tr = profile.traffic
  const totalShare = Object.values(tr.composition).reduce((s, x) => s + x, 0) || 1
  const laneName = (id: string) => profile.lanes.find((l) => l.id === id)?.name ?? id

  return (
    <div>
      <Section title="Генератор трафика">
        <Row label="Seed" hint="Одинаковый seed и профиль — одинаковый прогон. Нужен для честного сравнения режимов.">
          <NumField value={tr.seed} step={1} onChange={(v) => edit((p) => { p.traffic.seed = Math.round(v ?? 0) })} />
        </Row>
        <Row label="Мин. дистанция между машинами" hint="Зазор между стоящими машинами.">
          <NumField value={tr.min_gap_m} step={0.5} min={0.5}
            onChange={(v) => edit((p) => { if (v != null) p.traffic.min_gap_m = v })} />
          <span className="text-xs text-[var(--text-faint)]">м</span>
        </Row>
      </Section>

      <Section title="Интенсивность по полосам (пуассоновский поток)">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {profile.lanes.map((lane) => (
            <div key={lane.id} className={clsx('flex items-center gap-2 text-sm', selectedLaneId === lane.id && 'font-semibold')}>
              <span className="w-28 truncate" style={{ color: lane.color }}>{lane.name}</span>
              <NumField value={lane.arrival_rate_vph} min={0} step={10} className="w-20"
                onChange={(v) => edit((p) => { p.lanes.find((l) => l.id === lane.id)!.arrival_rate_vph = v ?? 0 })} />
              <span className="text-[11px] text-[var(--text-faint)]">маш/ч</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Состав транспорта (доли нормируются)">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {Object.keys(CLASS_LABELS).map((cls) => (
            <div key={cls} className="flex items-center gap-2 text-sm">
              <span className="w-24">{CLASS_LABELS[cls]}</span>
              <NumField value={tr.composition[cls] ?? 0} step={0.01} min={0} className="w-20"
                onChange={(v) => edit((p) => { p.traffic.composition[cls] = Math.max(0, v ?? 0) })} />
              <span className="text-[11px] text-[var(--text-faint)] font-mono-tab">
                {(((tr.composition[cls] ?? 0) / totalShare) * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Сценарий (множители интенсивности по времени)"
        right={
          <div className="flex gap-1">
            <SmallButton disabled={!selectedLaneId}
              title={selectedLaneId ? '' : 'Выберите полосу на схеме'}
              onClick={() => edit((p) => {
                p.traffic.scenario.push({ start_sec: 600, end_sec: 1500, lane_ids: [selectedLaneId!], multiplier: 3, label: `всплеск: ${laneName(selectedLaneId!)} ×3` })
              })}>+ всплеск на выбранной полосе</SmallButton>
            <SmallButton onClick={() => edit((p) => {
              p.traffic.scenario.push({ start_sec: 0, end_sec: 600, lane_ids: [], multiplier: 1.5, label: '' })
            })}>+ сегмент</SmallButton>
          </div>
        }>
        <Row label="Название сценария" hint="">
          <input value={tr.scenario_name} className={clsx(inputCls, 'w-64')}
            onChange={(e) => edit((p) => { p.traffic.scenario_name = e.target.value })} />
        </Row>
        {tr.scenario.length === 0 && (
          <p className="text-xs text-[var(--text-faint)]">Без сценария — постоянная интенсивность.</p>
        )}
        <div className="flex flex-col gap-2">
          {tr.scenario.map((seg, i) => (
            <div key={i} className="rounded-md border border-[var(--border)] p-2 text-xs flex flex-col gap-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[var(--text-faint)]">с</span>
                <NumField value={seg.start_sec / 60} step={1} min={0} className="w-16"
                  onChange={(v) => edit((p) => { p.traffic.scenario[i].start_sec = Math.max(0, (v ?? 0) * 60) })} />
                <span className="text-[var(--text-faint)]">по</span>
                <NumField value={seg.end_sec / 60} step={1} min={0} className="w-16"
                  onChange={(v) => edit((p) => { p.traffic.scenario[i].end_sec = Math.max(0, (v ?? 0) * 60) })} />
                <span className="text-[var(--text-faint)]">мин · ×</span>
                <NumField value={seg.multiplier} step={0.5} min={0} className="w-16"
                  onChange={(v) => edit((p) => { p.traffic.scenario[i].multiplier = Math.max(0, v ?? 1) })} />
                <input value={seg.label} placeholder="подпись" className={clsx(inputCls, 'flex-1 text-xs')}
                  onChange={(e) => edit((p) => { p.traffic.scenario[i].label = e.target.value })} />
                <SmallButton danger onClick={() => edit((p) => { p.traffic.scenario.splice(i, 1) })}>✕</SmallButton>
              </div>
              <div className="flex flex-wrap gap-1 items-center">
                <span className="text-[var(--text-faint)] mr-1">полосы:</span>
                <Toggle on={seg.lane_ids.length === 0}
                  onClick={() => edit((p) => { p.traffic.scenario[i].lane_ids = [] })}>все</Toggle>
                {profile.lanes.map((lane) => {
                  const on = seg.lane_ids.includes(lane.id)
                  return (
                    <Toggle key={lane.id} on={on} onClick={() => edit((p) => {
                      const s = p.traffic.scenario[i]
                      s.lane_ids = on ? s.lane_ids.filter((x) => x !== lane.id) : [...s.lane_ids, lane.id]
                    })}>{lane.name}</Toggle>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}
