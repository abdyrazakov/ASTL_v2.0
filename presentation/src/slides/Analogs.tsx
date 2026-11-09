import { Column, Heading, Step } from '../components/deck'

// Общеизвестные характеристики промышленных систем адаптивного управления — без цен и цифр,
// которые мы не измеряли сами.
const rows = [
  { name: 'SCOOT', where: 'Великобритания, с 1980-х', sense: 'индуктивные петли в асфальте', open: 'закрытая, коммерческая', check: 'годы работы во многих городах' },
  { name: 'SCATS', where: 'Австралия, с 1970-х', sense: 'петли у стоп-линий', open: 'закрытая, коммерческая', check: 'годы работы во многих городах' },
  { name: 'SURTRAC', where: 'США, Университет Карнеги — Меллона', sense: 'камеры и радары', open: 'закрытая, коммерческая', check: 'пилотные районы' },
]

export function Analogs() {
  return (
    <>
      <Column width={1300}><Heading>Чем ASTL отличается от промышленных систем</Heading></Column>
      <div className="absolute top-[276px] right-[120px] left-[120px]">
        <div className="grid grid-cols-[220px_1fr_1fr_1fr] gap-x-10 border-b border-paint/15 pb-4 text-[19px] text-paint-dim">
          <span>Система</span><span>Чем видит машины</span><span>Код</span><span>Как проверена</span>
        </div>
        {rows.map((r) => (
          <div key={r.name} className="grid grid-cols-[220px_1fr_1fr_1fr] gap-x-10 border-b border-paint/10 py-4 text-[21px] leading-[1.35]">
            <div><div className="font-bold">{r.name}</div><div className="mt-1 text-[17px] text-paint-dim">{r.where}</div></div>
            <span className="text-paint-dim">{r.sense}</span>
            <span className="text-paint-dim">{r.open}</span>
            <span className="text-paint-dim">{r.check}</span>
          </div>
        ))}
        <Step at={1}>
          <div className="grid grid-cols-[220px_1fr_1fr_1fr] gap-x-10 py-4 text-[21px] leading-[1.35]">
            <div><div className="font-bold text-go">ASTL</div><div className="mt-1 text-[17px] text-paint-dim">наш проект</div></div>
            <span>обычная камера и нейросеть на процессоре — без работ в асфальте</span>
            <span>открытый, правила объяснены и доступны для проверки</span>
            <span>свой симулятор: оба режима на одном трафике, 634 теста безопасности</span>
          </div>
          <p className="mt-2 max-w-[1200px] text-[20px] leading-[1.5] text-paint-dim">
            Промышленные системы проверены годами на тысячах перекрёстков — ASTL пока учебный прототип.
            Наша сила в другом: дешёвый вход, прозрачная логика и проверяемость каждой цифры.
          </p>
        </Step>
      </div>
    </>
  )
}
