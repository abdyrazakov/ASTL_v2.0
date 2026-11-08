// API этапа 2: профили перекрёстка и прогоны симуляции.
import { req } from './client'
import type {
  Comparison,
  ControllerMode,
  GreenRecord,
  IntersectionProfile,
  Scene,
  SimProgress,
  SimSnapshot,
  TemplateInfo,
  ValidationResult,
} from './simTypes'

const J = (body: unknown): RequestInit => ({ body: JSON.stringify(body) })

export const simApi = {
  // --- профили перекрёстка ---
  listTemplates(): Promise<TemplateInfo[]> {
    return req('/api/intersections/templates')
  },
  createFromTemplate(key: string): Promise<IntersectionProfile> {
    return req(`/api/intersections/from-template/${key}`, { method: 'POST' })
  },
  listProfiles(): Promise<IntersectionProfile[]> {
    return req('/api/intersections')
  },
  getProfile(id: string): Promise<IntersectionProfile> {
    return req(`/api/intersections/${id}`)
  },
  updateProfile(id: string, p: IntersectionProfile): Promise<IntersectionProfile> {
    return req(`/api/intersections/${id}`, { method: 'PUT', ...J(p) })
  },
  deleteProfile(id: string): Promise<void> {
    return req(`/api/intersections/${id}`, { method: 'DELETE' })
  },
  duplicateProfile(id: string): Promise<IntersectionProfile> {
    return req(`/api/intersections/${id}/duplicate`, { method: 'POST' })
  },
  validateProfile(p: IntersectionProfile): Promise<ValidationResult> {
    return req('/api/intersections/validate', { method: 'POST', ...J(p) })
  },

  // --- прогоны ---
  start(body: {
    profile_id: string
    controller_mode: ControllerMode
    seed: number | null
    duration_sec: number | null
    speed: number
  }): Promise<SimProgress> {
    return req('/api/simulations', { method: 'POST', ...J(body) })
  },
  getActive(): Promise<{ active: boolean } & Partial<SimProgress>> {
    return req('/api/simulations/active')
  },
  get(runId: string): Promise<SimProgress> {
    return req(`/api/simulations/${runId}`)
  },
  pause(runId: string): Promise<SimProgress> {
    return req(`/api/simulations/${runId}/pause`, { method: 'POST' })
  },
  resume(runId: string): Promise<SimProgress> {
    return req(`/api/simulations/${runId}/resume`, { method: 'POST' })
  },
  stop(runId: string): Promise<SimProgress> {
    return req(`/api/simulations/${runId}/stop`, { method: 'POST' })
  },
  setMode(runId: string, mode: ControllerMode): Promise<SimProgress> {
    return req(`/api/simulations/${runId}/controller`, { method: 'PATCH', ...J({ mode }) })
  },
  setSpeed(runId: string, speed: number): Promise<SimProgress> {
    return req(`/api/simulations/${runId}/speed`, { method: 'PATCH', ...J({ speed }) })
  },
  scene(runId: string): Promise<Scene> {
    return req(`/api/simulations/${runId}/scene`)
  },
  snapshot(runId: string): Promise<SimSnapshot> {
    return req(`/api/simulations/${runId}/snapshot`)
  },
  history(runId: string, since = 0): Promise<SimSnapshot[]> {
    return req(`/api/simulations/${runId}/history?since=${since}`)
  },
  phaseLog(runId: string, since = 0): Promise<GreenRecord[]> {
    return req(`/api/simulations/${runId}/phase-log?since=${since}`)
  },
  comparison(profileId: string, seed: number, durationSec: number | null): Promise<Comparison> {
    const dur = durationSec != null ? `&duration_sec=${durationSec}` : ''
    return req(`/api/simulations/comparison?profile_id=${profileId}&seed=${seed}${dur}`)
  },
  compare(profileId: string, seed: number, durationSec: number): Promise<Comparison> {
    return req('/api/simulations/compare', {
      method: 'POST',
      ...J({ profile_id: profileId, seed, duration_sec: durationSec }),
    })
  },
  exportUrl(runId: string, file: string): string {
    return `/output/${runId}/${file}`
  },
}

export const EXPORT_FILES = [
  'traffic_metrics.csv',
  'traffic_history.jsonl',
  'traffic_state.json',
  'phase_log.jsonl',
  'signal_log.jsonl',
  'events.jsonl',
  'summary.json',
  'profile.json',
  'run_metadata.json',
]
