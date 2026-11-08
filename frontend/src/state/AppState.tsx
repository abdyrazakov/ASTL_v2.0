import { createContext, type ReactNode, useContext, useEffect, useState } from 'react'

interface AppState {
  videoId: string | null
  profileId: string | null
  setVideoId: (id: string | null) => void
  setProfileId: (id: string | null) => void
  // этап 2: выбранный профиль перекрёстка (общий для редактора и симуляции)
  intersectionId: string | null
  setIntersectionId: (id: string | null) => void
}

const Ctx = createContext<AppState | null>(null)

const LS_VIDEO = 'astl.videoId'
const LS_PROFILE = 'astl.profileId'
const LS_INTERSECTION = 'astl.intersectionId'

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [videoId, setVideoIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(LS_VIDEO)
    } catch {
      return null
    }
  })
  const [profileId, setProfileIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(LS_PROFILE)
    } catch {
      return null
    }
  })

  const setVideoId = (id: string | null) => {
    setVideoIdState(id)
    try {
      if (id) localStorage.setItem(LS_VIDEO, id)
      else localStorage.removeItem(LS_VIDEO)
    } catch {
      /* noop */
    }
  }
  const setProfileId = (id: string | null) => {
    setProfileIdState(id)
    try {
      if (id) localStorage.setItem(LS_PROFILE, id)
      else localStorage.removeItem(LS_PROFILE)
    } catch {
      /* noop */
    }
  }

  const [intersectionId, setIntersectionIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(LS_INTERSECTION)
    } catch {
      return null
    }
  })
  const setIntersectionId = (id: string | null) => {
    setIntersectionIdState(id)
    try {
      if (id) localStorage.setItem(LS_INTERSECTION, id)
      else localStorage.removeItem(LS_INTERSECTION)
    } catch {
      /* noop */
    }
  }

  useEffect(() => {}, [])

  return (
    <Ctx.Provider value={{ videoId, profileId, setVideoId, setProfileId, intersectionId, setIntersectionId }}>
      {children}
    </Ctx.Provider>
  )
}

export function useAppState() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAppState must be used within AppStateProvider')
  return ctx
}
