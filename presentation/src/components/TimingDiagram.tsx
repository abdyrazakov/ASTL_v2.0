import { useEffect, useMemo, useRef } from 'react'
import { replayTime, useReplay } from '../data/replay'

const FILL: Record<string, string> = { G: '#2fbf71', Y: '#f59e0b' }
const W = 1360
const LABEL = 260
const ROW = 30
const GAP = 12

/**
 * Диаграмма цикла светофора по записи адаптивного прогона: строка — сигнальная группа,
 * ось — время; зелёный и жёлтый — полосы, красный — пустая дорожка. В режиме highlight
 * выделена пара конфликтующих групп: их зелёные не пересекаются ни разу.
 */
export function TimingDiagram({ pair, highlight }: { pair: [string, string]; highlight: boolean }) {
  const r = useReplay()
  const frames = r.runs.adaptive.frames
  const dur = (frames.length - 1) * r.frameDt
  const x = (t: number) => LABEL + (t / dur) * (W - LABEL)
  const head = useRef<SVGLineElement>(null)

  const rows = useMemo(() => r.groups.map((_, gi) => {
    const segs: { c: string; a: number; b: number }[] = []
    let c = frames[0].sig[gi], a = 0
    frames.forEach((f, i) => {
      if (f.sig[gi] !== c || i === frames.length - 1) {
        segs.push({ c, a: a * r.frameDt, b: i * r.frameDt })
        c = f.sig[gi]; a = i
      }
    })
    return segs.filter((s) => s.c !== 'R')
  }), [r, frames])

  useEffect(() => {
    let raf = 0
    const tick = () => {
      head.current?.setAttribute('x1', String(x(replayTime(r))))
      head.current?.setAttribute('x2', String(x(replayTime(r))))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  })

  const H = r.groups.length * (ROW + GAP) + 40
  const ticks = Array.from({ length: Math.floor(dur / 30) + 1 }, (_, i) => i * 30).filter((t) => t < dur - 10)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img"
      aria-label="Диаграмма цикла: зелёные и жёлтые интервалы каждой сигнальной группы за три минуты">
      {r.groups.map((g, gi) => {
        const y = gi * (ROW + GAP)
        const dim = highlight && !pair.includes(g)
        return (
          <g key={g} opacity={dim ? 0.2 : 1} style={{ transition: 'opacity .5s ease' }}>
            <text x={0} y={y + ROW / 2} dominantBaseline="central" fontSize={20}
              fill={highlight && pair.includes(g) ? '#eceae2' : '#a9aba5'}>{r.groupNames[gi]}</text>
            <rect x={LABEL} y={y + ROW / 2 - 1} width={W - LABEL} height={2} fill="#4a4d52" />
            {rows[gi].map((s, i) => (
              <rect key={i} x={x(s.a)} y={y} width={Math.max(1, x(s.b) - x(s.a))} height={ROW} rx={3} fill={FILL[s.c]} />
            ))}
          </g>
        )
      })}
      {ticks.map((t) => (
        <text key={t} x={x(t)} y={H - 8} fontSize={16} fill="#7d8079" textAnchor="middle">
          {`${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`}
        </text>
      ))}
      <line ref={head} y1={-4} y2={H - 30} stroke="#eceae2" strokeWidth={1.5} opacity={0.7} />
    </svg>
  )
}
