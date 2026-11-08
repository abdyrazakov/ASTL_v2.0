import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { CountDirection, Lane, Point, Profile, ReferencePointMode, VideoInfo } from '../api/types'
import { TopNav } from '../components/layout/TopNav'
import { EditorCanvas, type GeomField, type LayerVisibility, type Tool } from '../components/editor/EditorCanvas'
import { Toolbar } from '../components/editor/Toolbar'
import { LaneSidebar } from '../components/editor/LaneSidebar'
import { useHistory } from '../hooks/useHistory'
import { useAppState } from '../state/AppState'
import { insetPolygon, newDraftLane, segmentsSelfIntersect, pointInPolygon } from '../lib/laneFactory'

interface DraftState {
  base: { id: string; name: string; color: string; reference_point_mode: ReferencePointMode | null }
  step: 'observation' | 'queue' | 'line'
  observation: Point[]
  queue: Point[]
  linePoints: Point[]
  dirPoint: Point | null
}

function emptyProfileMeta(video: VideoInfo): Pick<Profile, 'name' | 'status' | 'notes' | 'reference_point_mode' | 'analysis_params' | 'source_video'> {
  return {
    name: `${video.filename} — новый профиль`,
    status: 'preliminary',
    notes: '',
    reference_point_mode: 'bottom_center',
    source_video: {
      filename: video.filename,
      width: video.width,
      height: video.height,
      fps: video.fps,
      duration_sec: video.duration_sec,
    },
    analysis_params: {
      model_name: 'yolo11n.pt',
      conf_threshold: 0.35,
      iou_threshold: 0.5,
      classes: ['car', 'bus', 'truck', 'motorcycle'],
      lane_switch_hysteresis_sec: 0.5,
      track_lost_grace_sec: 1.0,
      stationary_track_retention_sec: 4.0,
      reid_max_distance_bbox_h: 0.5,
      reid_min_box_overlap: 0.6,
      reid_new_track_window_sec: 1.0,
      tracker_buffer_sec: 3.0,
      tracker_low_conf: 0.1,
      speed_window_sec: 0.8,
      stop_max_drift_bbox_h: 0.2,
      stop_duration_threshold_sec: 2.0,
      stop_exit_speed: 1.0,
      queue_exit_duration_sec: 1.0,
      flow_window_sec: 60,
      crossing_cooldown_sec: 0.5,
    },
  }
}

function sourceVideoCompatible(profile: Profile, video: VideoInfo): boolean {
  const ratioA = profile.source_video.width / profile.source_video.height
  const ratioB = video.width / video.height
  return Math.abs(ratioA - ratioB) < 0.02
}

export function EditorPage() {
  const { videoId, profileId, setVideoId, setProfileId } = useAppState()
  const [videos, setVideos] = useState<VideoInfo[]>([])
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [video, setVideo] = useState<VideoInfo | null>(null)

  const [meta, setMeta] = useState<ReturnType<typeof emptyProfileMeta> | null>(null)
  const lanesHist = useHistory<Lane[]>([])
  const [selectedLaneId, setSelectedLaneId] = useState<string | null>(null)
  const [tool, setTool] = useState<Tool>('select')
  const [draft, setDraft] = useState<DraftState | null>(null)
  const [frameTime, setFrameTime] = useState(0)
  const [visibility, setVisibility] = useState<LayerVisibility>({ lanes: true, queueZones: true, lines: true })
  const [errors, setErrors] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [savedOk, setSavedOk] = useState(false)
  const [incompatibleWarning, setIncompatibleWarning] = useState(false)
  const [showParams, setShowParams] = useState(false)
  const [uploading, setUploading] = useState(false)
  const canvasResetRef = useRef<() => void>(() => {})

  useEffect(() => {
    api.listVideos().then(setVideos).catch(() => {})
    api.listProfiles().then(setProfiles).catch(() => {})
  }, [])

  useEffect(() => {
    if (!videoId) { setVideo(null); return }
    api.getVideo(videoId).then(setVideo).catch(() => setVideo(null))
  }, [videoId])

  // Загрузка профиля при выборе
  useEffect(() => {
    if (!profileId) return
    api.getProfile(profileId).then((p) => {
      setMeta({
        name: p.name, status: p.status, notes: p.notes,
        reference_point_mode: p.reference_point_mode,
        source_video: p.source_video, analysis_params: p.analysis_params,
      })
      lanesHist.resetTo(p.lanes)
      setSelectedLaneId(null)
    }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId])

  // Совместимость профиля с выбранным видео
  useEffect(() => {
    if (!video || !meta) { setIncompatibleWarning(false); return }
    const fakeProfile = { source_video: meta.source_video } as Profile
    setIncompatibleWarning(!sourceVideoCompatible(fakeProfile, video))
  }, [video, meta])

  const refreshProfiles = () => api.listProfiles().then(setProfiles).catch(() => {})

  async function handleUpload(file: File) {
    setUploading(true)
    try {
      const v = await api.uploadVideo(file)
      setVideos((prev) => [v, ...prev])
      setVideoId(v.video_id)
    } catch (e) {
      alert('Не удалось загрузить видео: ' + (e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  function startNewProfile() {
    if (!video) return
    setMeta(emptyProfileMeta(video))
    lanesHist.resetTo([])
    setSelectedLaneId(null)
    setProfileId(null)
    setIncompatibleWarning(false)
  }

  function handleAddLane() {
    const base = newDraftLane(lanesHist.state)
    setDraft({ base, step: 'observation', observation: [], queue: [], linePoints: [], dirPoint: null })
    setTool('draw_observation')
    setSelectedLaneId(null)
  }

  function cancelDraft() {
    setDraft(null)
    setTool('select')
  }

  const addError = useCallback((msg: string) => setErrors((prev) => [msg, ...prev].slice(0, 6)), [])

  function handleStageClick(p: Point) {
    if (!draft) return
    if (p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1) return
    if (tool === 'draw_observation') {
      setDraft({ ...draft, observation: [...draft.observation, p] })
    } else if (tool === 'draw_queue') {
      setDraft({ ...draft, queue: [...draft.queue, p] })
    } else if (tool === 'draw_line') {
      if (draft.linePoints.length < 2) {
        setDraft({ ...draft, linePoints: [...draft.linePoints, p] })
      } else if (!draft.dirPoint) {
        setDraft({ ...draft, dirPoint: p })
      }
    }
  }

  function finalizeStep() {
    if (!draft) return
    if (tool === 'draw_observation') {
      if (draft.observation.length < 3) { addError('Нужно минимум 3 вершины для полигона полосы'); return }
      if (segmentsSelfIntersect(draft.observation)) { addError('Полигон полосы самопересекается'); return }
      setDraft({ ...draft, step: 'queue', queue: insetPolygon(draft.observation, 0.8) })
      setTool('draw_queue')
    } else if (tool === 'draw_queue') {
      if (draft.queue.length < 3) { addError('Нужно минимум 3 вершины для зоны очереди'); return }
      if (segmentsSelfIntersect(draft.queue)) { addError('Зона очереди самопересекается'); return }
      const outside = draft.queue.filter((pt) => !pointInPolygon(pt, draft.observation))
      if (outside.length > 0) { addError('Зона очереди должна быть внутри полигона полосы'); return }
      setDraft({ ...draft, step: 'line' })
      setTool('draw_line')
    } else if (tool === 'draw_line') {
      if (draft.linePoints.length < 2 || !draft.dirPoint) {
        addError('Укажите две точки линии и точку направления')
        return
      }
      const [p1, p2] = draft.linePoints
      const len = Math.hypot(p2.x - p1.x, p2.y - p1.y)
      if (len < 1e-4) { addError('Линия подсчёта имеет нулевую длину'); return }
      const cross = (p2.x - p1.x) * (draft.dirPoint.y - p1.y) - (p2.y - p1.y) * (draft.dirPoint.x - p1.x)
      if (Math.abs(cross) < 1e-6) { addError('Точка направления не может лежать на линии'); return }

      const newLane: Lane = {
        id: draft.base.id,
        name: draft.base.name,
        color: draft.base.color,
        observation_polygon: { points: draft.observation },
        queue_zone_polygon: { points: draft.queue },
        count_line: { p1, p2, positive_side_point: draft.dirPoint, direction: 'positive' },
        reference_point_mode: draft.base.reference_point_mode,
      }
      lanesHist.set((prev) => [...prev, newLane])
      setDraft(null)
      setTool('select')
      setSelectedLaneId(newLane.id)
    }
  }

  // Клавиатура: Enter/Escape для рисования, Ctrl+Z/Ctrl+Shift+Z для undo/redo
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === 'Enter') { e.preventDefault(); finalizeStep() }
      else if (e.key === 'Escape') { e.preventDefault(); cancelDraft() }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault()
        if (e.shiftKey) lanesHist.redo(); else lanesHist.undo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, tool])

  function updateLanePoint(laneId: string, field: GeomField, index: number | null, p: Point) {
    const clamped = { x: Math.min(1, Math.max(0, p.x)), y: Math.min(1, Math.max(0, p.y)) }
    lanesHist.set((prev) => prev.map((lane) => {
      if (lane.id !== laneId) return lane
      if (field === 'observation') {
        const pts = [...lane.observation_polygon.points]; pts[index!] = clamped
        return { ...lane, observation_polygon: { points: pts } }
      }
      if (field === 'queue') {
        const pts = [...lane.queue_zone_polygon.points]; pts[index!] = clamped
        return { ...lane, queue_zone_polygon: { points: pts } }
      }
      if (field === 'line_p1') return { ...lane, count_line: { ...lane.count_line, p1: clamped } }
      if (field === 'line_p2') return { ...lane, count_line: { ...lane.count_line, p2: clamped } }
      if (field === 'line_dir') return { ...lane, count_line: { ...lane.count_line, positive_side_point: clamped } }
      return lane
    }), { record: false })
  }

  // Фиксируем изменение в истории по отпусканию мыши (чтобы не засорять стек по каждому пикселю)
  useEffect(() => {
    function onUp() { lanesHist.set((prev) => prev, { record: true }) }
    window.addEventListener('mouseup', onUp)
    return () => window.removeEventListener('mouseup', onUp)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function insertVertex(laneId: string, field: 'observation' | 'queue', index: number, p: Point) {
    lanesHist.set((prev) => prev.map((lane) => {
      if (lane.id !== laneId) return lane
      const key = field === 'observation' ? 'observation_polygon' : 'queue_zone_polygon'
      const pts = [...lane[key].points]
      pts.splice(index, 0, p)
      return { ...lane, [key]: { points: pts } }
    }))
  }

  function deleteVertex(laneId: string, field: 'observation' | 'queue', index: number) {
    lanesHist.set((prev) => prev.map((lane) => {
      if (lane.id !== laneId) return lane
      const key = field === 'observation' ? 'observation_polygon' : 'queue_zone_polygon'
      const pts = lane[key].points.filter((_, i) => i !== index)
      return { ...lane, [key]: { points: pts } }
    }))
  }

  function deleteLane(id: string) {
    if (!confirm('Удалить полосу?')) return
    lanesHist.set((prev) => prev.filter((l) => l.id !== id))
    if (selectedLaneId === id) setSelectedLaneId(null)
  }

  function renameLane(id: string, name: string) {
    lanesHist.set((prev) => prev.map((l) => (l.id === id ? { ...l, name } : l)), { record: false })
  }
  function recolorLane(id: string, color: string) {
    lanesHist.set((prev) => prev.map((l) => (l.id === id ? { ...l, color } : l)))
  }
  function changeDirection(id: string, dir: CountDirection) {
    lanesHist.set((prev) => prev.map((l) => (l.id === id ? { ...l, count_line: { ...l.count_line, direction: dir } } : l)))
  }
  function changeRefMode(id: string, mode: ReferencePointMode | null) {
    lanesHist.set((prev) => prev.map((l) => (l.id === id ? { ...l, reference_point_mode: mode } : l)))
  }

  const idSet = useMemo(() => new Set(lanesHist.state.map((l) => l.id)), [lanesHist.state])
  const nameSet = useMemo(() => new Set(lanesHist.state.map((l) => l.name)), [lanesHist.state])
  const hasDuplicateIds = idSet.size !== lanesHist.state.length
  const hasDuplicateNames = nameSet.size !== lanesHist.state.length

  async function handleSave() {
    if (!meta || !video) return
    if (lanesHist.state.length === 0) { addError('Добавьте хотя бы одну полосу перед сохранением'); return }
    if (hasDuplicateIds || hasDuplicateNames) { addError('ID и названия полос должны быть уникальны'); return }
    setSaving(true)
    setSavedOk(false)
    const payload: Partial<Profile> = { ...meta, lanes: lanesHist.state }
    try {
      const saved = profileId
        ? await api.updateProfile(profileId, payload)
        : await api.createProfile(payload)
      setProfileId(saved.profile_id)
      setErrors([])
      setSavedOk(true)
      refreshProfiles()
      setTimeout(() => setSavedOk(false), 2500)
    } catch (e: unknown) {
      const err = e as { message?: string }
      try {
        const parsed = JSON.parse(err.message || '{}')
        setErrors(parsed.errors || [err.message || 'Ошибка сохранения'])
      } catch {
        setErrors([err.message || 'Ошибка сохранения'])
      }
    } finally {
      setSaving(false)
    }
  }

  async function handleDuplicate() {
    if (!profileId) return
    const copy = await api.duplicateProfile(profileId)
    refreshProfiles()
    setProfileId(copy.profile_id)
  }

  const draftVisual = draft
    ? { color: draft.base.color, observation: draft.observation, queue: draft.queue, linePoints: draft.linePoints, dirPoint: draft.dirPoint }
    : null

  return (
    <div className="h-full flex flex-col">
      <TopNav
        right={
          <div className="flex items-center gap-2 text-sm">
            {savedOk && <span className="text-[var(--accent-teal)]">Сохранено ✓</span>}
            <button
              onClick={handleSave}
              disabled={saving || !video || lanesHist.state.length === 0}
              className="px-3 py-1.5 rounded-md bg-[var(--accent-teal-dim)] border border-[var(--accent-teal)] text-white disabled:opacity-40"
            >
              {saving ? 'Сохранение…' : 'Сохранить профиль'}
            </button>
            {profileId && (
              <button onClick={handleDuplicate} className="px-3 py-1.5 rounded-md border border-[var(--border)] text-[var(--text-muted)]">
                Дублировать
              </button>
            )}
          </div>
        }
      />

      <div className="flex items-center gap-3 px-3 py-2 border-b border-[var(--border)] bg-[var(--surface)] flex-wrap text-sm">
        <label className="text-[var(--text-muted)]">Видео:</label>
        <select
          value={videoId ?? ''}
          onChange={(e) => setVideoId(e.target.value || null)}
          className="bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1"
        >
          <option value="">— выберите видео —</option>
          {videos.map((v) => (
            <option key={v.video_id} value={v.video_id}>{v.filename} ({v.width}×{v.height})</option>
          ))}
        </select>
        <label className="px-2 py-1 rounded border border-[var(--border)] cursor-pointer text-[var(--text-muted)] hover:text-[var(--text)]">
          {uploading ? 'Загрузка…' : '+ Загрузить видео'}
          <input
            type="file" accept="video/*" className="hidden" disabled={uploading}
            onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
          />
        </label>

        <div className="w-px h-5 bg-[var(--border)] mx-1" />

        <label className="text-[var(--text-muted)]">Профиль:</label>
        <select
          value={profileId ?? ''}
          onChange={(e) => setProfileId(e.target.value || null)}
          className="bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1"
        >
          <option value="">— новый профиль —</option>
          {profiles.map((p) => (
            <option key={p.profile_id} value={p.profile_id}>
              {p.name} {p.status === 'preliminary' ? '(предв.)' : ''}
            </option>
          ))}
        </select>
        <button onClick={startNewProfile} disabled={!video} className="px-2 py-1 rounded border border-[var(--border)] text-[var(--text-muted)] disabled:opacity-40">
          Создать новый
        </button>

        {meta && (
          <>
            <div className="w-px h-5 bg-[var(--border)] mx-1" />
            <input
              value={meta.name}
              onChange={(e) => setMeta({ ...meta, name: e.target.value })}
              className="bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1 w-56"
            />
            <label className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
              <input
                type="checkbox"
                checked={meta.status === 'verified'}
                onChange={(e) => setMeta({ ...meta, status: e.target.checked ? 'verified' : 'preliminary' })}
              />
              проверено на видео
            </label>
            <button
              onClick={() => setShowParams((v) => !v)}
              className="px-2 py-1 rounded border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]"
            >
              ⚙ Параметры анализа
            </button>
          </>
        )}
      </div>

      {meta && showParams && (
        <div className="flex items-center gap-4 px-4 py-2 border-b border-[var(--border)] bg-[var(--surface-raised)] flex-wrap text-xs">
          <div className="flex items-center gap-1.5">
            <label className="text-[var(--text-muted)]">Модель детектора</label>
            <select
              value={meta.analysis_params.model_name}
              onChange={(e) => setMeta({ ...meta, analysis_params: { ...meta.analysis_params, model_name: e.target.value } })}
              className="bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1"
            >
              <option value="yolo11n.pt">yolo11n — быстрее, ниже точность (по умолчанию)</option>
              <option value="yolo11s.pt">yolo11s — точнее, медленнее</option>
              <option value="yolo11m.pt">yolo11m — ещё точнее, заметно медленнее на CPU</option>
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <label className="text-[var(--text-muted)]" title="Ниже — обнаруживает больше машин (в т.ч. частично закрытых), но больше ложных срабатываний">
              Порог уверенности (conf)
            </label>
            <input
              type="number" min={0.05} max={0.9} step={0.05}
              value={meta.analysis_params.conf_threshold}
              onChange={(e) => setMeta({ ...meta, analysis_params: { ...meta.analysis_params, conf_threshold: parseFloat(e.target.value) || 0.35 } })}
              className="w-16 bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1"
            />
          </div>
          <div className="flex items-center gap-1.5">
            <label className="text-[var(--text-muted)]" title="Выше — реже 'склеивает' в одну две соседние машины как дубликат одной рамки">
              Порог NMS (iou)
            </label>
            <input
              type="number" min={0.2} max={0.9} step={0.05}
              value={meta.analysis_params.iou_threshold}
              onChange={(e) => setMeta({ ...meta, analysis_params: { ...meta.analysis_params, iou_threshold: parseFloat(e.target.value) || 0.5 } })}
              className="w-16 bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1"
            />
          </div>
          <span className="text-[var(--text-faint)]">
            Машины рядом друг с другом иногда не распознаются — это ограничение модели и
            порогов, а не видео. Понизьте conf или поднимите iou, либо возьмите модель
            точнее (это замедлит обработку на CPU).
          </span>
        </div>
      )}

      {incompatibleWarning && (
        <div className="px-4 py-2 bg-[var(--accent-amber)]/15 border-b border-[var(--accent-amber)]/40 text-sm text-[var(--accent-amber)]">
          Выбранный профиль создан для видео с другим соотношением сторон. Выберите подходящий профиль в списке выше
          или нажмите «Создать новый» — автоматически применять несовместимую разметку нельзя.
        </div>
      )}

      {!video && (
        <div className="flex-1 flex items-center justify-center text-[var(--text-faint)]">
          Выберите или загрузите видео, чтобы начать разметку.
        </div>
      )}

      {video && !meta && (
        <div className="flex-1 flex items-center justify-center text-[var(--text-faint)]">
          Выберите профиль или создайте новый.
        </div>
      )}

      {video && meta && (
        <>
          <Toolbar
            tool={tool}
            visibility={visibility}
            onToggleVisibility={(k) => setVisibility((v) => ({ ...v, [k]: !v[k] }))}
            onUndo={lanesHist.undo}
            onRedo={lanesHist.redo}
            canUndo={lanesHist.canUndo}
            canRedo={lanesHist.canRedo}
            onResetView={() => canvasResetRef.current()}
          />

          {draft && (
            <div className="px-3 py-1.5 bg-[var(--accent-teal-dim)]/20 border-b border-[var(--accent-teal)]/30 text-xs flex items-center gap-3">
              <span>Новая полоса «{draft.base.name}» — шаг: {draft.step === 'observation' ? 'область наблюдения' : draft.step === 'queue' ? 'зона очереди' : 'линия подсчёта'}</span>
              <button onClick={cancelDraft} className="underline text-[var(--text-muted)]">отменить (Esc)</button>
            </div>
          )}

          {errors.length > 0 && (
            <div className="px-3 py-1.5 bg-[var(--accent-red)]/15 border-b border-[var(--accent-red)]/30 text-xs text-[var(--accent-red)] flex items-center justify-between">
              <span>{errors[0]}</span>
              <button onClick={() => setErrors([])} className="opacity-70">✕</button>
            </div>
          )}

          <div className="flex-1 flex overflow-hidden">
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="flex-1 overflow-hidden">
                <EditorCanvas
                  frameUrl={api.frameUrl(video.video_id, frameTime)}
                  videoW={video.width}
                  videoH={video.height}
                  lanes={lanesHist.state}
                  selectedLaneId={selectedLaneId}
                  tool={tool}
                  draft={draftVisual}
                  visibility={visibility}
                  onStageClick={handleStageClick}
                  onSelectLane={setSelectedLaneId}
                  onUpdatePoint={updateLanePoint}
                  onInsertVertex={insertVertex}
                  onDeleteVertex={deleteVertex}
                />
              </div>
              <div className="border-t border-[var(--border)] bg-[var(--surface)] px-4 py-2 flex items-center gap-3">
                <span className="text-xs text-[var(--text-muted)] font-mono-tab w-14">{frameTime.toFixed(1)}с</span>
                <input
                  type="range" min={0} max={video.duration_sec} step={0.1} value={frameTime}
                  onChange={(e) => setFrameTime(parseFloat(e.target.value))}
                  className="flex-1 accent-[var(--accent-teal)]"
                />
                <span className="text-xs text-[var(--text-faint)] font-mono-tab w-16 text-right">
                  / {video.duration_sec.toFixed(1)}с
                </span>
              </div>
            </div>

            <LaneSidebar
              lanes={lanesHist.state}
              selectedLaneId={selectedLaneId}
              onSelect={setSelectedLaneId}
              onAddLane={handleAddLane}
              addingLane={!!draft}
              onDeleteLane={deleteLane}
              onRenameLane={renameLane}
              onRecolorLane={recolorLane}
              onChangeDirection={changeDirection}
              onChangeRefMode={changeRefMode}
            />
          </div>
        </>
      )}
    </div>
  )
}
