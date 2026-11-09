import { createContext, useContext, type ReactNode } from 'react'

/** Номер шага внутри слайда: каждое нажатие стрелки открывает следующий шаг. */
export const StepContext = createContext(0)

export function useStep() {
  return useContext(StepContext)
}

/** Блок, который открывается нажатием (шаг ≥ at). Движение — ответ на действие докладчика. */
export function Step({ at, className = '', children }: { at: number; className?: string; children: ReactNode }) {
  const on = useStep() >= at
  return <div className={`step ${on ? '' : 'off'} ${className}`} aria-hidden={!on}>{children}</div>
}

/** Типовая колонка контентного слайда: слева, у левого поля, ширина под строку < 80 знаков. */
export function Column({ children, width = 620 }: { children: ReactNode; width?: number }) {
  return (
    <div className="absolute top-[118px] left-[120px] flex flex-col" style={{ width }}>
      {children}
    </div>
  )
}

export function Heading({ children }: { children: ReactNode }) {
  return <h2 className="text-[58px] leading-[1.04] font-extrabold tracking-[-0.022em] text-paint">{children}</h2>
}

export function Lead({ children }: { children: ReactNode }) {
  return <p className="mt-7 text-[25px] leading-[1.5] text-paint-dim">{children}</p>
}
