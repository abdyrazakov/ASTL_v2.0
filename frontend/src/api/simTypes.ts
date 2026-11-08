// Типы этапа 2: профиль перекрёстка, прогон симуляции, 2D-сцена.
import type { LaneSnapshot, TrafficSnapshot } from './types'

export type Heading = 'N' | 'E' | 'S' | 'W'
export type Movement = 'straight' | 'left' | 'right'
export type ControllerMode = 'fixed' | 'adaptive'
export type SignalColor = 'red' | 'yellow' | 'green'
export type SignalStateName = 'STARTUP_ALL_RED' | 'GREEN' | 'YELLOW' | 'ALL_RED' | 'FAULT'

export interface Approach {
  id: string
  name: string
  heading: Heading
}

export interface SimLane {
  id: string
  approach_id: string
  index: number
  name: string
  color: string
  movements: Movement[]
  length_m: number
  speed_limit_mps: number
  arrival_rate_vph: number
}

export interface LaneMovement {
  lane_id: string
  movement: Movement
}

export interface SignalGroup {
  id: string
  name: string
  movements: LaneMovement[]
}

export interface Phase {
  id: string
  name: string
  signal_groups: string[]
  fixed_green_sec: number
  min_green_sec: number | null
  max_green_sec: number | null
}

export interface Timings {
  min_green_sec: number
  max_green_sec: number
  yellow_sec: number
  all_red_clearance_sec: number
  startup_all_red_sec: number
  gap_out_sec: number
  max_red_wait_sec: number
  detector_distance_m: number
}

export interface ScenarioSegment {
  start_sec: number
  end_sec: number
  lane_ids: string[]
  multiplier: number
  label: string
}

export interface TrafficParams {
  composition: Record<string, number>
  seed: number
  min_gap_m: number
  scenario: ScenarioSegment[]
  scenario_name: string
}

export interface IntersectionProfile {
  schema_version: string
  kind: 'intersection'
  profile_id: string
  name: string
  template: string
  notes: string
  created_at: string
  updated_at: string
  approaches: Approach[]
  lanes: SimLane[]
  signal_groups: SignalGroup[]
  conflicts: Record<string, string[]>
  phases: Phase[]
  phase_order: string[]
  transitions: Record<string, string[]> | null
  timings: Timings
  traffic: TrafficParams
  adaptive: { wait_weight_per_sec: number; queue_clear_min_demand: number | null }
}

export interface TemplateInfo {
  key: string
  name: string
  description: string
}

export interface ValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

export type RunStatus = 'queued' | 'running' | 'paused' | 'completed' | 'error' | 'stopped'

export interface SimProgress {
  run_id: string
  kind: 'simulation'
  profile_id: string
  profile_name: string
  status: RunStatus
  sim_time_sec: number
  duration_sec: number | null
  speed: number
  realtime_ratio: number
  controller_mode: ControllerMode
  initial_controller_mode: ControllerMode
  mode_switches: number
  seed: number
  signal_state: SignalStateName
  active_phase: string | null
  next_phase: string | null
  phase_remaining_sec: number | null
  phase_remaining_is_estimate: boolean
  started_at: string | null
  error_message: string | null
  headless: boolean
}

/** Снимок полосы этапа 2 = поля этапа 1 + новые показатели симуляции. */
export interface SimLaneSnapshot extends LaneSnapshot {
  approach_id: string
  entry_backlog: number
  queue_spillback: boolean
  signals: Partial<Record<Movement, SignalColor>>
  arrival_rate_vph_now: number
  arrivals: number
  departed_count: number
  avg_delay_sec: number
  max_delay_sec: number
  stops_per_vehicle: number
  avg_departed_wait_sec: number
  max_departed_wait_sec: number
  throughput_per_hour: number
}

export interface SimTotals {
  departed: number
  avg_delay_sec: number
  stops_per_vehicle: number
  throughput_per_hour: number
  vehicles_in_system: number
}

export interface SimSafety {
  blocked_violations: number
  faults: number
  red_clamps: number
  conflict_invariant_ok_now: boolean
}

export interface SimSnapshot extends TrafficSnapshot {
  source: 'simulation'
  lanes: SimLaneSnapshot[]
  controller_mode: ControllerMode
  signal_state: SignalStateName
  active_phase: string | null
  next_phase: string | null
  phase_remaining_sec: number | null
  phase_remaining_is_estimate: boolean
  signals: Record<string, SignalColor>
  totals: SimTotals
  safety: SimSafety
  seed: number
}

export interface SceneVehicle {
  id: number
  lane_id: string
  cls: string
  movement: Movement
  s: number
  length: number
  state: 'moving' | 'waiting'
  crossed: boolean
  progress: number
}

export interface Scene {
  t: number
  signal_state: SignalStateName
  active_phase: string | null
  next_phase: string | null
  phase_remaining_sec: number | null
  phase_remaining_is_estimate: boolean
  controller_mode: ControllerMode
  signals: Record<string, SignalColor>
  vehicles: SceneVehicle[]
  backlog: Record<string, number>
}

export interface GreenRecord {
  phase_id: string
  start_sec: number
  end_sec: number
  duration_sec: number
  reason: string
  mode: string
  next_phase: string
}

export interface RunBrief {
  run_id: string
  created_at: string
  controller_mode: ControllerMode
  totals: SimTotals
  lanes: Record<string, {
    name: string
    arrivals: number
    departed_count: number
    avg_delay_sec: number
    stops_per_vehicle: number
    throughput_per_hour: number
    max_departed_wait_sec: number
  }>
}

export type Comparison =
  | { available: true; seed: number; duration_sec: number; fixed: RunBrief; adaptive: RunBrief }
  | { available: false; seed: number; have_modes: string[]; message: string }
