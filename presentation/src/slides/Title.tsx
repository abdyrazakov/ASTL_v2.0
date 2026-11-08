const header = [
  'Министерство науки, высшего образования и инноваций Кыргызской Республики',
  'Кыргызский государственный технический университет им. И.Раззакова',
  'Институт информационных технологий',
  'Кафедра «Программное обеспечение компьютерных систем»',
  'Направление: 710400 «Программная инженерия»',
]

export function Title() {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center px-[160px] text-center">
      <div className="flex flex-col gap-1 text-[19px] leading-[1.5] text-paint-dim">
        {header.map((line) => <div key={line}>{line}</div>)}
      </div>
      <div className="mt-[72px] text-[21px] text-paint-dim">Тема проекта</div>
      <h1 className="mt-4 max-w-[1180px] text-[54px] leading-[1.12] font-extrabold tracking-[-0.022em] text-paint">
        ASTL: адаптивное управление светофором на основе машинного зрения и имитационного моделирования перекрёстка
      </h1>
      <div className="mt-[72px] flex gap-[72px] text-[23px]">
        <div><span className="text-paint-dim">Выполнил:</span> Атамбек</div>
        <div><span className="text-paint-dim">Преподаватель:</span> Жогаштиев Н.Т.</div>
      </div>
    </div>
  )
}
