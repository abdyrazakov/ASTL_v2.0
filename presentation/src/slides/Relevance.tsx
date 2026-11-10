import { Column, Heading, Lead, Step } from '../components/deck'

// Цвет полосы — не украшение: красный — проблема, жёлтый — барьер, зелёный — возможность,
// голубой — то, что отличает наше решение.
const items = [
  {
    color: '#e5484d',
    label: 'проблема',
    title: 'Фиксированный цикл тратит время',
    text: 'Зелёный горит пустым полосам, пока на соседних подходах растёт очередь.',
  },
  {
    color: '#f59e0b',
    label: 'барьер',
    title: 'Промышленные системы дороги и закрыты',
    text: 'SCOOT и SCATS требуют петель в асфальте и остаются коммерческими продуктами.',
  },
  {
    color: '#2fbf71',
    label: 'возможность',
    title: 'Камеры уже есть',
    text: 'Обычная камера и нейросеть на процессоре дают дешёвый вход без работ на дороге.',
  },
  {
    color: '#6fa3c4',
    label: 'проверка',
    title: 'Решения нужно доказывать',
    text: 'Свой симулятор позволяет сравнить режимы на одном трафике и проверить безопасность.',
  },
]

export function Relevance() {
  return (
    <Column width={1360}>
      <Heading>Актуальность</Heading>
      <Lead>Почему задача важна сейчас — и почему её стоит решать открыто.</Lead>
      <div className="mt-14 grid grid-cols-2 gap-x-16 gap-y-10">
        {items.map((item, i) => (
          <Step key={item.title} at={i + 1}>
            <div className="border-l-[5px] pl-7" style={{ borderColor: item.color }}>
              <div className="text-[17px] tracking-[0.18em] text-paint-dim uppercase">{item.label}</div>
              <div className="mt-2 text-[30px] leading-tight font-bold">{item.title}</div>
              <div className="mt-2 text-[21px] leading-[1.45] text-paint-dim">{item.text}</div>
            </div>
          </Step>
        ))}
      </div>
    </Column>
  )
}
