import clsx from 'clsx'
import type { Heading, IntersectionProfile, Movement } from '../../api/simTypes'
import {
  ALL_MOVEMENTS, addApproach, addLane, conflicts, cycleTransitions, normalize, removeApproach,
  removeLane, toggleConflict, uniqueId,
} from '../../lib/intersectionEdit'
import { HEADING_LABEL, MOVEMENT_GLYPH, MOVEMENT_LABEL, PALETTE } from '../../lib/intersectionGeometry'
import { NumField, Section, SmallButton, Toggle, inputCls } from './ui'

export type Edit = (fn: (p: IntersectionProfile) => void) => void

const HEADINGS: Heading[] = ['N', 'E', 'S', 'W']

// ------------------------------------------------------------------ полосы

export function LanesTab({ profile, edit, selectedLaneId, onSelectLane }: {
  profile: IntersectionProfile
  edit: Edit
  selectedLaneId: string | null
  onSelectLane: (id: string | null) => void
}) {
  return (
    <div>
      <Section title="Подходы (сторона, с которой едут машины)">
        <div className="flex gap-1.5">
          {HEADINGS.map((h) => {
            const a = profile.approaches.find((x) => x.heading === h)
            return (
              <Toggle key={h} on={!!a} title={a ? 'Убрать подход вместе с его полосами' : 'Добавить подход'}
                onClick={() => edit((p) => (a ? removeApproach(p, a.id) : addApproach(p, h)))}>
                {HEADING_LABEL[h]}
              </Toggle>
            )
          })}
        </div>
      </Section>

      {profile.approaches.map((a) => {
        const lanes = profile.lanes.filter((l) => l.approach_id === a.id).sort((x, y) => x.index - y.index)
        return (
          <Section key={a.id} title={`${a.name} — полосы (от осевой к обочине)`}
            right={<SmallButton onClick={() => edit((p) => addLane(p, a.id))} disabled={lanes.length >= 6}>+ полоса</SmallButton>}>
            <div className="flex flex-col gap-1.5">
              {lanes.map((lane) => (
                <div key={lane.id}
                  onClick={() => onSelectLane(lane.id)}
                  className={clsx('rounded-md border p-2 flex flex-wrap items-center gap-2',
                    selectedLaneId === lane.id ? 'border-[var(--accent-teal)]' : 'border-[var(--border)]')}
                  style={{ borderLeftWidth: 4, borderLeftColor: lane.color }}>
                  <input value={lane.name} className={clsx(inputCls, 'w-28')} aria-label="Название полосы"
                    onChange={(e) => edit((p) => { p.lanes.find((l) => l.id === lane.id)!.name = e.target.value })} />
                  <div className="flex gap-1" role="group" aria-label="Разрешённые манёвры">
                    {ALL_MOVEMENTS.map((m) => (
                      <Toggle key={m} on={lane.movements.includes(m)} title={MOVEMENT_LABEL[m]}
                        onClick={() => edit((p) => {
                          const l = p.lanes.find((x) => x.id === lane.id)!
                          const has = l.movements.includes(m)
                          if (has && l.movements.length === 1) return // хотя бы один манёвр
                          l.movements = has ? l.movements.filter((x) => x !== m)
                            : ALL_MOVEMENTS.filter((x) => x === m || l.movements.includes(x))
                          normalize(p)
                        })}>
                        {MOVEMENT_GLYPH[m]}
                      </Toggle>
                    ))}
                  </div>
                  <span className="text-[11px] text-[var(--text-faint)]">длина</span>
                  <NumField value={lane.length_m} min={30} max={1000} step={10} className="w-16"
                    onChange={(v) => edit((p) => { p.lanes.find((l) => l.id === lane.id)!.length_m = v ?? 150 })} />
                  <span className="text-[11px] text-[var(--text-faint)]">м · поток</span>
                  <NumField value={lane.arrival_rate_vph} min={0} max={3000} step={10} className="w-16"
                    onChange={(v) => edit((p) => { p.lanes.find((l) => l.id === lane.id)!.arrival_rate_vph = v ?? 0 })} />
                  <span className="text-[11px] text-[var(--text-faint)]">маш/ч</span>
                  <input type="color" value={lane.color} aria-label="Цвет полосы"
                    className="w-7 h-6 bg-transparent border-0 p-0 cursor-pointer"
                    onChange={(e) => edit((p) => { p.lanes.find((l) => l.id === lane.id)!.color = e.target.value })} />
                  <div className="flex-1" />
                  <SmallButton danger onClick={() => edit((p) => removeLane(p, lane.id))}>удалить</SmallButton>
                </div>
              ))}
              {lanes.length === 0 && <p className="text-xs text-[var(--text-faint)]">Нет полос.</p>}
            </div>
          </Section>
        )
      })}
      <p className="text-[11px] text-[var(--text-faint)] leading-relaxed">
        Геометрия схемы условная и служит только для наглядности; аналитика считается по длине полосы
        в метрах и моментам событий модели.
      </p>
    </div>
  )
}

// ------------------------------------------------------------------ группы

export function GroupsTab({ profile, edit, selectedGroupId, onSelectGroup }: {
  profile: IntersectionProfile
  edit: Edit
  selectedGroupId: string | null
  onSelectGroup: (id: string | null) => void
}) {
  const owner = new Map<string, string>()
  for (const g of profile.signal_groups) for (const lm of g.movements) owner.set(`${lm.lane_id}|${lm.movement}`, g.id)
  const groupName = (id: string) => profile.signal_groups.find((g) => g.id === id)?.name ?? id

  return (
    <div>
      <Section title="Сигнальные группы"
        right={<SmallButton onClick={() => edit((p) => {
          const id = uniqueId('g', p.signal_groups.map((g) => g.id))
          p.signal_groups.push({ id, name: `Группа ${p.signal_groups.length + 1}`, movements: [] })
          onSelectGroup(id)
        })}>+ группа</SmallButton>}>
        <p className="text-[11px] text-[var(--text-faint)] mb-2 leading-relaxed">
          Группа — один сигнал светофора для набора совместимых манёвров. Каждый манёвр полосы с
          трафиком должен принадлежать ровно одной группе.
        </p>
        <div className="flex flex-col gap-2">
          {profile.signal_groups.map((g, gi) => {
            const sel = selectedGroupId === g.id
            return (
              <div key={g.id} onClick={() => onSelectGroup(g.id)}
                className={clsx('rounded-md border p-2', sel ? 'border-[var(--accent-teal)]' : 'border-[var(--border)]')}
                style={{ borderLeftWidth: 4, borderLeftColor: PALETTE[gi % PALETTE.length] }}>
                <div className="flex items-center gap-2 mb-1.5">
                  <input value={g.name} className={clsx(inputCls, 'flex-1')} aria-label="Название группы"
                    onChange={(e) => edit((p) => { p.signal_groups.find((x) => x.id === g.id)!.name = e.target.value })} />
                  <span className="text-[10px] font-mono-tab text-[var(--text-faint)]">{g.id}</span>
                  <SmallButton danger onClick={() => edit((p) => {
                    p.signal_groups = p.signal_groups.filter((x) => x.id !== g.id)
                    normalize(p)
                  })}>удалить</SmallButton>
                </div>
                {sel ? (
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                    {profile.lanes.map((lane) => (
                      <div key={lane.id} className="flex items-center gap-1.5 text-xs">
                        <span className="w-20 truncate" style={{ color: lane.color }}>{lane.name}</span>
                        {lane.movements.map((m: Movement) => {
                          const key = `${lane.id}|${m}`
                          const own = owner.get(key)
                          const mine = own === g.id
                          const taken = !!own && !mine
                          return (
                            <Toggle key={m} on={mine} disabled={taken}
                              title={taken ? `уже в группе «${groupName(own!)}»` : MOVEMENT_LABEL[m]}
                              onClick={() => edit((p) => {
                                const grp = p.signal_groups.find((x) => x.id === g.id)!
                                grp.movements = mine
                                  ? grp.movements.filter((lm) => !(lm.lane_id === lane.id && lm.movement === m))
                                  : [...grp.movements, { lane_id: lane.id, movement: m }]
                              })}>
                              {MOVEMENT_GLYPH[m]}
                            </Toggle>
                          )
                        })}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-[var(--text-muted)]">
                    {g.movements.length
                      ? g.movements.map((lm) => `${profile.lanes.find((l) => l.id === lm.lane_id)?.name ?? lm.lane_id} ${MOVEMENT_GLYPH[lm.movement]}`).join(', ')
                      : <span className="text-[var(--accent-amber)]">нет манёвров — выберите группу, чтобы привязать</span>}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </Section>
    </div>
  )
}

// ------------------------------------------------------------------ конфликты

export function ConflictsTab({ profile, edit }: { profile: IntersectionProfile; edit: Edit }) {
  const groups = profile.signal_groups
  return (
    <div>
      <Section title="Матрица конфликтов">
        <p className="text-[11px] text-[var(--text-faint)] mb-2 leading-relaxed">
          Отметьте пары групп, которые <b>не могут</b> одновременно показывать разрешающий сигнал
          (зелёный или жёлтый). Отметка ставится сразу в обе клетки — матрица всегда симметрична.
          Конфликты задаются вручную: система не выводит их из геометрии и не проверяет соответствие
          реальному перекрёстку — это ответственность того, кто настраивает профиль.
        </p>
        <div className="overflow-auto">
          <table className="text-xs border-collapse">
            <thead>
              <tr>
                <th />
                {groups.map((g, i) => (
                  <th key={g.id} className="px-1 pb-1 font-normal text-[var(--text-muted)] align-bottom">
                    <div className="[writing-mode:vertical-rl] rotate-180 whitespace-nowrap max-h-40 overflow-hidden"
                      style={{ color: PALETTE[i % PALETTE.length] }}>{g.name}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {groups.map((a, i) => (
                <tr key={a.id}>
                  <td className="pr-2 py-0.5 whitespace-nowrap text-right" style={{ color: PALETTE[i % PALETTE.length] }}>{a.name}</td>
                  {groups.map((b) => (
                    <td key={b.id} className="p-0.5 text-center">
                      {a.id === b.id ? (
                        <span className="text-[var(--text-faint)]">—</span>
                      ) : (
                        <input type="checkbox" aria-label={`${a.name} конфликтует с ${b.name}`}
                          checked={conflicts(profile, a.id, b.id)}
                          onChange={(e) => edit((p) => toggleConflict(p, a.id, b.id, e.target.checked))}
                          className="w-4 h-4 accent-[var(--accent-red)] cursor-pointer" />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  )
}

// ------------------------------------------------------------------ фазы

export function PhasesTab({ profile, edit, selectedPhaseId, onSelectPhase }: {
  profile: IntersectionProfile
  edit: Edit
  selectedPhaseId: string | null
  onSelectPhase: (id: string | null) => void
}) {
  const ordered = profile.phase_order
    .map((id) => profile.phases.find((p) => p.id === id))
    .filter((p): p is NonNullable<typeof p> => !!p)
  const t = profile.timings

  return (
    <div>
      <Section title="Фазы в циклическом порядке"
        right={<SmallButton onClick={() => edit((p) => {
          const id = uniqueId('p', p.phases.map((x) => x.id))
          p.phases.push({ id, name: `Фаза ${p.phases.length + 1}`, signal_groups: [], fixed_green_sec: 20, min_green_sec: null, max_green_sec: null })
          p.phase_order.push(id)
          if (p.transitions) p.transitions = cycleTransitions(p)
          onSelectPhase(id)
        })}>+ фаза</SmallButton>}>
        <p className="text-[11px] text-[var(--text-faint)] mb-2 leading-relaxed">
          Фаза — набор совместимых групп, горящих зелёным одновременно. Группы, конфликтующие с уже
          выбранными, недоступны. Порядок задаёт цикл фиксированного режима.
        </p>
        <div className="flex flex-col gap-2">
          {ordered.map((ph, idx) => {
            const sel = selectedPhaseId === ph.id
            return (
              <div key={ph.id} onClick={() => onSelectPhase(ph.id)}
                className={clsx('rounded-md border p-2', sel ? 'border-[var(--accent-teal)]' : 'border-[var(--border)]')}>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs font-mono-tab text-[var(--text-faint)] w-4">{idx + 1}</span>
                  <input value={ph.name} className={clsx(inputCls, 'flex-1')} aria-label="Название фазы"
                    onChange={(e) => edit((p) => { p.phases.find((x) => x.id === ph.id)!.name = e.target.value })} />
                  <SmallButton disabled={idx === 0} title="Раньше в цикле" onClick={() => edit((p) => {
                    const o = p.phase_order; const i = o.indexOf(ph.id);[o[i - 1], o[i]] = [o[i], o[i - 1]]
                  })}>↑</SmallButton>
                  <SmallButton disabled={idx === ordered.length - 1} title="Позже в цикле" onClick={() => edit((p) => {
                    const o = p.phase_order; const i = o.indexOf(ph.id);[o[i + 1], o[i]] = [o[i], o[i + 1]]
                  })}>↓</SmallButton>
                  <SmallButton danger onClick={() => edit((p) => {
                    p.phases = p.phases.filter((x) => x.id !== ph.id)
                    normalize(p)
                  })}>удалить</SmallButton>
                </div>
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {profile.signal_groups.map((g, gi) => {
                    const on = ph.signal_groups.includes(g.id)
                    const clash = !on && ph.signal_groups.find((x) => conflicts(profile, x, g.id))
                    return (
                      <Toggle key={g.id} on={on} disabled={!!clash}
                        title={clash ? `конфликтует с «${profile.signal_groups.find((x) => x.id === clash)?.name}»` : undefined}
                        onClick={() => edit((p) => {
                          const x = p.phases.find((y) => y.id === ph.id)!
                          x.signal_groups = on ? x.signal_groups.filter((y) => y !== g.id) : [...x.signal_groups, g.id]
                        })}>
                        <span className="inline-block w-1.5 h-1.5 rounded-full mr-1 align-middle"
                          style={{ background: PALETTE[gi % PALETTE.length] }} />
                        {g.name}
                      </Toggle>
                    )
                  })}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--text-faint)]">
                  <span>зелёный фикс. цикла</span>
                  <NumField value={ph.fixed_green_sec} min={1} step={1} className="w-16"
                    onChange={(v) => edit((p) => { p.phases.find((x) => x.id === ph.id)!.fixed_green_sec = v ?? 20 })} />
                  <span>с · min</span>
                  <NumField value={ph.min_green_sec} allowEmpty placeholder={String(t.min_green_sec)} className="w-14"
                    onChange={(v) => edit((p) => { p.phases.find((x) => x.id === ph.id)!.min_green_sec = v })} />
                  <span>max</span>
                  <NumField value={ph.max_green_sec} allowEmpty placeholder={String(t.max_green_sec)} className="w-14"
                    onChange={(v) => edit((p) => { p.phases.find((x) => x.id === ph.id)!.max_green_sec = v })} />
                  <span>с (пусто — общие тайминги)</span>
                </div>
              </div>
            )
          })}
        </div>
      </Section>

      <Section title="Допустимые переходы между фазами">
        <label className="flex items-center gap-2 text-sm mb-2">
          <input type="checkbox" checked={profile.transitions === null}
            onChange={(e) => edit((p) => { p.transitions = e.target.checked ? null : cycleTransitions(p) })}
            className="accent-[var(--accent-teal)]" />
          из любой фазы в любую (рекомендуется для адаптивного режима)
        </label>
        {profile.transitions !== null && (
          <>
            <p className="text-[11px] text-[var(--text-faint)] mb-1.5">
              Строка — из какой фазы, столбец — в какую. Переходы циклического порядка обязательны.
            </p>
            <table className="text-xs">
              <thead>
                <tr>
                  <th />
                  {ordered.map((b) => <th key={b.id} className="px-1.5 font-normal text-[var(--text-muted)]">{b.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {ordered.map((a) => (
                  <tr key={a.id}>
                    <td className="pr-2 text-right text-[var(--text-muted)] whitespace-nowrap">{a.name} →</td>
                    {ordered.map((b) => (
                      <td key={b.id} className="text-center">
                        {a.id === b.id ? <span className="text-[var(--text-faint)]">—</span> : (
                          <input type="checkbox" className="accent-[var(--accent-teal)]"
                            checked={(profile.transitions?.[a.id] ?? []).includes(b.id)}
                            onChange={(e) => edit((p) => {
                              const tr = p.transitions ?? {}
                              const list = new Set(tr[a.id] ?? [])
                              if (e.target.checked) list.add(b.id)
                              else list.delete(b.id)
                              tr[a.id] = [...list]
                              p.transitions = tr
                            })} />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Section>
    </div>
  )
}
