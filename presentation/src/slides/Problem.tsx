import { Column, Heading, Lead, Step } from '../components/deck'
import { useLiveFrame } from '../data/replay'

export function Problem() {
  const f = useLiveFrame('fixed')
  return (
    <Column width={600}>
      <Heading>Фиксированный цикл не видит очередь</Heading>
      <Lead>
        Фаза горит заданное время, даже когда её полоса пуста, — а на соседнем подходе тем временем стоят машины.
      </Lead>
      <Step at={1} className="mt-16">
        <div className="text-[120px] leading-none font-extrabold tracking-[-0.03em] text-stop">{f.q}</div>
        <p className="mt-4 max-w-[480px] text-[22px] leading-[1.45] text-paint-dim">
          машин стоят с горящими стоп-сигналами прямо сейчас — запись фиксированного режима в час пик
        </p>
      </Step>
    </Column>
  )
}
