import { useEffect, useState, type ReactNode } from 'react'
import clsx from 'clsx'

export const inputCls =
  'bg-[var(--surface-sunken)] border border-[var(--border)] rounded px-2 py-1 text-sm focus:border-[var(--accent-teal)] outline-none'

/** Числовое поле, которое не мешает набирать дробные значения ("1." / "") и
 * отдаёт число только когда ввод корректен. */
export function NumField({
  value, onChange, step = 1, min, max, className, placeholder, allowEmpty = false, title,
}: {
  value: number | null
  onChange: (v: number | null) => void
  step?: number
  min?: number
  max?: number
  className?: string
  placeholder?: string
  allowEmpty?: boolean
  title?: string
}) {
  const [text, setText] = useState(value == null ? '' : String(value))
  const [focused, setFocused] = useState(false)
  useEffect(() => {
    if (!focused) setText(value == null ? '' : String(value))
  }, [value, focused])
  return (
    <input
      type="number"
      inputMode="decimal"
      title={title}
      value={text}
      step={step}
      min={min}
      max={max}
      placeholder={placeholder}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onChange={(e) => {
        setText(e.target.value)
        if (e.target.value === '') {
          if (allowEmpty) onChange(null)
          return
        }
        const n = Number(e.target.value)
        if (Number.isFinite(n)) onChange(n)
      }}
      className={clsx(inputCls, 'font-mono-tab', className ?? 'w-20')}
    />
  )
}

export function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex items-start gap-3 py-1.5">
      <span className="w-48 shrink-0 pt-1">
        <span className="block text-sm text-[var(--text)]">{label}</span>
        {hint && <span className="block text-[11px] text-[var(--text-faint)] leading-snug mt-0.5">{hint}</span>}
      </span>
      <span className="flex items-center gap-2 flex-wrap">{children}</span>
    </label>
  )
}

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="mb-4">
      <div className="flex items-center justify-between mb-1.5">
        <h3 className="text-xs uppercase tracking-wide text-[var(--text-muted)]">{title}</h3>
        {right}
      </div>
      {children}
    </section>
  )
}

export function SmallButton({ children, onClick, danger, disabled, title }: {
  children: ReactNode
  onClick: () => void
  danger?: boolean
  disabled?: boolean
  title?: string
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
      className={clsx(
        'px-2 py-0.5 rounded border text-xs disabled:opacity-40',
        danger
          ? 'border-[var(--accent-red)]/40 text-[var(--accent-red)] hover:bg-[var(--accent-red)]/10'
          : 'border-[var(--border-strong)] text-[var(--text-muted)] hover:text-[var(--text)]',
      )}>
      {children}
    </button>
  )
}

export function Toggle({ on, onClick, children, title, disabled }: {
  on: boolean
  onClick: () => void
  children: ReactNode
  title?: string
  disabled?: boolean
}) {
  return (
    <button type="button" onClick={onClick} title={title} aria-pressed={on} disabled={disabled}
      className={clsx(
        'px-2 py-0.5 rounded border text-xs transition-colors disabled:opacity-35 disabled:cursor-not-allowed',
        on
          ? 'border-[var(--accent-teal)] bg-[var(--accent-teal-dim)]/50 text-white'
          : 'border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]',
      )}>
      {children}
    </button>
  )
}
