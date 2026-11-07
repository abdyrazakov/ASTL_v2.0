import type {
  JobProgress,
  Profile,
  RenderOptions,
  TrafficSnapshot,
  VideoInfo,
} from './types'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: init?.body && !(init.body instanceof FormData)
      ? { 'Content-Type': 'application/json', ...(init.headers || {}) }
      : init?.headers,
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data)
    } catch {
      // игнорируем — используем statusText
    }
    throw new ApiError(detail, res.status)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export const api = {
  // --- видео ---
  uploadVideo(file: File): Promise<VideoInfo> {
    const form = new FormData()
    form.append('file', file)
    return req('/api/videos', { method: 'POST', body: form })
  },
  listVideos(): Promise<VideoInfo[]> {
    return req('/api/videos')
  },
  getVideo(id: string): Promise<VideoInfo> {
    return req(`/api/videos/${id}`)
  },
  frameUrl(videoId: string, t: number): string {
    return `/api/videos/${videoId}/frame?t=${t.toFixed(3)}`
  },

  // --- профили ---
  createProfile(profile: Partial<Profile>): Promise<Profile> {
    return req('/api/profiles', { method: 'POST', body: JSON.stringify(profile) })
  },
  updateProfile(id: string, profile: Partial<Profile>): Promise<Profile> {
    return req(`/api/profiles/${id}`, { method: 'PUT', body: JSON.stringify(profile) })
  },
  listProfiles(): Promise<Profile[]> {
    return req('/api/profiles')
  },
  getProfile(id: string): Promise<Profile> {
    return req(`/api/profiles/${id}`)
  },
  deleteProfile(id: string): Promise<void> {
    return req(`/api/profiles/${id}`, { method: 'DELETE' })
  },
  duplicateProfile(id: string): Promise<Profile> {
    return req(`/api/profiles/${id}/duplicate`, { method: 'POST' })
  },
  validateProfile(profile: Partial<Profile>): Promise<{ valid: boolean; errors: string[] }> {
    return req('/api/profiles/validate', { method: 'POST', body: JSON.stringify(profile) })
  },

  // --- задания анализа ---
  createJob(videoId: string, profileId: string): Promise<JobProgress> {
    return req('/api/jobs', {
      method: 'POST',
      body: JSON.stringify({ video_id: videoId, profile_id: profileId }),
    })
  },
  getActiveJob(): Promise<{ active: boolean } & Partial<JobProgress>> {
    return req('/api/jobs/active')
  },
  getJob(runId: string): Promise<JobProgress> {
    return req(`/api/jobs/${runId}`)
  },
  pauseJob(runId: string): Promise<JobProgress> {
    return req(`/api/jobs/${runId}/pause`, { method: 'POST' })
  },
  resumeJob(runId: string): Promise<JobProgress> {
    return req(`/api/jobs/${runId}/resume`, { method: 'POST' })
  },
  stopJob(runId: string): Promise<JobProgress> {
    return req(`/api/jobs/${runId}/stop`, { method: 'POST' })
  },
  setRenderOptions(runId: string, options: Partial<RenderOptions>): Promise<unknown> {
    return req(`/api/jobs/${runId}/render-options`, { method: 'PATCH', body: JSON.stringify(options) })
  },
  getSnapshot(runId: string): Promise<TrafficSnapshot> {
    return req(`/api/jobs/${runId}/snapshot`)
  },
  getHistory(runId: string, since = 0): Promise<TrafficSnapshot[]> {
    return req(`/api/jobs/${runId}/history?since=${since}`)
  },
  liveStreamUrl(runId: string): string {
    return `/api/jobs/${runId}/live.mjpg`
  },
  exportFileUrl(runId: string, filename: string): string {
    return `/output/${runId}/${filename}`
  },
}
