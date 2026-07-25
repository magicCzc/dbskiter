export interface HealthResponse {
  status: string
  score: number
  issues: string[]
  collected_at: string
}

export interface SlowQuery {
  sql: string
  execution_time: number
  execution_count: number
  avg_time: number
  rows_examined: number
}

export interface SlowQueryResponse {
  total: number
  queries: SlowQuery[]
}

export interface Risk {
  severity: string
  description: string
  category: string
  current_value: string
  recommended_value: string
}

export interface SecurityResponse {
  total_risks: number
  critical_count: number
  high_count: number
  risks: Risk[]
}

export interface BackupResult {
  success: boolean
  backup_id: string
  file_path: string
  file_size: number
  error?: string
}

export interface BackupRecord {
  backup_id: string
  backup_type: string
  file_path: string
  file_size: number
  success: boolean
  error?: string
}

export interface Task {
  name: string
  task_type: string
  schedule: string
  status: string
  last_run: string
  next_run: string
}

export interface LogEntry {
  timestamp: string
  command: string
  database: string
  status_code: number
  execution_time_ms: number
}

export interface ApiStatus {
  status: string
  version: string
  api_endpoints: string[]
}