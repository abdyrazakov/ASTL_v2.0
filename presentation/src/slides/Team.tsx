import { useEffect, useState } from 'react'

// Плоская иллюстрация команды: две условные фигуры без черт лица, в палитре презентации.
// У каждого предмет по его части работы: ноутбук со светофором — симуляция, камера — зрение.

function Person({ cx, skin, top, topDark, pants, hair, prop }: {
  cx: number; skin: string; top: string; topDark: string; pants: string; hair: 'swept' | 'fringe'; prop: 'laptop' | 'camera'
}) {
  const arm = { fill: 'none', stroke: topDark, strokeWidth: 30, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  return (
    <g>
      <ellipse cx={cx} cy={652} rx={96} ry={12} fill="#000" opacity={0.28} />
      {/* ноги и обувь */}
      <rect x={cx - 46} y={400} width={40} height={222} rx={16} fill={pants} />
      <rect x={cx + 6} y={400} width={40} height={222} rx={16} fill={pants} />
      <rect x={cx - 54} y={610} width={52} height={24} rx={11} fill="#eceae2" />
      <rect x={cx + 2} y={610} width={52} height={24} rx={11} fill="#eceae2" />
      {/* шея и корпус */}
      <rect x={cx - 15} y={176} width={30} height={40} rx={10} fill={skin} />
      <path d={`M${cx - 78},252 Q${cx - 80},214 ${cx - 38},204 L${cx + 38},204 Q${cx + 80},214 ${cx + 78},252 L${cx + 70},432 Q${cx},446 ${cx - 70},432 Z`} fill={top} />
      <path d={`M${cx - 30},206 Q${cx},236 ${cx + 30},206`} fill="none" stroke={topDark} strokeWidth={6} strokeLinecap="round" />
      {prop === 'laptop' ? (
        <>
          <polyline points={`${cx - 70},238 ${cx - 86},330 ${cx - 54},366`} {...arm} />
          <polyline points={`${cx + 70},238 ${cx + 86},330 ${cx + 54},366`} {...arm} />
          {/* ноутбук: на экране — светофор */}
          <rect x={cx - 62} y={292} width={124} height={78} rx={7} fill="#1e2024" stroke="#8a8d91" strokeWidth={3} />
          <circle cx={cx - 26} cy={331} r={9} fill="#e5484d" opacity={0.35} />
          <circle cx={cx} cy={331} r={9} fill="#f59e0b" opacity={0.35} />
          <circle cx={cx + 26} cy={331} r={9} fill="#2fbf71" />
          <path d={`M${cx - 70},370 L${cx + 70},370 L${cx + 60},382 L${cx - 60},382 Z`} fill="#8a8d91" />
          <circle cx={cx - 54} cy={370} r={13} fill={skin} />
          <circle cx={cx + 54} cy={370} r={13} fill={skin} />
        </>
      ) : (
        <>
          <polyline points={`${cx + 70},238 ${cx + 86},330 ${cx + 80},416`} {...arm} />
          <circle cx={cx + 80} cy={424} r={14} fill={skin} />
          <polyline points={`${cx - 70},238 ${cx - 84},322 ${cx - 30},306`} {...arm} />
          {/* камера */}
          <rect x={cx - 44} y={278} width={58} height={40} rx={7} fill="#1e2024" stroke="#8a8d91" strokeWidth={3} />
          <circle cx={cx - 15} cy={298} r={12} fill="#2a2d31" stroke="#a9aba5" strokeWidth={3} />
          <circle cx={cx - 15} cy={298} r={4} fill="#2fbf71" />
          <circle cx={cx - 30} cy={312} r={13} fill={skin} />
        </>
      )}
      {/* голова */}
      <ellipse cx={cx} cy={142} rx={44} ry={50} fill={skin} />
      <ellipse cx={cx + 43} cy={148} rx={7} ry={11} fill={skin} />
      {hair === 'swept' ? (
        <path d={`M${cx - 47},146 Q${cx - 52},84 ${cx + 4},84 Q${cx + 54},86 ${cx + 46},140 Q${cx + 28},108 ${cx - 12},110 Q${cx - 34},114 ${cx - 47},146 Z`} fill="#1c1916" />
      ) : (
        <path d={`M${cx - 46},140 Q${cx - 48},86 ${cx},86 Q${cx + 50},86 ${cx + 46},136 Q${cx + 40},116 ${cx + 22},114 L${cx - 30},120 Q${cx - 42},124 ${cx - 46},140 Z`} fill="#24201c" />
      )}
    </g>
  )
}

const team = [
  {
    name: 'Абдисаламов Атамбек',
    group: 'студент группы ПИ-4-25, кафедра ПОКС',
    role: 'симуляция перекрёстка, автомат сигналов, адаптивный контроллер, интерфейс',
    color: '#e9b308',
  },
  {
    name: 'Абдыразаков Бекболсун',
    group: 'студент группы МИР-2-26, кафедра АИИиР',
    role: 'машинное зрение: распознавание машин и анализ очереди по видео',
    color: '#6fa3c4',
  },
]

const A = { skin: '#c9976f', top: '#e9b308', topDark: '#c49606', pants: '#1e2227' }
const B = { skin: '#b9845e', top: '#4b7a99', topDark: '#3d6681', pants: '#2e3238' }

/** Вариант 1: двое рядом с ноутбуком и камерой. */
function Classic() {
  return (
    <>
      <Person cx={190} {...A} hair="swept" prop="laptop" />
      <Person cx={410} {...B} hair="fringe" prop="camera" />
    </>
  )
}

/** Вариант 2: на пешеходном переходе, между ними — работающий светофор. */
function Crossing() {
  return (
    <>
      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
        <rect key={i} x={30 + i * 72} y={612} width={44} height={50} rx={3} fill="#eceae2" opacity={0.14} />
      ))}
      <rect x={292} y={196} width={16} height={460} rx={6} fill="#4a4d52" />
      <rect x={266} y={70} width={68} height={176} rx={18} fill="#1e2024" stroke="#4a4d52" strokeWidth={4} />
      <circle className="tl-red" cx={300} cy={106} r={20} fill="#e5484d" />
      <circle className="tl-yellow" cx={300} cy={158} r={20} fill="#f59e0b" />
      <circle className="tl-green" cx={300} cy={210} r={20} fill="#2fbf71" />
      <g transform="translate(-40 0)"><Person cx={170} {...A} hair="swept" prop="laptop" /></g>
      <g transform="translate(40 0)"><Person cx={430} {...B} hair="fringe" prop="camera" /></g>
    </>
  )
}

/** Сидящий человек со спины (для сцены за столом). */
function Back({ cx, top, topDark, hair }: { cx: number; top: string; topDark: string; hair: string }) {
  return (
    <g>
      <rect x={cx - 70} y={420} width={140} height={150} rx={22} fill="#1e2024" />
      <path d={`M${cx - 96},676 Q${cx - 96},470 ${cx - 50},452 L${cx + 50},452 Q${cx + 96},470 ${cx + 96},676 Z`} fill={top} />
      <path d={`M${cx - 30},458 Q${cx},500 ${cx + 30},458`} fill="none" stroke={topDark} strokeWidth={8} strokeLinecap="round" />
      <rect x={cx - 14} y={410} width={28} height={46} rx={10} fill={topDark} />
      <ellipse cx={cx} cy={388} rx={42} ry={47} fill={hair} />
    </g>
  )
}

/** Вариант 3: за работой — у одного на экране перекрёсток, у другого видео с рамками распознавания. */
function Desk() {
  return (
    <>
      {/* левый монитор: схема перекрёстка */}
      <rect x={40} y={150} width={250} height={170} rx={10} fill="#1e2024" stroke="#4a4d52" strokeWidth={4} />
      <rect x={52} y={226} width={226} height={22} fill="#393c41" />
      <rect x={154} y={162} width={22} height={146} fill="#393c41" />
      <line x1={52} y1={237} x2={278} y2={237} stroke="#e9b308" strokeWidth={1.5} />
      <line x1={165} y1={162} x2={165} y2={308} stroke="#e9b308" strokeWidth={1.5} />
      {[70, 88, 106, 124].map((x) => <rect key={x} x={x} y={240} width={12} height={6} rx={1.5} fill="#e4e2da" />)}
      {[180, 196].map((y) => <rect key={y} x={157} y={y} width={6} height={11} rx={1.5} fill="#e4e2da" />)}
      <circle className="tl-green" cx={150} cy={222} r={4} fill="#2fbf71" />
      <circle className="tl-red" cx={181} cy={252} r={4} fill="#e5484d" />
      {/* правый монитор: кадр с камеры и рамки детекций */}
      <rect x={310} y={150} width={250} height={170} rx={10} fill="#1b2a33" stroke="#4a4d52" strokeWidth={4} />
      <path d="M322 308 L420 168 L450 168 L548 308 Z" fill="#2c3a42" />
      <line x1={435} y1={176} x2={435} y2={306} stroke="#eceae2" strokeWidth={2} strokeDasharray="8 8" opacity={0.5} />
      {[[384, 262, 44, 28], [446, 222, 30, 20], [408, 198, 20, 14]].map(([x, y, w, h], i) => (
        <g key={i}>
          <rect x={x + 4} y={y + 4} width={w - 8} height={h - 8} rx={2} fill="#9aa1a8" />
          <rect x={x} y={y} width={w} height={h} fill="none" stroke="#2fbf71" strokeWidth={2} />
          <rect x={x} y={y - 7} width={Math.min(w, 22)} height={6} fill="#2fbf71" />
        </g>
      ))}
      <rect x={150} y={320} width={20} height={44} fill="#4a4d52" />
      <rect x={420} y={320} width={20} height={44} fill="#4a4d52" />
      {/* стол */}
      <rect x={10} y={362} width={580} height={22} rx={4} fill="#5b4a3b" />
      <rect x={30} y={384} width={14} height={276} fill="#4a3c30" />
      <rect x={556} y={384} width={14} height={276} fill="#4a3c30" />
      <Back cx={165} top={A.top} topDark={A.topDark} hair="#1c1916" />
      <Back cx={435} top={B.top} topDark={B.topDark} hair="#24201c" />
    </>
  )
}

const VARIANTS = [
  { id: 'classic', label: 'двое рядом с ноутбуком и камерой', Scene: Classic },
  { id: 'crossing', label: 'двое на пешеходном переходе у работающего светофора', Scene: Crossing },
  { id: 'desk', label: 'двое за столом у мониторов: перекрёсток и видео с распознаванием', Scene: Desk },
]

export function Team() {
  // shortcut: выбор варианта иллюстрации клавишей V — временно, пока не выбран финальный
  const [v, setV] = useState(0)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'v' || e.key === 'V' || e.key === 'м' || e.key === 'М') setV((x) => (x + 1) % VARIANTS.length)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const { label, Scene } = VARIANTS[v]
  return (
    <>
      <svg key={v} viewBox="0 0 600 680" width={600} height={680} className="enter absolute top-[90px] left-[90px]" role="img"
        aria-label={`Иллюстрация команды: ${label}`}>
        <Scene />
      </svg>
      <div className="absolute top-[150px] left-[790px] w-[690px]">
        <h2 className="text-[58px] leading-[1.04] font-extrabold tracking-[-0.022em]">Команда</h2>
        <div className="mt-12 flex flex-col gap-10">
          {team.map((m) => (
            <div key={m.name} className="border-l-[5px] pl-7" style={{ borderColor: m.color }}>
              <div className="text-[34px] leading-tight font-bold">{m.name}</div>
              <div className="mt-2 text-[22px] text-paint">{m.group}</div>
              <div className="mt-2 text-[21px] leading-[1.45] text-paint-dim">{m.role}</div>
            </div>
          ))}
        </div>
        <div className="mt-16 text-[30px] font-bold">Спасибо. Готовы ответить на вопросы</div>
      </div>
    </>
  )
}
