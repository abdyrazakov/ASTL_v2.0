import { useCallback, useEffect, useLayoutEffect, useState } from 'react'
import { StepContext } from './components/deck'
import { IntersectionCanvas } from './components/IntersectionCanvas'
import { ReplayContext, useLoadReplay } from './data/replay'
import { slides } from './slides'

function readHash(): number {
  const n = Number(location.hash.replace('#', '')) - 1
  return Number.isInteger(n) && n >= 0 && n < slides.length ? n : 0
}

/** Масштаб холста 1600×900 под окно браузера. */
function useScale() {
  const [scale, setScale] = useState(1)
  useLayoutEffect(() => {
    const fit = () => setScale(Math.min(window.innerWidth / 1600, window.innerHeight / 900))
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [])
  return scale
}

export function App() {
  const { data, error } = useLoadReplay()
  const [pos, setPos] = useState({ index: readHash(), step: 0 })
  const scale = useScale()

  const next = useCallback(() => setPos((p) => {
    if (p.step < slides[p.index].steps) return { ...p, step: p.step + 1 }
    return p.index < slides.length - 1 ? { index: p.index + 1, step: 0 } : p
  }), [])
  const prev = useCallback(() => setPos((p) => {
    if (p.step > 0) return { ...p, step: p.step - 1 }
    // назад — на предыдущий слайд сразу полностью раскрытым
    return p.index > 0 ? { index: p.index - 1, step: slides[p.index - 1].steps } : p
  }), [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'].includes(e.key)) { e.preventDefault(); next() }
      else if (['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'].includes(e.key)) { e.preventDefault(); prev() }
      else if (e.key === 'Home') setPos({ index: 0, step: 0 })
      else if (e.key === 'End') setPos({ index: slides.length - 1, step: slides[slides.length - 1].steps })
      else if (e.key === 'f' || e.key === 'F') {
        if (document.fullscreenElement) document.exitFullscreen()
        else document.documentElement.requestFullscreen()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [next, prev])

  useEffect(() => { history.replaceState(null, '', `#${pos.index + 1}`) }, [pos.index])

  const slide = slides[pos.index]
  const cam = slide.camera
  const Comp = slide.Comp
  return (
    <div className="stage" onClick={next}>
      <div className="canvas" style={{ transform: `translate(-50%, -50%) scale(${scale})` }}>
        {error && <p className="absolute top-[120px] left-[120px] max-w-[1200px] text-[24px] text-stop">{error}</p>}
        {data && (
          <ReplayContext.Provider value={data}>
            <div className="camera" style={{ transform: `translate(${cam.x}px, ${cam.y}px) perspective(1700px) rotateX(${cam.rx ?? 0}deg) rotateZ(${cam.rz ?? 0}deg) scale(${cam.s})`, opacity: cam.o }}>
              <IntersectionCanvas key={cam.mode} replay={data} mode={cam.mode} label="Живая запись симуляции перекрёстка" />
            </div>
            <div className="scrim-left absolute inset-0 transition-opacity duration-1000" style={{ opacity: slide.scrim === 'left' ? 1 : 0 }} />
            <div className="scrim-full absolute inset-0 transition-opacity duration-1000" style={{ opacity: slide.scrim === 'full' ? 1 : 0 }} />
            <StepContext.Provider value={pos.step}>
              <div key={pos.index} className="enter absolute inset-0">
                <Comp />
              </div>
            </StepContext.Provider>
          </ReplayContext.Provider>
        )}
        {/* Прогресс — дорожная разметка: пройденные штрихи, текущий — стоп-линия */}
        <div className="absolute bottom-[48px] left-[120px] flex items-center gap-[10px]" aria-label={`Слайд ${pos.index + 1} из ${slides.length}`}>
          {slides.map((s, i) => (
            <span key={s.id} className="h-[4px] rounded-[1px] transition-all duration-500"
              style={{ width: i === pos.index ? 44 : 18, background: i === pos.index ? '#eceae2' : i < pos.index ? 'rgba(236,234,226,.55)' : 'rgba(236,234,226,.18)' }} />
          ))}
        </div>
      </div>
    </div>
  )
}
