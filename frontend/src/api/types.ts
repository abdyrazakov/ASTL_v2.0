export interface VideoInfo {
  video_id: string
  filename: string
  width: number
  height: number
  fps: number
  duration_sec: number
  frame_count: number
  uploaded_at: string
}

export interface Point {
  x: number
  y: number
}

export interface PolygonT {
  points: Point[]
}

export type CountDirection = 'positive' | 'negative' | 'both'

export interface CountLineT {
  p1: Point
  p2: Point
  positive_side_point: Point
  direction: CountDirection
}

export type ReferencePointMode = 'bottom_center' | 'bottom_left' | 'bottom_right' | 'center'

export interface Lane {
  id: string
  name: string
  color: string
  observation_polygon: PolygonT
  queue_zone_polygon: PolygonT
  count_line: CountLineT
  reference_point_mode: ReferencePointMode | null
}

export interface AnalysisParams {
  model_name: string
  conf_threshold: number
  iou_threshold: number
  classes: string[]
  lane_switch_hysteresis_sec: number
  track_lost_grace_sec: number
  speed_window_sec: number
  stop_enter_speed: number
  stop_duration_threshold_sec: number
  stop_exit_speed: number
  queue_exit_duration_sec: number
  flow_window_sec: number
  crossing_cooldown_sec: number
}

export interface SourceVideoInfo {
  filename: string
  width: number
  height: number
  fps: number
  duration_sec: number
}

export interface Profile {
  schema_version: string
  profile_id: string
  name: string
  status: 'preliminary' | 'verified'
  created_at: string
  updated_at: string
  source_video: SourceVideoInfo
  reference_point_mode: ReferencePointMode
  lanes: Lane[]
  analysis_params: AnalysisParams
  notes: string
}

export interface LaneSnapshot {
  lane_id: string
  name: string
  color: string
  vehicles: number
  queued: number
  queue_truncated_by_frame: boolean
  avg_wait_sec: number
  max_wait_sec: number
  wait_sample_size: number
  flow_count_window: number
  flow_window_available_sec: number
  flow_window_target_sec: number
  total_crossings: number
  vehicle_types: Record<string, number>
}

export interface TrafficSnapshot {
  schema_version: string
  timestamp_sec: number
  lanes: LaneSnapshot[]
  run_id?: string
  profile_id?: string
  window_duration_sec?: number
}

export type JobStatus = 'queued' | 'running' | 'paused' | 'completed' | 'error' | 'stopped'

export interface JobProgress {
  run_id: string
  video_id: string
  profile_id: string
  status: JobStatus
  video_time_sec: number
  source_duration_sec: number
  frames_processed: number
  frames_total: number
  processing_fps: number
  source_fps: number
  realtime_ratio: number
  started_at: string | null
  error_message: string | null
  model_ready: boolean
}

export interface RenderOptions {
  show_boxes: boolean
  show_ids: boolean
  show_trajectories: boolean
  show_lanes: boolean
  show_queue_zones: boolean
  show_lines: boolean
}
