import { Column, Heading, Step } from '../components/deck'

const steps = [
  ['Измерить', 'сколько машин стоит на каждой полосе и сколько они ждут'],
  ['Выбрать', 'фазу, которой зелёный сейчас нужнее всего'],
  ['Переключить', 'только через жёлтый и полностью красный — без исключений'],
]

export function Approach() {
  return (
    <Column width={600}>
      <Heading>Светофор, который считает машины</Heading>
      <ol className="mt-14 flex flex-col gap-9">
        {steps.map(([title, text], i) => (
          <Step key={title} at={i + 1}>
            <li className="grid grid-cols-[64px_1fr] items-baseline">
              <span className="text-[40px] font-extrabold text-lane-yellow">{i + 1}</span>
              <div>
                <div className="text-[34px] font-bold">{title}</div>
                <div className="mt-1 text-[22px] leading-[1.45] text-paint-dim">{text}</div>
              </div>
            </li>
          </Step>
        ))}
      </ol>
    </Column>
  )
}
