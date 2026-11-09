import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import clsx from 'clsx'
import { ApiError } from '../api/client'
import { simApi } from '../api/simClient'
import type { IntersectionProfile, TemplateInfo, ValidationResult } from '../api/simTypes'
import { TopNav } from '../components/layout/TopNav'
import { IntersectionScene } from '../components/sim/IntersectionScene'
import { ConflictsTab, GroupsTab, LanesTab, PhasesTab } from '../components/intersection/StructureTabs'
import { TimingsTab, TrafficTab } from '../components/intersection/ParamTabs'
import { inputCls } from '../components/intersection/ui'
import { clone } from '../lib/intersectionEdit'
import { useAppState } from '../state/AppState'

type Tab = 'lanes' | 'groups' | 'conflicts' | 'phases' | 'timings' | 'traffic'
const TABS: { key: Tab; label: string }[] = [
  { key: 'lanes', label: 'Полосы' },
  { key: 'groups', label: 'Сигнальные группы' },
  { key: 'conflicts', label: 'Конфликты' },
  { key: 'phases', label: 'Фазы' },
  { key: 'timings', label: 'Тайминги' },
  { key: 'traffic', label: 'Трафик' },
]

function parseErrors(e: unknown): string[] {
  if (e instanceof ApiError) {
    try {
      const d = JSON.parse(e.message)
      if (Array.isArray(d.errors)) return d.errors
    } catch {
      /* не JSON */
    }
    return [e.message]
  }
  return [(e as Error).message]
}

export function IntersectionEditorPage() {
  const { intersectionId, setIntersectionId } = useAppState()
  const [templates, setTemplates] = useState<TemplateInfo[]>([])
  const [profiles, setProfiles] = useState<IntersectionProfile[]>([])
  const [profile, setProfile] = useState<IntersectionProfile | null>(null)
  const [saved, setSaved] = useState<string>('') // JSON последней сохранённой версии
  const [tab, setTab] = useState<Tab>('lanes')
  const [templateKey, setTemplateKey] = useState('four_way_protected_left')
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [saveErrors, setSaveErrors] = useState<string[]>([])
  const [savedOk, setSavedOk] = useState(false)
  const [selectedLaneId, setSelectedLaneId] = useState<string | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)
  const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null)

  const dirty = !!profile && JSON.stringify(profile) !== saved

  function refreshList() {
    return simApi.listProfiles().then(setProfiles).catch(() => {})
  }

  useEffect(() => {
    simApi.listTemplates().then(setTemplates).catch(() => {})
    refreshList()
  }, [])

  useEffect(() => {
    if (!intersectionId) { setProfile(null); setSaved(''); return }
    simApi.getProfile(intersectionId).then((p) => {
      setProfile(p)
      setSaved(JSON.stringify(p))
      setSaveErrors([])
    }).catch(() => { setProfile(null); setIntersectionId(null) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intersectionId])

  // живая валидация на сервере (те же правила, что при сохранении)
  useEffect(() => {
    if (!profile) { setValidation(null); return }
    const h = setTimeout(() => {
      simApi.validateProfile(profile).then(setValidation).catch(() => {})
    }, 350)
    return () => clearTimeout(h)
  }, [profile])

  const edit = (fn: (p: IntersectionProfile) => void) => {
    if (!profile) return
    const next = clone(profile)
    fn(next)
    setProfile(next)
    setSavedOk(false)
  }

  function confirmLeave(): boolean {
    return !dirty || confirm('Есть несохранённые изменения. Отбросить их?')
  }

  async function createFromTemplate() {
    if (!confirmLeave()) return
    const p = await simApi.createFromTemplate(templateKey)
    await refreshList()
    setIntersectionId(p.profile_id)
  }

  async function save() {
    if (!profile) return
    try {
      const p = await simApi.updateProfile(profile.profile_id, profile)
      setProfile(p)
      setSaved(JSON.stringify(p))
      setSaveErrors([])
      setSavedOk(true)
      refreshList()
    } catch (e) {
      setSaveErrors(parseErrors(e))
      setSavedOk(false)
    }
  }

  async function duplicate() {
    if (!profile || !confirmLeave()) return
    const p = await simApi.duplicateProfile(profile.profile_id)
    await refreshList()
    setIntersectionId(p.profile_id)
  }

  async function remove() {
    if (!profile || !confirm(`Удалить профиль «${profile.name}»?`)) return
    await simApi.deleteProfile(profile.profile_id)
    await refreshList()
    setIntersectionId(null)
  }

  const highlightGroups = useMemo(() => {
    if (!profile) return undefined
    if (tab === 'groups' && selectedGroupId) return new Set([selectedGroupId])
    if (tab === 'phases' && selectedPhaseId) {
      return new Set(profile.phases.find((p) => p.id === selectedPhaseId)?.signal_groups ?? [])
    }
    return undefined
  }, [profile, tab, selectedGroupId, selectedPhaseId])

  const highlightLanes = useMemo(() => {
    if (!profile || !highlightGroups) return undefined
    const set = new Set<string>()
    for (const g of profile.signal_groups) {
      if (highlightGroups.has(g.id)) g.movements.forEach((lm) => set.add(lm.lane_id))
    }
    return set
  }, [profile, highlightGroups])

  const errors = saveErrors.length ? saveErrors : validation?.errors ?? []
  const warnings = validation?.warnings ?? []

  return (
    <div className="h-full flex flex-col bg-[var(--bg)]">
      <TopNav />
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)] bg-[var(--surface)] flex-wrap text-sm">
        <label className="text-[var(--text-muted)]">Профиль:</label>
        <select value={intersectionId ?? ''} className={clsx(inputCls, 'max-w-[18rem]')}
          onChange={(e) => { if (confirmLeave()) setIntersectionId(e.target.value || null) }}>
          <option value="">— выберите —</option>
          {profiles.map((p) => <option key={p.profile_id} value={p.profile_id}>{p.name}</option>)}
        </select>
        <div className="w-px h-5 bg-[var(--border)] mx-1" />
        <label className="text-[var(--text-muted)]">Шаблон:</label>
        <select value={templateKey} onChange={(e) => setTemplateKey(e.target.value)} className={inputCls}>
          {templates.map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}
        </select>
        <button onClick={createFromTemplate}
          className="px-3 py-1.5 rounded-md bg-[var(--accent-teal-dim)] border border-[var(--accent-teal)] text-white">
          + Создать из шаблона
        </button>
        <div className="flex-1" />
        {profile && (
          <>
            <input value={profile.name} aria-label="Название профиля" className={clsx(inputCls, 'w-64')}
              onChange={(e) => edit((p) => { p.name = e.target.value })} />
            <button onClick={save} disabled={!dirty && !saveErrors.length}
              className="px-3 py-1.5 rounded-md border border-[var(--accent-teal)] text-[var(--accent-teal)] disabled:opacity-40">
              {dirty ? 'Сохранить профиль' : 'Сохранено'}
            </button>
            <button onClick={duplicate} className="px-3 py-1.5 rounded-md border border-[var(--border-strong)]">Дублировать</button>
            <button onClick={remove} className="px-3 py-1.5 rounded-md border border-[var(--accent-red)]/50 text-[var(--accent-red)]">Удалить</button>
            <Link to="/simulation" className="px-3 py-1.5 rounded-md border border-[var(--border-strong)]">К симуляции →</Link>
          </>
        )}
      </div>

      {templates.find((t) => t.key === templateKey) && (
        <div className="px-3 py-1.5 border-b border-[var(--border)] bg-[var(--surface)] text-[11px] text-[var(--text-faint)]">
          <span className="text-[var(--text-muted)]">Шаблон «{templates.find((t) => t.key === templateKey)!.name}»:</span>{' '}
          {templates.find((t) => t.key === templateKey)!.description}
        </div>
      )}

      {!profile ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-[var(--text-faint)] text-sm">
          <p>Выберите профиль перекрёстка или создайте новый из шаблона.</p>
          <p className="text-xs">Доступно шаблонов: {templates.length} — от простого 2-фазного до 3–4-полосных схем.</p>
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 min-w-0 flex flex-col">
            <div className="flex-1 min-h-0 relative">
              <div className="absolute inset-0 flex items-center justify-center p-3">
                <div className="h-full aspect-square max-w-full">
                  <IntersectionScene profile={profile} selectedLaneId={selectedLaneId}
                    highlightGroupIds={highlightGroups} highlightLaneIds={highlightLanes}
                    onLaneClick={(id) => setSelectedLaneId(id === selectedLaneId ? null : id)} />
                </div>
              </div>
              <p className="absolute left-3 bottom-3 text-[11px] text-[var(--text-faint)] max-w-xs leading-snug">
                Цвет стоп-линии — сигнальная группа манёвра. Клик по полосе выбирает её.
                На вкладках «Группы»/«Фазы» подсвечиваются полосы выбранной группы/фазы.
              </p>
            </div>
          </div>

          <div className="w-[560px] shrink-0 border-l border-[var(--border)] bg-[var(--surface)] flex flex-col overflow-hidden">
            <div className="flex flex-wrap gap-1 p-2 border-b border-[var(--border)]">
              {TABS.map((t) => (
                <button key={t.key} onClick={() => setTab(t.key)}
                  className={clsx('px-2.5 py-1 rounded-md text-xs border',
                    tab === t.key ? 'bg-[var(--surface-raised)] border-[var(--border-strong)] text-[var(--text)]'
                      : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text)]')}>
                  {t.label}
                </button>
              ))}
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {tab === 'lanes' && <LanesTab profile={profile} edit={edit} selectedLaneId={selectedLaneId} onSelectLane={setSelectedLaneId} />}
              {tab === 'groups' && <GroupsTab profile={profile} edit={edit} selectedGroupId={selectedGroupId} onSelectGroup={setSelectedGroupId} />}
              {tab === 'conflicts' && <ConflictsTab profile={profile} edit={edit} />}
              {tab === 'phases' && <PhasesTab profile={profile} edit={edit} selectedPhaseId={selectedPhaseId} onSelectPhase={setSelectedPhaseId} />}
              {tab === 'timings' && <TimingsTab profile={profile} edit={edit} />}
              {tab === 'traffic' && <TrafficTab profile={profile} edit={edit} selectedLaneId={selectedLaneId} />}
            </div>
            <div className="max-h-48 overflow-y-auto border-t border-[var(--border)] p-3 text-xs shrink-0">
              {errors.length > 0 ? (
                <>
                  <p className="text-[var(--accent-red)] font-medium mb-1">
                    Профиль не пройдёт проверку ({errors.length}) — сохранение и запуск заблокированы:
                  </p>
                  <ul className="list-disc pl-4 flex flex-col gap-0.5 text-[var(--accent-red)]">
                    {errors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </>
              ) : (
                <p className="text-[var(--accent-teal)]">
                  ✓ Профиль корректен{savedOk ? ' и сохранён' : dirty ? ' (не сохранён)' : ''}.
                </p>
              )}
              {warnings.length > 0 && (
                <ul className="list-disc pl-4 mt-1.5 flex flex-col gap-0.5 text-[var(--accent-amber)]">
                  {warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
