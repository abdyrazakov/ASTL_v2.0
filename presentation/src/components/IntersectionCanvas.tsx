import { useEffect, useRef } from 'react'
import type { Movement } from '../../../frontend/src/api/simTypes'
import {
  C, LANE_W, armSides, bezier, computeLayout, laneFrame, pointOnLane, travelDir, turnPath,
} from '../../../frontend/src/lib/intersectionGeometry'
import { type Mode, type Replay, replayTime } from '../data/replay'

const MOVES: Movement[] = ['straight', 'left', 'right']
const LENGTH_M = [4.5, 12, 10, 2.2] // car, bus, truck, motorcycle — как в engine.VEHICLE_SPECS
const BODY = ['#e4e2da', '#d9a40a', '#9aa1a8', '#e4e2da']
const LAMP: Record<string, string> = { G: '#2fbf71', Y: '#f59e0b', R: '#e5484d' }

/**
 * Перекрёсток сверху, проигрывающий настоящую запись симуляции. Дорога рисуется один
 * раз во внеэкранный холст, на каждом кадре — только сигналы и машины (позиции
 * интерполируются между кадрами записи по id машины).
 */
export function IntersectionCanvas({ replay, mode, label }: { replay: Replay; mode: Mode; label: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return
    const p = replay.profile
    const L = computeLayout(p)
    const lanes = replay.lanes.map((id) => p.lanes.find((l) => l.id === id)!)
    const groupIdx = new Map(replay.groups.map((g, i) => [g, i]))
    const lampGroups = lanes.map((lane) => {
      const seen: number[] = []
      for (const m of lane.movements) {
        const g = p.signal_groups.find((sg) => sg.movements.some((lm) => lm.lane_id === lane.id && lm.movement === m))
        const gi = g ? groupIdx.get(g.id)! : -1
        if (gi >= 0 && !seen.includes(gi)) seen.push(gi)
      }
      return seen
    })
    const frames = replay.runs[mode].frames
    const road = document.createElement('canvas')
    let raf = 0

    const paintRoad = (px: number) => {
      road.width = road.height = px
      const g = road.getContext('2d')!
      g.setTransform(px / 1000, 0, 0, px / 1000, 0, 0)
      const roadW = L.lanesPerSide * LANE_W
      const sides = armSides(p)
      g.fillStyle = '#393c41'
      for (const h of sides) {
        const d = travelDir(h)
        const vertical = d.x === 0
        const len = C - L.half
        const x = vertical ? C - roadW : d.x > 0 ? 0 : C + L.half
        const y = vertical ? (d.y > 0 ? 0 : C + L.half) : C - roadW
        g.fillRect(x, y, vertical ? roadW * 2 : len, vertical ? len : roadW * 2)
      }
      g.fillRect(C - L.half, C - L.half, L.half * 2, L.half * 2)

      for (const h of sides) {
        const d = travelDir(h)
        const r = { x: -d.y, y: d.x }
        const edge = { x: C - d.x * L.half, y: C - d.y * L.half }
        const far = { x: C - d.x * C, y: C - d.y * C }
        const line = (off: number) => {
          g.beginPath()
          g.moveTo(far.x + r.x * off, far.y + r.y * off)
          g.lineTo(edge.x + r.x * off, edge.y + r.y * off)
          g.stroke()
        }
        // двойная сплошная по оси
        g.strokeStyle = '#e9b308'; g.lineWidth = 2; g.setLineDash([])
        line(-2.5); line(2.5)
        // прерывистые линии между полосами
        g.strokeStyle = 'rgba(236,234,226,.42)'; g.lineWidth = 2; g.setLineDash([16, 18])
        for (let i = 1; i < L.lanesPerSide; i++) { line(i * LANE_W); line(-i * LANE_W) }
        // кромка
        g.setLineDash([]); g.strokeStyle = 'rgba(236,234,226,.55)'
        line(roadW - 2); line(-roadW + 2)
        // пешеходный переход внутри квадрата перекрёстка
        g.fillStyle = 'rgba(236,234,226,.16)'
        for (let o = -roadW + 6; o < roadW - 4; o += 14) {
          const cx = C - d.x * (L.half - 14) + r.x * o
          const cy = C - d.y * (L.half - 14) + r.y * o
          g.save(); g.translate(cx, cy); g.rotate(Math.atan2(d.y, d.x))
          g.fillRect(-9, -3.5, 18, 7); g.restore()
        }
      }
      // стоп-линии входящих полос
      g.strokeStyle = '#eceae2'; g.lineWidth = 5; g.setLineDash([])
      for (const lane of lanes) {
        const f = laneFrame(p, lane, L)
        const a = { x: f.stop.x - f.r.x * LANE_W / 2 - f.d.x * 4, y: f.stop.y - f.r.y * LANE_W / 2 - f.d.y * 4 }
        g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(a.x + f.r.x * LANE_W, a.y + f.r.y * LANE_W); g.stroke()
      }
    }

    const fit = () => {
      const px = Math.round(cv.clientWidth * Math.min(2, window.devicePixelRatio || 1))
      if (px <= 0) return
      if (cv.width !== px) cv.width = cv.height = px
      // проверяем именно слой дороги: в dev (StrictMode) эффект запускается дважды,
      // холст уже нужного размера, а новый слой дороги ещё пуст
      if (road.width !== px) paintRoad(px)
    }
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(cv)

    const draw = () => {
      raf = requestAnimationFrame(draw)
      const k = cv.width / 1000
      if (!k) return
      const t = replayTime(replay)
      const fi = Math.min(frames.length - 2, Math.floor(t / replay.frameDt))
      const u = t / replay.frameDt - fi
      const a = frames[fi]
      const next = new Map(frames[fi + 1].v.map((v) => [v[0], v]))

      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.clearRect(0, 0, cv.width, cv.height)
      ctx.drawImage(road, 0, 0)
      ctx.setTransform(k, 0, 0, k, 0, 0)

      // сигналы: огонь на стоп-линии каждой полосы, по группе манёвра
      lanes.forEach((lane, li) => {
        const f = laneFrame(p, lane, L)
        const gs = lampGroups[li]
        gs.forEach((gi, j) => {
          const off = -LANE_W / 2 + (LANE_W / gs.length) * (j + 0.5)
          const x = f.stop.x + f.r.x * off + f.d.x * 7
          const y = f.stop.y + f.r.y * off + f.d.y * 7
          const col = LAMP[a.sig[gi]]
          ctx.shadowColor = col; ctx.shadowBlur = 14; ctx.fillStyle = col
          ctx.beginPath(); ctx.arc(x, y, 4.2, 0, Math.PI * 2); ctx.fill()
        })
      })
      ctx.shadowBlur = 0

      for (const v of a.v) {
        const [id, li, s10, pr, mi, cls, waiting] = v
        const b = next.get(id)
        const lane = lanes[li]
        let pos, dir
        if (pr >= 0) {
          const pb = b && b[3] >= 0 ? b[3] : pr
          ;({ pos, dir } = bezier(turnPath(p, lane, L, MOVES[mi]), Math.min(1, (pr + (pb - pr) * u) / 100)))
        } else {
          const sb = b && b[3] < 0 ? b[2] : s10
          ;({ pos, dir } = pointOnLane(p, lane, L, (s10 + (sb - s10) * u) / 10))
        }
        const len = Math.max(6, LENGTH_M[cls] * L.scale)
        const w = LANE_W * (cls === 3 ? 0.32 : 0.56)
        ctx.save()
        ctx.translate(pos.x - dir.x * len / 2, pos.y - dir.y * len / 2)
        ctx.rotate(Math.atan2(dir.y, dir.x))
        ctx.fillStyle = BODY[cls]
        ctx.beginPath(); ctx.roundRect(-len / 2, -w / 2, len, w, 2.5); ctx.fill()
        if (waiting) {
          // стоит в очереди — горят стоп-сигналы
          ctx.fillStyle = '#ff4d4f'; ctx.shadowColor = '#ff4d4f'; ctx.shadowBlur = 8
          ctx.fillRect(-len / 2, -w / 2 + 0.6, 1.8, 2.6)
          ctx.fillRect(-len / 2, w / 2 - 3.2, 1.8, 2.6)
          ctx.shadowBlur = 0
        }
        ctx.restore()
      }
    }
    raf = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(raf); ro.disconnect() }
  }, [replay, mode])

  return <canvas ref={ref} className="block h-full w-full" role="img" aria-label={label} />
}
