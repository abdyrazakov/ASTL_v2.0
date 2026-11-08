import { Column, Heading, Step, useStep } from '../components/deck'
import { GreenRhythm } from '../components/GreenRhythm'

export function Controller() {
  const step = useStep()
  return (
    <>
      <Column width={1200}><Heading>Зелёный длится столько, сколько нужно очереди</Heading></Column>
      <div className="absolute top-[330px] left-[120px]">
        <GreenRhythm show={step >= 1 ? ['fixed', 'adaptive'] : ['fixed']} />
      </div>
      <Step at={2} className="absolute bottom-[112px] left-[380px] w-[1000px]">
        <p className="text-[23px] leading-[1.45] text-paint">
          Адаптивный режим уступает зелёный, когда очередь разъехалась или поток иссяк, а машину, ждущую
          90 секунд, пропускает следующей. Восток в пике получает больше — без перенастройки вручную.
        </p>
      </Step>
    </>
  )
}
