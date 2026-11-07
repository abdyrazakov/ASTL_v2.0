import { useCallback, useRef, useState } from 'react'

/** Простой стек undo/redo поверх неизменяемого состояния. */
export function useHistory<T>(initial: T) {
  const [state, setStateRaw] = useState(initial)
  const past = useRef<T[]>([])
  const future = useRef<T[]>([])

  const set = useCallback((updater: T | ((prev: T) => T), opts?: { record?: boolean }) => {
    setStateRaw((prev) => {
      const next = typeof updater === 'function' ? (updater as (p: T) => T)(prev) : updater
      if (opts?.record !== false) {
        past.current.push(prev)
        if (past.current.length > 100) past.current.shift()
        future.current = []
      }
      return next
    })
  }, [])

  const undo = useCallback(() => {
    setStateRaw((prev) => {
      const last = past.current.pop()
      if (last === undefined) return prev
      future.current.push(prev)
      return last
    })
  }, [])

  const redo = useCallback(() => {
    setStateRaw((prev) => {
      const next = future.current.pop()
      if (next === undefined) return prev
      past.current.push(prev)
      return next
    })
  }, [])

  const canUndo = past.current.length > 0
  const canRedo = future.current.length > 0

  const resetTo = useCallback((value: T) => {
    past.current = []
    future.current = []
    setStateRaw(value)
  }, [])

  return { state, set, undo, redo, canUndo, canRedo, resetTo }
}
