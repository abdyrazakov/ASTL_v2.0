import { Column, Heading, useStep } from '../components/deck'

// Средняя задержка на машину, с: 5 seed × 1 ч, одинаковый трафик (VERIFICATION_STAGE2.md, раздел 6.3).
// Процент взят из замера по неокруглённым средним.
const rows: [string, number, number, number][] = [
  ['С выделенными левыми', 62.5, 23.4, 62],
  ['T-образный', 20.2, 10.0, 51],
  ['Асимметричный, короткие подходы', 37.9, 19.1, 50],
  ['Магистраль и второстепенная', 25.5, 13.7, 46],
  ['Простой, 4 подхода', 12.4, 7.6, 39],
  ['4 подхода по 3 полосы', 30.7, 21.2, 31],
  ['T-образный, главная в 3 полосы', 16.1, 11.1, 31],
  ['3 полосы, расщеплённые фазы', 29.9, 21.5, 28],
  ['Бульвар со сдвоенными левыми', 37.6, 27.6, 27],
  ['Утро, вечер и ночь', 95.4, 71.7, 25],
  ['Две односторонние улицы', 16.1, 13.1, 19],
]
const SCALE_X = 0
const SCALE_W = 640
const MAX = 100

export function Results() {
  const moved = useStep() >= 1
  const px = (v: number) => SCALE_X + (v / MAX) * SCALE_W
  return (
    <>
      <Column width={1300}><Heading>Средняя задержка ниже на всех одиннадцати перекрёстках</Heading></Column>
      <div className="absolute top-[300px] right-[120px] left-[120px] text-[20px]">
        <div className="mb-4 grid grid-cols-[400px_640px_1fr] text-[17px] text-paint-dim">
          <span />
          <span className="flex justify-between"><span>0 с</span><span>50 с</span><span>100 с</span></span>
          <span className="text-right">фиксированный → адаптивный</span>
        </div>
        {rows.map(([name, f, a, pct], i) => (
          <div key={name} className="grid h-[42px] grid-cols-[400px_640px_1fr] items-center">
            <span className="text-paint">{name}</span>
            <div className="relative h-full">
              <div className="absolute top-1/2 h-[2px] -translate-y-1/2 bg-paint/25"
                style={{ left: px(moved ? a : f), width: moved ? px(f) - px(a) : 0, transition: `all .9s cubic-bezier(.65,0,.35,1) ${i * 45}ms` }} />
              <div className="absolute top-1/2 h-[14px] w-[14px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-paint-dim" style={{ left: px(f) }} />
              <div className="absolute top-1/2 h-[14px] w-[14px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-go shadow-[0_0_14px_#2fbf71]"
                style={{ left: px(moved ? a : f), opacity: moved ? 1 : 0, transition: `left .9s cubic-bezier(.65,0,.35,1) ${i * 45}ms, opacity .3s ${i * 45}ms` }} />
            </div>
            <span className="text-right text-paint-dim">
              {f.toFixed(1)} → <span className="text-paint">{a.toFixed(1)} с</span>
              <span className="ml-5 inline-block w-[64px] font-bold text-go" style={{ opacity: moved ? 1 : 0, transition: 'opacity .4s .5s' }}>−{pct}%</span>
            </span>
          </div>
        ))}
      </div>
    </>
  )
}
