import { Column, Heading } from '../components/deck'

const stations = [
  ['Источник', 'видео с камеры (YOLO11n + ByteTrack) или симулятор'],
  ['Аналитика полос', 'один формат снимка для видео и модели'],
  ['Контроллер фаз', 'фиксированный или адаптивный — только предлагает решение'],
  ['Автомат сигналов', 'тайминги и проверка конфликтов перед каждой сменой'],
  ['Интерфейс и экспорт', 'схема, графики, JSON, JSONL, CSV'],
]

const stack = [
  ['Сервер', 'Python 3.11, FastAPI, Pydantic'],
  ['Зрение', 'Ultralytics YOLO11n, ByteTrack, OpenCV'],
  ['Модель', 'свой дискретный симулятор, шаг 0,1 с'],
  ['Интерфейс', 'React 19, TypeScript, SVG, Recharts'],
  ['Проверка', '634 автотеста, работает офлайн на CPU'],
]

export function Architecture() {
  return (
    <>
      <Column width={1100}><Heading>Один конвейер для видео и модели</Heading></Column>
      <div className="absolute top-[300px] left-[120px] w-[720px]">
        {stations.map(([name, text], i) => (
          <div key={name} className="relative grid grid-cols-[48px_1fr] pb-9 last:pb-0">
            {i < stations.length - 1 && <div className="absolute top-[30px] bottom-0 left-[11px] w-[3px] bg-lane-yellow/60" />}
            <div className={`mt-[6px] h-[25px] w-[25px] rounded-full ${i === 3 ? 'bg-go shadow-[0_0_22px_#2fbf71]' : 'bg-paint'}`} />
            <div>
              <div className="text-[28px] font-bold">{name}</div>
              <div className="mt-1 text-[20px] leading-[1.45] text-paint-dim">{text}</div>
            </div>
          </div>
        ))}
      </div>
      <dl className="absolute top-[300px] right-[120px] grid w-[560px] grid-cols-[150px_1fr] gap-x-6 gap-y-6 text-[21px] leading-[1.4]">
        {stack.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-paint-dim">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </>
  )
}
