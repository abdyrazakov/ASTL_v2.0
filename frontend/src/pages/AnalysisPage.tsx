import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Profile, VideoInfo } from '../api/types'
import { TopNav } from '../components/layout/TopNav'
import { AnalysisTopBar } from '../components/analysis/AnalysisTopBar'
import { VideoPanel } from '../components/analysis/VideoPanel'
import { LaneCards } from '../components/analysis/LaneCards'
import { HistoryCharts } from '../components/analysis/HistoryCharts'
import { EventLog } from '../components/analysis/EventLog'
import { DemandRanking } from '../components/analysis/DemandRanking'
import { useJobPolling } from '../hooks/useJobPolling'
import { useAppState } from '../state/AppState'

export function AnalysisPage() {
  const { videoId, profileId, setVideoId, setProfileId } = useAppState()
  const [videos, setVideos] = useState<VideoInfo[]>([])
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [profile, setProfile] = useState<Profile | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [selectedLaneId, setSelectedLaneId] = useState<string | null>(null)
  const [currentTime, setCurrentTime] = useState<number | null>(null)
  const [starting, setStarting] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const { progress, snapshot, history } = useJobPolling(runId)

  useEffect(() => {
    api.listVideos().then(setVideos).catch(() => {})
    api.listProfiles().then(setProfiles).catch(() => {})
    api.getActiveJob().then((a) => {
      if (a.active && a.run_id) {
        setRunId(a.run_id)
        // Восстанавливаем видео/профиль активного задания — иначе при
        // обновлении страницы во время выполнения анализа верхняя панель
        // покажет прогресс, а всё остальное (видео, карточки полос, графики)
        // останется пустым, потому что videoId/profileId не выбраны.
        if (a.video_id) setVideoId(a.video_id)
        if (a.profile_id) setProfileId(a.profile_id)
      }
    }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!profileId) { setProfile(null); return }
    api.getProfile(profileId).then(setProfile).catch(() => setProfile(null))
  }, [profileId])

  async function handleStart() {
    if (!videoId || !profileId) return
    setStarting(true)
    try {
      const job = await api.createJob(videoId, profileId)
      setRunId(job.run_id)
    } catch (e) {
      alert('Не удалось запустить анализ: ' + (e as Error).message)
    } finally {
      setStarting(false)
    }
  }

  async function handlePause() { if (runId) await api.pauseJob(runId) }
  async function handleResume() { if (runId) await api.resumeJob(runId) }
  async function handleStop() { if (runId) await api.stopJob(runId) }

  function handleFullscreen() {
    if (!document.fullscreenElement) rootRef.current?.requestFullscreen()
    else document.exitFullscreen()
  }

  const selectedLane = snapshot?.lanes.find((l) => l.lane_id === selectedLaneId)
  const profileMissing = videoId && !profileId
  const canStart = !!videoId && !!profileId && !!profile?.lanes.length

  return (
    <div ref={rootRef} className="h-full flex flex-col bg-[var(--bg)]">
      <TopNav />
      <AnalysisTopBar
        videos={videos}
        profiles={profiles}
        videoId={videoId}
        profileId={profileId}
        onVideoChange={setVideoId}
        onProfileChange={setProfileId}
        progress={progress}
        onStart={handleStart}
        onPause={handlePause}
        onResume={handleResume}
        onStop={handleStop}
        canStart={canStart}
        onFullscreen={handleFullscreen}
        starting={starting}
      />

      {!videoId && (
        <div className="flex-1 flex items-center justify-center text-[var(--text-faint)] text-sm">
          Видео ещё не выбрано — выберите его вверху или загрузите на вкладке «Настройка камеры».
        </div>
      )}
      {profileMissing && (
        <div className="flex-1 flex items-center justify-center text-[var(--text-faint)] text-sm">
          Профиль разметки не выбран. Создайте его на вкладке «Настройка камеры».
        </div>
      )}
      {videoId && profileId && profile && profile.lanes.length === 0 && (
        <div className="flex-1 flex items-center justify-center text-[var(--text-faint)] text-sm">
          В выбранном профиле нет ни одной полосы — добавьте её в редакторе.
        </div>
      )}

      {videoId && profileId && profile && profile.lanes.length > 0 && (
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 min-h-0">
              <VideoPanel
                progress={progress}
                profile={profile}
                selectedLaneId={selectedLaneId}
                onSelectLane={setSelectedLaneId}
                onTimeUpdate={setCurrentTime}
              />
            </div>
            <div className="h-56 border-t border-[var(--border)] shrink-0">
              <HistoryCharts
                history={history}
                selectedLaneId={selectedLaneId}
                selectedLaneColor={selectedLane?.color ?? 'var(--accent-teal)'}
                currentTime={currentTime}
              />
            </div>
          </div>

          <div className="w-80 shrink-0 border-l border-[var(--border)] bg-[var(--surface)] flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto">
              <LaneCards lanes={snapshot?.lanes ?? []} selectedLaneId={selectedLaneId} onSelect={setSelectedLaneId} />
            </div>
            <div className="h-44 border-t border-[var(--border)] p-0 shrink-0">
              <DemandRanking lanes={snapshot?.lanes ?? []} />
            </div>
            <div className="h-48 border-t border-[var(--border)] shrink-0">
              <EventLog history={history} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
