import { IntersectionCanvas } from '../components/IntersectionCanvas'
import { type Mode, useLiveFrame, useReplay } from '../data/replay'

function Side({ mode, title }: { mode: Mode; title: string }) {
  const r = useReplay()
  const f = useLiveFrame(mode)
  return (
    <div className="flex w-[560px] flex-col">
      <div className="h-[560px] w-[560px] overflow-hidden rounded-[6px]">
        <IntersectionCanvas replay={r} mode={mode} label={`Запись режима: ${title}`} />
      </div>
      <div className="mt-6 text-[30px] font-bold">{title}</div>
      <div className="mt-3 grid grid-cols-2 gap-6 text-[21px] text-paint-dim">
        <div><span className={`text-[44px] font-extrabold ${mode === 'fixed' ? 'text-stop' : 'text-go'}`}>{f.q}</span><br />в очереди сейчас</div>
        <div><span className="text-[44px] font-extrabold text-paint">{f.d.toFixed(1)} с</span><br />средняя задержка с начала часа</div>
      </div>
    </div>
  )
}

export function Demo() {
  const r = useReplay()
  return (
    <div className="absolute inset-0 flex flex-col items-center pt-[40px]">
      <p className="text-[20px] text-paint-dim">
        Одни и те же машины в обоих режимах: seed {r.seed}, пик на восточном подходе, запись симуляции
      </p>
      <div className="mt-6 flex items-start gap-[120px]">
        <Side mode="fixed" title="Фиксированный цикл" />
        <Side mode="adaptive" title="Адаптивный" />
      </div>
    </div>
  )
}
