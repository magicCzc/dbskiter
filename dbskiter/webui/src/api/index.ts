import type {
  HealthResponse, SlowQueryResponse, SecurityResponse,
  BackupResult, BackupRecord, Task, LogEntry, ApiStatus, DatabasesResponse,
  UserInfo, DiagnoseResult, LockResponse, SpaceResponse, ConnectionResponse,
  TrendResponse, InspectorResponse, DbConfig, DbConfigListResponse, DbConfigTestResponse,
  SqlExecuteResponse, SchemaResponse, AlertListResponse, AlertStatsResponse,
  AnomalyInfo, CapacityInfo,
} from '@/types'
import { IS_DEMO, shouldMock, handleMock } from '@/mock'

const API_BASE = '/api'
const CACHE_TTL = 30000 // 30 秒缓存

// 简单缓存层
const cache = new Map<string, { data: unknown; time: number }>()

function getCached<T>(key: string): T | null {
  const hit = cache.get(key)
  if (hit && Date.now() - hit.time < CACHE_TTL) {
    return hit.data as T
  }
  cache.delete(key)
  return null
}

function setCache(key: string, data: unknown) {
  cache.set(key, { data, time: Date.now() })
  // 限制缓存大小
  if (cache.size > 50) {
    const oldest = cache.keys().next().value
    if (oldest) cache.delete(oldest)
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = options?.method || 'GET'

  // 演示模式：直接返回 mock 数据
  if (shouldMock(path)) {
    const mockData = await handleMock(path, options)
    return mockData as T
  }

  // 非 GET 请求清除相关缓存
  if (method !== 'GET') {
    cache.clear()
  }

  // GET 请求使用缓存（除非指定 noCache）
  const noCache = (options?.headers as Record<string, string> | undefined)?.['X-No-Cache'] === 'true'
  if (method === 'GET' && !noCache) {
    const cached = getCached<T>(path)
    if (cached) return cached
  }

  const url = `${API_BASE}${path}`
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options?.body) {
    headers['Content-Type'] = 'application/json'
  }
  // 清理自定义 header 避免发送到服务端
  const cleanHeaders = { ...headers }
  if (noCache) {
    delete cleanHeaders['X-No-Cache']
  }

  const resp = await fetch(url, {
    headers: cleanHeaders,
    ...options,
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  const data = await resp.json()
  // GET 请求结果写入缓存
  if (method === 'GET') {
    setCache(path, data)
  }
  return data
}

export const api = {
  status: () => request<ApiStatus>('/status'),

  health: (db = 'default') =>
    request<HealthResponse>(`/health?database=${encodeURIComponent(db)}`),

  slowQueries: (db = 'default', top = 10, hours = 6) =>
    request<SlowQueryResponse>(
      `/slow-queries?database=${encodeURIComponent(db)}&top=${top}&hours=${hours}`
    ),

  security: (db = 'default') =>
    request<SecurityResponse>(`/security?database=${encodeURIComponent(db)}`),

  diagnose: (db = 'default') =>
    request<DiagnoseResult>(`/diagnose/realtime?database=${encodeURIComponent(db)}`),

  createBackup: async (db = 'default', type = 'full', tables?: string) => {
    let url = `/backup?database=${encodeURIComponent(db)}&backup_type=${type}`
    if (tables) url += `&tables=${encodeURIComponent(tables)}`
    return request<BackupResult>(url, { method: 'POST' })
  },

  listBackups: (db = 'default') =>
    request<{ backups: BackupRecord[] }>(`/backups?database=${encodeURIComponent(db)}`),

  tasks: (db = 'default') =>
    request<{ tasks: Task[] }>(`/tasks?database=${encodeURIComponent(db)}`),

  listTasks: () =>
    request<{ success: boolean; tasks: Task[]; types: Record<string, unknown> }>('/tasks'),

  listTaskTypes: () =>
    request<{ success: boolean; types: Record<string, unknown> }>('/tasks/types'),

  createTask: (config: { name: string; task_type: string; db_alias: string; cron_expr: string; params?: Record<string, unknown> }) =>
    request<{ success: boolean; id?: number; message?: string }>('/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),

  toggleTask: (id: number) =>
    request<{ success: boolean; is_enabled: boolean; message?: string }>(`/tasks/${id}/toggle`, { method: 'POST' }),

  deleteTask: (id: number) =>
    request<{ success: boolean; message?: string }>(`/tasks/${id}`, { method: 'DELETE' }),

  listUsers: () =>
    request<{ success: boolean; users: UserInfo[] }>('/auth/users'),

  updateUserRole: (userId: number, role: string) =>
    request<{ success: boolean; message?: string }>(`/auth/users/${userId}/role`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    }),

  toggleUser: (userId: number) =>
    request<{ success: boolean; is_active: boolean; message?: string }>(`/auth/users/${userId}/toggle`, { method: 'POST' }),

  logs: (db = 'default', hours = 24) =>
    request<{ logs: LogEntry[] }>(`/logs?database=${encodeURIComponent(db)}&hours=${hours}`),

  databases: () =>
    request<DatabasesResponse>('/databases', { headers: { 'X-No-Cache': 'true' } as unknown as HeadersInit }),

  anomalies: (db = 'default', hours = 6) =>
    request<{ success: boolean; data?: { anomalies?: AnomalyInfo[]; raw_metrics?: { anomalies?: AnomalyInfo[] } } }>(`/monitor/anomalies?database=${encodeURIComponent(db)}&hours=${hours}`),

  capacity: (db = 'default', resource = 'disk') =>
    request<{ success: boolean; data?: CapacityInfo & { raw_metrics?: Record<string, unknown> } }>(`/monitor/capacity?database=${encodeURIComponent(db)}&resource=${resource}`),

  topSql: (db = 'default', limit = 10) =>
    request<{ success: boolean; data: { top_queries: Record<string, unknown>[]; raw_metrics: Record<string, unknown> } }>(`/diagnose/top?database=${encodeURIComponent(db)}&limit=${limit}`),

  locks: (db = 'default') =>
    request<LockResponse>(`/diagnose/locks?database=${encodeURIComponent(db)}`),

  space: (db = 'default', top = 20) =>
    request<SpaceResponse>(`/diagnose/space?database=${encodeURIComponent(db)}&top=${top}`),

  connections: (db = 'default') =>
    request<ConnectionResponse>(`/diagnose/connections?database=${encodeURIComponent(db)}`),

  // ── Phase 1: 新增 API 方法 ─────────────────────────

  trends: (db = 'default', hours = 24) =>
    request<TrendResponse>(`/monitor/trends?database=${encodeURIComponent(db)}&hours=${hours}`),

  inspectorReport: (db = 'default', reportType = 'full') =>
    request<InspectorResponse>(`/inspector/report?database=${encodeURIComponent(db)}&report_type=${reportType}`),

  // ── Phase 2: SQL 编辑器 API ─────────────────────────

  executeSQL: async (db: string, sql: string, limit = 100, readOnly = true) => {
    const url = `/sql/execute?database=${encodeURIComponent(db)}&sql=${encodeURIComponent(sql)}&limit=${limit}&read_only=${readOnly}`
    return request<SqlExecuteResponse>(url, { method: 'POST' })
  },

  getSchema: (db = 'default', table?: string) => {
    let url = `/sql/schema?database=${encodeURIComponent(db)}`
    if (table) url += `&table=${encodeURIComponent(table)}`
    return request<SchemaResponse>(url)
  },

  // ── 数据库配置管理 ────────────────────────────────

  listDbConfigs: () =>
    request<DbConfigListResponse>('/config/databases'),

  addDbConfig: (config: Partial<DbConfig>) =>
    request<{ success: boolean; alias?: string; message?: string; connection?: DbConfigTestResponse }>('/config/databases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),

  updateDbConfig: (alias: string, config: Partial<DbConfig>) =>
    request<{ success: boolean; alias?: string; message?: string }>(`/config/databases/${encodeURIComponent(alias)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),

  deleteDbConfig: (alias: string) =>
    request<{ success: boolean; message?: string }>(`/config/databases/${encodeURIComponent(alias)}`, { method: 'DELETE' }),

  testDbConfig: (config: { alias?: string; host?: string; port?: number; user?: string; password?: string; database?: string; dialect?: string }) =>
    request<DbConfigTestResponse>('/config/databases/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),

  // ── 告警 API ──────────────────────────────────────

  listAlerts: (params?: { db_alias?: string; status?: string; level?: string; limit?: number }) => {
    const p = new URLSearchParams()
    if (params?.db_alias) p.set('db_alias', params.db_alias)
    if (params?.status) p.set('status', params.status)
    if (params?.level) p.set('level', params.level)
    if (params?.limit) p.set('limit', String(params.limit))
    const qs = p.toString()
    return request<AlertListResponse>(`/alerts${qs ? '?' + qs : ''}`)
  },

  getAlertStats: () =>
    request<AlertStatsResponse>('/alerts/stats'),

  acknowledgeAlert: (id: number) =>
    request<{ success: boolean; message?: string }>(`/alerts/${id}/acknowledge`, { method: 'POST' }),

  resolveAlert: (id: number) =>
    request<{ success: boolean; message?: string }>(`/alerts/${id}/resolve`, { method: 'POST' }),

  resolveAllAlerts: () =>
    request<{ success: boolean; resolved_count?: number }>('/alerts/resolve-all', { method: 'POST' }),

  getAlertHistory: (hours = 24, db_alias?: string) => {
    let url = `/alerts/history?hours=${hours}`
    if (db_alias) url += `&db_alias=${encodeURIComponent(db_alias)}`
    return request<AlertListResponse>(url)
  },
}

export function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let s = bytes
  while (s >= 1024 && i < units.length - 1) { s /= 1024; i++ }
  return `${s.toFixed(1)} ${units[i]}`
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}min`
}

export function severityClass(severity: string): string {
  const map: Record<string, string> = {
    critical: 'badge-critical',
    high: 'badge-high',
    medium: 'badge-medium',
    low: 'badge-low',
    healthy: 'badge-low',
    warning: 'badge-medium',
    success: 'badge-low',
    failed: 'badge-critical',
  }
  return map[severity] || 'badge-medium'
}

export function exportCSV(data: Record<string, unknown>[], filename = 'export.csv') {
  if (!data.length) return
  const headers = Object.keys(data[0])
  const rows = data.map(row => headers.map(h => {
    const val = row[h]?.toString() || ''
    return val.includes(',') ? `"${val}"` : val
  }).join(','))
  const csv = [headers.join(','), ...rows].join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}