import { useEffect, useMemo, useRef, useState } from 'react'
import { Arrow, Circle, Group, Image as KonvaImage, Layer, Line, Rect, Stage, Text } from 'react-konva'
import type Konva from 'konva'
import type { Lane, Point } from '../../api/types'
import { useImage } from '../../hooks/useImage'
import { pointInPolygon } from '../../lib/laneFactory'

export type Tool = 'select' | 'draw_observation' | 'draw_queue' | 'draw_line'
export type GeomField = 'observation' | 'queue' | 'line_p1' | 'line_p2' | 'line_dir'

export interface LayerVisibility {
  lanes: boolean
  queueZones: boolean
  lines: boolean
}

interface DraftLaneVisual {
  color: string
  observation: Point[]
  queue: Point[]
  linePoints: Point[] // 0, 1 или 2 точки в процессе набора (p1, p2)
  dirPoint: Point | null
}

interface Props {
  frameUrl: string | null
  videoW: number
  videoH: number
  lanes: Lane[]
  selectedLaneId: string | null
  tool: Tool
  draft: DraftLaneVisual | null
  visibility: LayerVisibility
  onStageClick: (p: Point) => void
  onSelectLane: (id: string | null) => void
  onUpdatePoint: (laneId: string, field: GeomField, index: number | null, p: Point) => void
  onInsertVertex: (laneId: string, field: 'observation' | 'queue', index: number, p: Point) => void
  onDeleteVertex: (laneId: string, field: 'observation' | 'queue', index: number) => void
}

function nearestEdgeIndex(points: Point[], p: Point): number {
  let best = 0
  let bestDist = Infinity
  for (let i = 0; i < points.length; i++) {
    const a = points[i]
    const b = points[(i + 1) % points.length]
    const dx = b.x - a.x, dy = b.y - a.y
    const len2 = dx * dx + dy * dy || 1e-12
    let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2
    t = Math.max(0, Math.min(1, t))
    const projX = a.x + t * dx, projY = a.y + t * dy
    const dist = (p.x - projX) ** 2 + (p.y - projY) ** 2
    if (dist < bestDist) { bestDist = dist; best = i + 1 }
  }
  return best
}

function toPx(points: Point[], w: number, h: number): number[] {
  const out: number[] = []
  for (const p of points) {
    out.push(p.x * w, p.y * h)
  }
  return out
}

export function EditorCanvas({
  frameUrl,
  videoW,
  videoH,
  lanes,
  selectedLaneId,
  tool,
  draft,
  visibility,
  onStageClick,
  onSelectLane,
  onUpdatePoint,
  onInsertVertex,
  onDeleteVertex,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<Konva.Stage>(null)
  const [containerSize, setContainerSize] = useState({ w: 800, h: 500 })
  const [image] = useImage(frameUrl)
  const [zoom, setZoom] = useState(1)
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 })

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0]
      setContainerSize({ w: entry.contentRect.width, h: entry.contentRect.height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const fitScale = useMemo(() => {
    if (!videoW || !videoH) return 1
    return Math.min(containerSize.w / videoW, containerSize.h / videoH) || 1
  }, [containerSize, videoW, videoH])

  // При смене кадра/видео — вернуть камеру редактора в исходное положение (fit).
  useEffect(() => {
    setZoom(1)
    setStagePos({
      x: (containerSize.w - videoW * fitScale) / 2,
      y: (containerSize.h - videoH * fitScale) / 2,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frameUrl, videoW, videoH])

  useEffect(() => {
    setStagePos((pos) => {
      // Держим картинку по центру, если позиция ещё не задана пользователем
      if (pos.x === 0 && pos.y === 0) {
        return {
          x: (containerSize.w - videoW * fitScale) / 2,
          y: (containerSize.h - videoH * fitScale) / 2,
        }
      }
      return pos
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitScale])

  const scale = fitScale * zoom

  function handleWheel(e: Konva.KonvaEventObject<WheelEvent>) {
    e.evt.preventDefault()
    const stage = stageRef.current
    if (!stage) return
    const oldScale = scale
    const pointer = stage.getPointerPosition()
    if (!pointer) return
    const mousePointTo = {
      x: (pointer.x - stagePos.x) / oldScale,
      y: (pointer.y - stagePos.y) / oldScale,
    }
    const direction = e.evt.deltaY > 0 ? -1 : 1
    const newZoom = Math.min(6, Math.max(0.3, zoom * (direction > 0 ? 1.12 : 1 / 1.12)))
    const newScale = fitScale * newZoom
    setZoom(newZoom)
    setStagePos({
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale,
    })
  }

  function relPoint(stage: Konva.Stage): Point | null {
    const pos = stage.getPointerPosition()
    if (!pos) return null
    const x = (pos.x - stagePos.x) / scale / videoW
    const y = (pos.y - stagePos.y) / scale / videoH
    return { x, y }
  }

  function handleStageMouseDown(e: Konva.KonvaEventObject<MouseEvent>) {
    const stage = stageRef.current
    if (!stage) return
    if (tool !== 'select') {
      const p = relPoint(stage)
      if (p) onStageClick(p)
      return
    }
    // select-инструмент: клик по пустому месту (не по полосе) снимает выделение
    if (e.target === stage || e.target.name() !== 'lane-hit') {
      onSelectLane(null)
    }
  }

  const draggable = tool === 'select'

  return (
    <div ref={containerRef} className="relative w-full h-full overflow-hidden bg-[var(--surface-sunken)]">
      <Stage
        ref={stageRef}
        width={containerSize.w}
        height={containerSize.h}
        scaleX={scale}
        scaleY={scale}
        x={stagePos.x}
        y={stagePos.y}
        draggable={draggable}
        onDragEnd={(e) => {
          if (e.target === stageRef.current) setStagePos({ x: e.target.x(), y: e.target.y() })
        }}
        onWheel={handleWheel}
        onMouseDown={handleStageMouseDown}
      >
        <Layer>
          {image && <KonvaImage image={image} width={videoW} height={videoH} />}
          {!image && <Rect width={videoW || 400} height={videoH || 300} fill="#0b1012" />}
        </Layer>

        <Layer listening={tool === 'select'}>
          {lanes.map((lane) => {
            const selected = lane.id === selectedLaneId
            const obsPx = toPx(lane.observation_polygon.points, videoW, videoH)
            const queuePx = toPx(lane.queue_zone_polygon.points, videoW, videoH)
            const line = lane.count_line
            const p1 = { x: line.p1.x * videoW, y: line.p1.y * videoH }
            const p2 = { x: line.p2.x * videoW, y: line.p2.y * videoH }
            const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 }
            const dirPt = { x: line.positive_side_point.x * videoW, y: line.positive_side_point.y * videoH }
            const dirVec = { x: dirPt.x - mid.x, y: dirPt.y - mid.y }
            const dirLen = Math.hypot(dirVec.x, dirVec.y) || 1
            const arrowEnd = {
              x: mid.x + (dirVec.x / dirLen) * 34,
              y: mid.y + (dirVec.y / dirLen) * 34,
            }

            return (
              <Group key={lane.id}>
                {visibility.lanes && (
                  <Line
                    points={obsPx}
                    closed
                    fill={lane.color + '33'}
                    stroke={lane.color}
                    strokeWidth={selected ? 3 : 2}
                    name="lane-hit"
                    onClick={() => tool === 'select' && onSelectLane(lane.id)}
                    onTap={() => tool === 'select' && onSelectLane(lane.id)}
                    onDblClick={() => {
                      if (tool !== 'select' || !selected) return
                      const stage = stageRef.current
                      const pos = stage?.getRelativePointerPosition()
                      if (!pos) return
                      const p = { x: pos.x / videoW, y: pos.y / videoH }
                      const idx = nearestEdgeIndex(lane.observation_polygon.points, p)
                      onInsertVertex(lane.id, 'observation', idx, p)
                    }}
                    onMouseEnter={(e) => {
                      if (tool === 'select') e.target.getStage()!.container().style.cursor = 'pointer'
                    }}
                    onMouseLeave={(e) => {
                      e.target.getStage()!.container().style.cursor = 'default'
                    }}
                  />
                )}
                {visibility.queueZones && (
                  <Line
                    points={queuePx}
                    closed
                    fill={lane.color + '55'}
                    stroke={lane.color}
                    strokeWidth={1}
                    dash={[6, 4]}
                    listening={false}
                  />
                )}
                {visibility.lines && (
                  <>
                    <Line points={[p1.x, p1.y, p2.x, p2.y]} stroke={lane.color} strokeWidth={4} listening={false} />
                    <Arrow
                      points={[mid.x, mid.y, arrowEnd.x, arrowEnd.y]}
                      stroke={lane.color}
                      fill={lane.color}
                      strokeWidth={3}
                      pointerLength={9}
                      pointerWidth={9}
                      listening={false}
                    />
                  </>
                )}
                {visibility.lanes && (
                  <Text
                    x={obsPx[0]}
                    y={obsPx[1] - 20}
                    text={lane.name}
                    fill={lane.color}
                    fontSize={14 / scale < 20 ? 14 : 14}
                    fontStyle="600"
                    listening={false}
                  />
                )}

                {selected && (
                  <>
                    {lane.observation_polygon.points.map((pt, i) => (
                      <VertexHandle
                        key={`obs-${i}`}
                        x={pt.x * videoW}
                        y={pt.y * videoH}
                        color={lane.color}
                        scale={scale}
                        onDrag={(np) => onUpdatePoint(lane.id, 'observation', i, np)}
                        onDoubleClick={() => {
                          if (lane.observation_polygon.points.length > 3) onDeleteVertex(lane.id, 'observation', i)
                        }}
                        videoW={videoW}
                        videoH={videoH}
                      />
                    ))}
                    {lane.queue_zone_polygon.points.map((pt, i) => (
                      <VertexHandle
                        key={`q-${i}`}
                        x={pt.x * videoW}
                        y={pt.y * videoH}
                        color="#ffffff"
                        scale={scale}
                        small
                        onDrag={(np) => onUpdatePoint(lane.id, 'queue', i, np)}
                        onDoubleClick={() => {
                          if (lane.queue_zone_polygon.points.length > 3) onDeleteVertex(lane.id, 'queue', i)
                        }}
                        videoW={videoW}
                        videoH={videoH}
                      />
                    ))}
                    <VertexHandle
                      x={p1.x} y={p1.y} color="#fde047" scale={scale} square
                      onDrag={(np) => onUpdatePoint(lane.id, 'line_p1', null, np)}
                      videoW={videoW} videoH={videoH}
                    />
                    <VertexHandle
                      x={p2.x} y={p2.y} color="#fde047" scale={scale} square
                      onDrag={(np) => onUpdatePoint(lane.id, 'line_p2', null, np)}
                      videoW={videoW} videoH={videoH}
                    />
                    <VertexHandle
                      x={dirPt.x} y={dirPt.y} color="#fb923c" scale={scale} triangle
                      onDrag={(np) => onUpdatePoint(lane.id, 'line_dir', null, np)}
                      videoW={videoW} videoH={videoH}
                    />
                  </>
                )}
              </Group>
            )
          })}

          {draft && (
            <Group listening={false}>
              {draft.observation.length > 0 && (
                <Line
                  points={toPx(draft.observation, videoW, videoH)}
                  closed={draft.observation.length > 2}
                  fill={draft.color + '33'}
                  stroke={draft.color}
                  strokeWidth={2}
                  dash={[4, 4]}
                />
              )}
              {draft.queue.length > 0 && (
                <Line
                  points={toPx(draft.queue, videoW, videoH)}
                  closed={draft.queue.length > 2}
                  fill={draft.color + '55'}
                  stroke="#fff"
                  strokeWidth={1}
                  dash={[4, 4]}
                />
              )}
              {draft.linePoints.length > 0 &&
                draft.linePoints.map((p, i) => (
                  <Circle key={i} x={p.x * videoW} y={p.y * videoH} radius={5 / scale} fill="#fde047" />
                ))}
              {draft.linePoints.length === 2 && (
                <Line
                  points={[
                    draft.linePoints[0].x * videoW, draft.linePoints[0].y * videoH,
                    draft.linePoints[1].x * videoW, draft.linePoints[1].y * videoH,
                  ]}
                  stroke="#fde047"
                  strokeWidth={3}
                />
              )}
            </Group>
          )}
        </Layer>
      </Stage>
    </div>
  )
}

function VertexHandle({
  x, y, color, scale, videoW, videoH, onDrag, onDoubleClick, small, square, triangle,
}: {
  x: number; y: number; color: string; scale: number; videoW: number; videoH: number
  onDrag: (p: Point) => void; onDoubleClick?: () => void
  small?: boolean; square?: boolean; triangle?: boolean
}) {
  const r = (small ? 4 : 6) / Math.max(scale, 0.15)
  return (
    <Circle
      x={x}
      y={y}
      radius={r}
      fill={color}
      stroke="#0b1012"
      strokeWidth={1.5 / Math.max(scale, 0.15)}
      draggable
      onDragMove={(e) => {
        onDrag({ x: e.target.x() / videoW, y: e.target.y() / videoH })
      }}
      onDblClick={onDoubleClick}
      onDblTap={onDoubleClick}
      onMouseEnter={(e) => (e.target.getStage()!.container().style.cursor = 'grab')}
      onMouseLeave={(e) => (e.target.getStage()!.container().style.cursor = 'default')}
      opacity={square || triangle ? 0.95 : 1}
    />
  )
}

export function pointInLane(p: Point, lane: Lane): boolean {
  return pointInPolygon(p, lane.observation_polygon.points)
}
