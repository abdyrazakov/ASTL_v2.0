import type { FC } from 'react'
import type { Mode } from '../data/replay'
import { Approach } from './Approach'
import { Architecture } from './Architecture'
import { Controller } from './Controller'
import { Demo } from './Demo'
import { Analogs } from './Analogs'
import { Next } from './Next'
import { Problem } from './Problem'
import { Results } from './Results'
import { Safety } from './Safety'
import { Stages } from './Stages'
import { Team } from './Team'
import { Title } from './Title'

/** Камера над живым перекрёстком: какой режим проигрывать, куда смотреть и насколько ярко.
 *  x, y — сдвиг квадрата 900×900 на холсте 1600×900 (по центру: x = 350), s — масштаб,
 *  rx — наклон камеры к горизонту, rz — поворот вокруг перекрёстка, в градусах. */
export interface Camera { mode: Mode; x: number; y: number; s: number; o: number; rx?: number; rz?: number }

export interface SlideDef {
  id: string
  steps: number // сколько нажатий открывает все шаги слайда
  camera: Camera
  scrim: 'left' | 'full' | 'none'
  Comp: FC
}

const hidden: Camera = { mode: 'adaptive', x: 350, y: 0, s: 2.4, o: 0 }

export const slides: SlideDef[] = [
  { id: 'title', steps: 0, camera: { mode: 'adaptive', x: 350, y: 40, s: 1.5, o: 0.2, rx: 58, rz: -32 }, scrim: 'full', Comp: Title },
  { id: 'problem', steps: 1, camera: { mode: 'fixed', x: 720, y: 30, s: 1.45, o: 1, rx: 50, rz: -28 }, scrim: 'left', Comp: Problem },
  { id: 'approach', steps: 3, camera: { mode: 'adaptive', x: 740, y: 30, s: 1.35, o: 1, rx: 46, rz: 24 }, scrim: 'left', Comp: Approach },
  { id: 'stages', steps: 0, camera: hidden, scrim: 'none', Comp: Stages },
  { id: 'architecture', steps: 0, camera: hidden, scrim: 'none', Comp: Architecture },
  { id: 'safety', steps: 1, camera: hidden, scrim: 'none', Comp: Safety },
  { id: 'controller', steps: 2, camera: hidden, scrim: 'none', Comp: Controller },
  { id: 'demo', steps: 0, camera: hidden, scrim: 'none', Comp: Demo },
  { id: 'results', steps: 1, camera: hidden, scrim: 'none', Comp: Results },
  { id: 'analogs', steps: 1, camera: hidden, scrim: 'none', Comp: Analogs },
  { id: 'next', steps: 0, camera: { mode: 'adaptive', x: 350, y: 60, s: 1.6, o: 0.22, rx: 60, rz: 30 }, scrim: 'full', Comp: Next },
  { id: 'team', steps: 0, camera: hidden, scrim: 'none', Comp: Team },
]
