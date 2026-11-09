import { useMemo } from 'react'
import type { IntersectionProfile, Movement, Scene, SignalColor } from '../../api/simTypes'
import {
  C, CLASS_COLORS, HEADING_LABEL, LANE_W, MOVEMENT_GLYPH, PALETTE, SIGNAL_COLORS, VIEW,
  angleDeg, armSides, bezier, computeLayout, laneFrame, pointOnLane, travelDir, turnPath,
} from '../../lib/intersectionGeometry'

/**
 * Схема перекрёстка сверху. В режиме симуляции (передан `scene`) стоп-линии
 * окрашены по текущему сигналу своей группы, машины — по классу (красная
 * обводка — стоит в очереди). В редакторе (без `scene`) стоп-линии окрашены
 * цветом сигнальной группы, выбранные полосы подсвечены.
 */
export function IntersectionScene({
  profile, scene, highlightLaneIds, highlightGroupIds, selectedLaneId, onLaneClick,
}: {
  profile: IntersectionProfile
  scene?: Scene | null
  highlightLaneIds?: Set<string>
  highlightGroupIds?: Set<string>
  selectedLaneId?: string | null
  onLaneClick?: (laneId: string) => void
}) {
  const L = useMemo(() => computeLayout(profile), [profile])
  const movementGroup = useMemo(() => {
    const m = new Map<string, string>()
    for (const g of profile.signal_groups) for (const lm of g.movements) m.set(`${lm.lane_id}|${lm.movement}`, g.id)
    return m
  }, [profile])
  const groupColor = useMemo(() => {
    const m = new Map<string, string>()
    profile.signal_groups.forEach((g, i) => m.set(g.id, PALETTE[i % PALETTE.length]))
    return m
  }, [profile])
  const laneById = useMemo(() => new Map(profile.lanes.map((l) => [l.id, l])), [profile])

  const roadW = L.lanesPerSide * LANE_W
  const live = !!scene

  return (
    <svg viewBox={`0 0 ${VIEW} ${VIEW}`} className="w-full h-full select-none" role="img"
      aria-label="Схема перекрёстка">
      <rect x={0} y={0} width={VIEW} height={VIEW} fill="var(--surface-sunken)" />

      {/* дороги: входящие полосы справа от осевой, выезды — слева */}
      {armSides(profile).map((side) => {
        const d = travelDir(side)
        const vertical = d.x === 0
        const len = C - L.half
        const x = vertical ? C - roadW : d.x > 0 ? 0 : C + L.half
        const y = vertical ? (d.y > 0 ? 0 : C + L.half) : C - roadW
        return (
          <g key={side}>
            <rect x={x} y={y} width={vertical ? roadW * 2 : len} height={vertical ? len : roadW * 2} fill="#1d272b" />
            {vertical
              ? <line x1={C} y1={y} x2={C} y2={y + len} stroke="#f5a623" strokeOpacity={0.55} strokeWidth={2} />
              : <line x1={x} y1={C} x2={x + len} y2={C} stroke="#f5a623" strokeOpacity={0.55} strokeWidth={2} />}
          </g>
        )
      })}
      <rect x={C - L.half} y={C - L.half} width={L.half * 2} height={L.half * 2} fill="#232f34" />

      {/* полосы */}
      {profile.lanes.map((lane) => {
        const f = laneFrame(profile, lane, L)
        const hl = highlightLaneIds?.has(lane.id)
        const sel = selectedLaneId === lane.id
        const nx = f.r.x * LANE_W * 0.5
        const ny = f.r.y * LANE_W * 0.5
        const poly = [
          `${f.start.x - nx},${f.start.y - ny}`, `${f.start.x + nx},${f.start.y + ny}`,
          `${f.stop.x + nx},${f.stop.y + ny}`, `${f.stop.x - nx},${f.stop.y - ny}`,
        ].join(' ')
        return (
          <g key={lane.id} onClick={onLaneClick ? () => onLaneClick(lane.id) : undefined}
            style={{ cursor: onLaneClick ? 'pointer' : undefined }}>
            <polygon points={poly}
              fill={hl || sel ? lane.color : '#28353a'}
              fillOpacity={hl || sel ? 0.28 : 1}
              stroke={sel ? lane.color : '#3a4a51'} strokeWidth={sel ? 2.5 : 1}
              strokeDasharray={sel ? undefined : '10 8'} />
            <LaneLabel profile={profile} laneId={lane.id} L={L} backlog={scene?.backlog[lane.id] ?? 0} />
          </g>
        )
      })}

      {/* стоп-линии (= сигнальные головы) и стрелки манёвров */}
      {profile.lanes.map((lane) => {
        const f = laneFrame(profile, lane, L)
        const groups: { gid: string | undefined; movs: Movement[] }[] = []
        for (const m of lane.movements) {
          const gid = movementGroup.get(`${lane.id}|${m}`)
          const ex = groups.find((g) => g.gid === gid)
          if (ex) ex.movs.push(m)
          else groups.push({ gid, movs: [m] })
        }
        const segW = LANE_W / groups.length
        return groups.map((g, i) => {
          const off = -LANE_W / 2 + segW * (i + 0.5)
          const cx = f.stop.x + f.r.x * off
          const cy = f.stop.y + f.r.y * off
          let color = '#5c6e74'
          if (live) color = g.gid ? SIGNAL_COLORS[(scene!.signals[g.gid] ?? 'red') as SignalColor] : '#5c6e74'
          else if (g.gid) color = groupColor.get(g.gid) ?? '#5c6e74'
          const dim = !live && highlightGroupIds && highlightGroupIds.size > 0 && !(g.gid && highlightGroupIds.has(g.gid))
          const ang = angleDeg(f.d) + 90
          const gx = cx - f.d.x * 16
          const gy = cy - f.d.y * 16
          return (
            <g key={`${lane.id}-${i}`} opacity={dim ? 0.25 : 1}>
              <rect x={cx - segW / 2 + 1} y={cy - 3.5} width={segW - 2} height={7} rx={2}
                fill={color} transform={`rotate(${angleDeg(f.r)} ${cx} ${cy})`} />
              <text x={gx} y={gy} fill="#e8edef" fillOpacity={0.75} fontSize={13} textAnchor="middle"
                dominantBaseline="central" transform={`rotate(${ang} ${gx} ${gy})`}>
                {g.movs.map((m) => MOVEMENT_GLYPH[m]).join('')}
              </text>
            </g>
          )
        })
      })}

      {/* машины */}
      {scene?.vehicles.map((v) => {
        const lane = laneById.get(v.lane_id)
        if (!lane) return null
        const { pos, dir } = v.crossed
          ? bezier(turnPath(profile, lane, L, v.movement), Math.min(1, Math.max(0, v.progress)))
          : pointOnLane(profile, lane, L, v.s)
        const len = Math.max(5, v.length * L.scale)
        const cx = pos.x - dir.x * len / 2
        const cy = pos.y - dir.y * len / 2
        const w = LANE_W * 0.58
        return (
          <rect key={v.id} x={cx - len / 2} y={cy - w / 2} width={len} height={w} rx={2}
            fill={CLASS_COLORS[v.cls] ?? '#dfe7ea'}
            stroke={v.state === 'waiting' ? '#ef4444' : '#0b1012'} strokeWidth={v.state === 'waiting' ? 2 : 1}
            transform={`rotate(${angleDeg(dir)} ${cx} ${cy})`} />
        )
      })}

      {/* подписи подходов */}
      {profile.approaches.map((a) => {
        const d = travelDir(a.heading)
        const x = C - d.x * (C - 40) - (d.y !== 0 ? roadW + 70 : 0)
        const y = C - d.y * (C - 24) - (d.x !== 0 ? roadW + 26 : 0)
        return (
          <text key={a.id} x={x} y={y} fill="var(--text-muted)" fontSize={20} textAnchor="middle"
            dominantBaseline="central">{a.name || HEADING_LABEL[a.heading]}</text>
        )
      })}
    </svg>
  )
}

function LaneLabel({ profile, laneId, L, backlog }: {
  profile: IntersectionProfile; laneId: string; L: ReturnType<typeof computeLayout>; backlog: number
}) {
  const lane = profile.lanes.find((l) => l.id === laneId)!
  const f = laneFrame(profile, lane, L)
  const x = f.start.x + f.d.x * 14
  const y = f.start.y + f.d.y * 14
  const vertical = f.d.x === 0
  return (
    <g>
      <text x={x} y={y} fill={lane.color} fontSize={12} textAnchor="middle" dominantBaseline="central"
        transform={vertical ? `rotate(-90 ${x} ${y})` : undefined}>
        {lane.name}
      </text>
      {backlog > 0 && (
        <text x={x + f.r.x * 34} y={y + f.r.y * 34} fill="#ef4444" fontSize={13} fontWeight={600}
          textAnchor="middle" dominantBaseline="central">+{backlog}</text>
      )}
    </g>
  )
}
