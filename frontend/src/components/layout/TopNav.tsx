import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import clsx from 'clsx'

const tabClass = ({ isActive }: { isActive: boolean }) =>
  clsx(
    'px-3 py-1.5 text-sm rounded-md transition-colors',
    isActive
      ? 'bg-[var(--surface-raised)] text-[var(--text)] border border-[var(--border-strong)]'
      : 'text-[var(--text-muted)] hover:text-[var(--text)] border border-transparent',
  )

export function TopNav({ right }: { right?: ReactNode }) {
  return (
    <header className="flex items-center gap-4 border-b border-[var(--border)] bg-[var(--surface)] px-4 py-2.5 shrink-0">
      <div className="flex items-center gap-2 pr-2 border-r border-[var(--border)]">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
          <rect x="9" y="2" width="6" height="20" rx="2" fill="var(--accent-teal)" opacity="0.18" />
          <circle cx="12" cy="6" r="2.1" fill="var(--accent-red)" />
          <circle cx="12" cy="12" r="2.1" fill="var(--accent-amber)" />
          <circle cx="12" cy="18" r="2.1" fill="var(--accent-teal)" />
        </svg>
        <span className="font-semibold tracking-tight text-[15px]">ASTL</span>
      </div>
      <nav className="flex items-center gap-1">
        <NavLink to="/editor" className={tabClass}>
          Настройка камеры
        </NavLink>
        <NavLink to="/analysis" className={tabClass}>
          Анализ движения
        </NavLink>
      </nav>
      <div className="flex-1" />
      <div className="flex items-center gap-2">{right}</div>
    </header>
  )
}
