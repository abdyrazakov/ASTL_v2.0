import { Column, Heading, Step } from '../components/deck'

const points = [
  ['Фиксированный цикл проигрывает', 'адаптивный режим снизил среднюю задержку на всех 11 типах перекрёстков — от 19 до 62%.'],
  ['Безопасность не зависит от алгоритма', 'конфликтующие потоки не получают зелёный одновременно: 634 теста, ноль нарушений.'],
  ['Решение доступно и проверяемо', 'обычная камера, нейросеть на CPU, открытый код и работа офлайн.'],
]

export function Conclusion() {
  return (
    <>
      <Column width={940}>
        <Heading>Заключение</Heading>
        <ol className="mt-12 flex flex-col gap-6">
          {points.map(([title, text], i) => (
            <li key={title} className="grid grid-cols-[44px_1fr] gap-5">
              <span className="text-[26px] font-extrabold text-lane-yellow">{String(i + 1).padStart(2, '0')}</span>
              <div>
                <div className="text-[28px] leading-tight font-bold">{title}</div>
                <div className="mt-1 text-[21px] leading-[1.45] text-paint-dim">{text}</div>
              </div>
            </li>
          ))}
        </ol>
        <Step at={1} className="mt-10">
          <div className="border-t border-paint/15 pt-6 text-[22px] leading-[1.45]">
            <span className="text-paint-dim">Дальше — </span>
            зелёная волна и макет на Raspberry Pi: тот же автомат сигналов зажжёт настоящие светодиоды.
          </div>
        </Step>
      </Column>

      <div className="absolute top-[300px] right-[120px] w-[340px] border-l-[5px] border-lane-yellow pl-8">
        <div className="text-[15px] tracking-[0.18em] text-paint-dim uppercase">Средняя задержка</div>
        <div className="mt-2 text-[80px] leading-none font-extrabold tracking-[-0.04em] whitespace-nowrap text-go">19–62%</div>
        <div className="mt-4 text-[21px] leading-[1.45] text-paint-dim">
          ниже на всех 11 типах перекрёстков: 5 seed, 1 час модельного времени
        </div>
        <div className="mt-8 grid grid-cols-2 gap-4">
          <div className="border-t border-paint/15 pt-4">
            <div className="text-[40px] leading-none font-extrabold">634</div>
            <div className="mt-1 text-[16px] text-paint-dim">автотеста</div>
          </div>
          <div className="border-t border-paint/15 pt-4">
            <div className="text-[40px] leading-none font-extrabold">0</div>
            <div className="mt-1 text-[16px] text-paint-dim">конфликтов</div>
          </div>
        </div>
      </div>

      <div className="absolute bottom-[112px] left-[120px] text-[23px] text-paint">
        Спасибо за внимание. Готовы ответить на вопросы.
      </div>
    </>
  )
}
