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
  [key: string]: any
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
  created_at?: string
  [key: string]: any
}

export interface Task {
  name: string
  task_type: string
  schedule: string
  status: string
  last_run: string
  next_run: string
  [key: string]: any
}

export interface LogEntry {
  timestamp: string
  command: string
  database: string
  status_code: number
  execution_time_ms: number
  args?: Record<string, any>
  action?: string
  [key: string]: any
}

export interface ApiStatus {
  status: string
  version: string
  api_endpoints: string[]
}

export interface DatabasesResponse {
  databases: string[]
}

// ── 健康诊断 ─────────────────────────────────

export interface DiagnoseResult {
  success: boolean
  database: string
  score: number
  status: string
  issues: DiagnoseIssue[]
  ai_hints: Record<string, any>
  raw_data: Record<string, any>
  [key: string]: any
}

export interface DiagnoseIssue {
  severity?: string
  message?: string
  description?: string
  type?: string
  [key: string]: any
}

// ── 慢查询 ─────────────────────────────────

export interface SlowQueryItem {
  sql: string
  execution_time: number
  execution_count: number
  avg_time: number
  rows_examined: number
  [key: string]: any
}

// ── 锁分析 ─────────────────────────────────

export interface LockInfo {
  blocking_pid: number
  blocked_pid: number
  blocking_query: string
  blocked_query: string
  blocking_duration: number
  database: string
  [key: string]: any
}

export interface LockResponse {
  success: boolean
  data?: {
    locks?: LockInfo[]
    deadlocks?: any[]
    [key: string]: any
  }
  error?: string
  solution?: string
  [key: string]: any
}

// ── 空间分析 ─────────────────────────────────

export interface SpaceInfo {
  table_name: string
  table_schema: string
  total_size: number
  data_size: number
  index_size: number
  free_space: number
  [key: string]: any
}

export interface SpaceResponse {
  success: boolean
  data?: {
    raw_metrics?: {
      total_space: number
      tables: SpaceInfo[]
      table_count: number
    }
    [key: string]: any
  }
  [key: string]: any
}

// ── 连接管理 ─────────────────────────────────

export interface ConnectionInfo {
  pid: number
  user: string
  host: string
  database: string
  state: string
  query: string
  duration: number
  [key: string]: any
}

export interface ConnectionResponse {
  success: boolean
  data?: {
    raw_metrics?: {
      connections: ConnectionInfo[]
      max_connections: number
    }
    [key: string]: any
  }
  [key: string]: any
}

// ── 异常检测 ─────────────────────────────────

export interface AnomalyInfo {
  metric: string
  timestamp: string
  actual_value: number
  expected_value: number
  deviation: number
  severity: string
  description: string
  [key: string]: any
}

// ── 容量预测 ─────────────────────────────────

export interface CapacityInfo {
  resource: string
  current_usage: number
  total_capacity: number
  growth_rate: number
  estimated_exhaustion: string
  days_remaining: number
  [key: string]: any
}

// ── 趋势数据 ─────────────────────────────────

export interface TrendResponse {
  timestamps: string[]
  cpu: number[]
  memory: number[]
  disk: number[]
  qps: number[]
  [key: string]: any
}

// ── 告警管理 ─────────────────────────────────

export interface AlertItem {
  id: number
  db_alias: string
  metric: string
  level: string
  current_value: number
  threshold: number
  message: string
  status: string
  created_at: string
  resolved_at?: string
  [key: string]: any
}

export interface AlertListResponse {
  success: boolean
  total: number
  alerts: AlertItem[]
  [key: string]: any
}

export interface AlertStatsResponse {
  success: boolean
  stats: {
    total: number
    open: number
    critical: number
    warning: number
  }
  [key: string]: any
}

// ── 巡检报告 ─────────────────────────────────

export interface InspectorResponse {
  success: boolean
  data?: {
    raw_metrics?: {
      health_score?: number
      score?: number
      items?: any[]
      issues?: any[]
      statistics?: Record<string, any>
      [key: string]: any
    }
    score?: number
    [key: string]: any
  }
  score?: number
  [key: string]: any
}

// ── Database 配置 ─────────────────────────────────

export interface DbConfig {
  alias: string
  host: string
  port: number
  user: string
  password: string
  database: string
  dialect: string
  pool_size: number
  [key: string]: any
}

export interface DbConfigListResponse {
  success: boolean
  databases: Record<string, DbConfig>
  count: number
  [key: string]: any
}

export interface DbConfigTestResponse {
  success: boolean
  database?: string
  message: string
  [key: string]: any
}

// ── SQL 执行 ─────────────────────────────────

export interface SqlExecuteResponse {
  success: boolean
  data?: {
    row_count: number
    columns: string[]
    rows: any[][]
    execution_time: number
    sql?: string
    [key: string]: any
  }
  error?: string
  execution_time?: number
  row_count?: number
  columns?: string[]
  rows?: any[][]
  [key: string]: any
}

// ── Schema 信息 ─────────────────────────────────

export interface SchemaColumn {
  name: string
  type: string
  nullable: boolean
  default?: string
  [key: string]: any
}

export interface SchemaIndex {
  name: string
  columns: string[]
  unique: boolean
  [key: string]: any
}

export interface SchemaResponse {
  success: boolean
  table?: string
  columns?: SchemaColumn[]
  indexes?: SchemaIndex[]
  tables?: string[]
  data?: any
  [key: string]: any
}

// ── 通用 API 响应 ─────────────────────────────────

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  message?: string
  [key: string]: any
}

export interface ApiListResponse<T = any> {
  success: boolean
  data?: T[]
  items?: T[]
  total?: number
  [key: string]: any
}

export interface ApiError {
  detail: string
  [key: string]: any
}

export interface UserInfo {
  id: number
  username: string
  role: string
  email: string
  is_active: boolean
  created_at?: string
  last_login?: string | null
  [key: string]: any
}

export interface ScheduledTaskInfo {
  id: number
  name: string
  task_type: string
  db_alias: string
  cron_expr: string
  is_enabled: boolean
  last_run: string | null
  next_run?: string | null
  created_at?: string
  params?: Record<string, any>
  [key: string]: any
}