import { Column, Heading } from '../components/deck'

// Состояние этапа показано сигналом: зелёный — готово, жёлтый — начат, красный — впереди
const stages = [
  { lamp: '#2fbf71', state: 'готово', title: 'Машинное зрение', text: 'очередь и ожидание по полосам из видео' },
  { lamp: '#2fbf71', state: 'готово', title: 'Симуляция', text: 'автомат сигналов и адаптивный контроллер' },
  { lamp: '#e5484d', state: 'впереди', title: 'Зелёная волна', text: 'согласование нескольких перекрёстков' },
  { lamp: '#f59e0b', state: 'начат', title: 'Макет', text: 'Raspberry Pi уже есть, светодиоды через GPIO' },
]

export function Stages() {
  return (
    <>
      <Column width={900}><Heading>Четыре этапа, два готовы</Heading></Column>
      <div className="absolute top-[420px] right-[120px] left-[120px]">
        <div className="absolute top-[22px] right-0 left-0 h-[3px]"
          style={{ backgroundImage: 'repeating-linear-gradient(90deg, rgba(236,234,226,.45) 0 26px, transparent 26px 50px)' }} />
        <div className="relative grid grid-cols-4 gap-10">
          {stages.map((s) => (
            <div key={s.title}>
              <div className="h-[48px] w-[48px] rounded-full border-[6px] border-asphalt-deep"
                style={{ background: s.lamp, boxShadow: `0 0 28px ${s.lamp}` }} />
              <div className="mt-8 text-[20px] text-paint-dim">{s.state}</div>
              <div className="mt-1 text-[34px] leading-[1.15] font-bold">{s.title}</div>
              <div className="mt-3 text-[21px] leading-[1.45] text-paint-dim">{s.text}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
