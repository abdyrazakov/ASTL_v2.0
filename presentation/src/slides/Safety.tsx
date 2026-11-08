import { Column, Heading, Step, useStep } from '../components/deck'
import { TimingDiagram } from '../components/TimingDiagram'
import { useReplay } from '../data/replay'

const PAIR: [string, string] = ['n_t', 'e_t']

export function Safety() {
  const r = useReplay()
  const step = useStep()
  const names = PAIR.map((g) => r.groupNames[r.groups.indexOf(g)].split(':')[0])
  return (
    <>
      <Column width={1300}><Heading>Конфликтующие потоки никогда не получают зелёный вместе</Heading></Column>
      <div className="absolute top-[300px] left-[120px]">
        <TimingDiagram pair={PAIR} highlight={step >= 1} />
      </div>
      <Step at={1} className="absolute bottom-[112px] left-[380px] w-[1000px]">
        <p className="text-[23px] leading-[1.45] text-paint">
          {names[0]} прямо и {names[1]} прямо пересекаются. За эти три минуты их зелёные не совпали ни разу —
          и на 150 случайных перекрёстках с хаотичным контроллером тоже.
        </p>
      </Step>
    </>
  )
}
