import { Column, Heading, Lead, Step } from '../components/deck'

// Задачи идут в том же порядке, что и работа над проектом: увидеть → смоделировать → управлять → доказать.
const tasks = [
  ['Видеть очередь', 'распознавать транспорт и оценивать очередь по видео: YOLO11n и ByteTrack'],
  ['Смоделировать перекрёсток', 'свой симулятор, автомат сигналов и проверка конфликтов'],
  ['Управлять по спросу', 'адаптивный контроллер продлевает зелёный фазе, которой он нужнее'],
  ['Доказать эффект', 'сравнить оба режима на одном трафике и показать результат в интерфейсе'],
]

export function Goals() {
  return (
    <Column width={1360}>
      <Heading>Цели и задачи</Heading>
      <Lead>
        Цель — снизить среднюю задержку транспорта на перекрёстке, управляя светофором
        по реальной очереди, а не по фиксированному расписанию.
      </Lead>
      <div className="mt-14 grid grid-cols-2 gap-x-16 gap-y-10">
        {tasks.map(([title, text], i) => (
          <Step key={title} at={i + 1}>
            <div className="grid grid-cols-[58px_1fr] items-baseline border-t border-paint/15 pt-6">
              <span className="text-[36px] font-extrabold text-lane-yellow">{String(i + 1).padStart(2, '0')}</span>
              <div>
                <div className="text-[30px] leading-tight font-bold">{title}</div>
                <div className="mt-2 text-[21px] leading-[1.45] text-paint-dim">{text}</div>
              </div>
            </div>
          </Step>
        ))}
      </div>
    </Column>
  )
}
