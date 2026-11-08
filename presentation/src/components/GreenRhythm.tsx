import { useReplay, type Mode } from '../data/replay'

// С–Ю — оттенки разметки, З–В — оттенки дорожной жёлтой: два направления читаются как две оси
const PHASE_FILL = ['#eceae2', '#8f918b', '#e9b308', '#8a6d12']
const W = 1360
const LABEL = 260
const FROM = 900
const TO = 1500

/** Зелёные фаз за 10 минут пика, в настоящем масштабе времени: ширина = длительность. */
export function GreenRhythm({ show }: { show: Mode[] }) {
  const r = useReplay()
  const x = (t: number) => LABEL + ((t - FROM) / (TO - FROM)) * (W - LABEL)
  const rows: { mode: Mode; name: string }[] = [
    { mode: 'fixed', name: 'Фиксированный' },
    { mode: 'adaptive', name: 'Адаптивный' },
  ]
  return (
    <div>
      <svg viewBox={`0 0 ${W} 190`} width={W} height={190} role="img"
        aria-label="Зелёные фаз за 10 минут пика: у фиксированного режима одинаковые, у адаптивного — разной длины">
        {rows.map(({ mode, name }, ri) => {
          const y = ri * 78
          const greens = r.runs[mode].greens.filter(([, s, d]) => s + d > FROM && s < TO)
          return (
            <g key={mode} opacity={show.includes(mode) ? 1 : 0} style={{ transition: 'opacity .5s ease' }}>
              <text x={0} y={y + 28} dominantBaseline="central" fontSize={22} fill="#eceae2">{name}</text>
              {greens.map(([ph, s, d], i) => {
                const a = Math.max(s, FROM)
                const b = Math.min(s + d, TO)
                return <rect key={i} x={x(a)} y={y} width={Math.max(1, x(b) - x(a) - 2)} height={56} rx={3} fill={PHASE_FILL[ph]} />
              })}
            </g>
          )
        })}
        {[0, 2, 4, 6, 8].map((m) => (
          <text key={m} x={x(FROM + m * 60)} y={182} fontSize={16} fill="#7d8079" textAnchor="middle">{`${15 + m} мин`}</text>
        ))}
      </svg>
      <div className="mt-5 flex gap-9 pl-[260px] text-[19px] text-paint-dim">
        {r.phases.map((p, i) => (
          <span key={p} className="flex items-center gap-3">
            <span className="inline-block h-[14px] w-[28px] rounded-[3px]" style={{ background: PHASE_FILL[i] }} />{p}
          </span>
        ))}
      </div>
    </div>
  )
}
