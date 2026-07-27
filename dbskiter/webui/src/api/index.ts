import type {
  HealthResponse, SlowQueryResponse, SecurityResponse,
  BackupResult, BackupRecord, Task, LogEntry, ApiStatus, DatabasesResponse,
} from '@/types'

const API_BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  const resp = await fetch(url, {
    headers: { Accept: 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
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
    request<any>(`/diagnose/realtime?database=${encodeURIComponent(db)}`),

  createBackup: async (db = 'default', type = 'full', tables?: string) => {
    let url = `/backup?database=${encodeURIComponent(db)}&backup_type=${type}`
    if (tables) url += `&tables=${encodeURIComponent(tables)}`
    return request<BackupResult>(url, { method: 'POST' })
  },

  listBackups: (db = 'default') =>
    request<{ backups: BackupRecord[] }>(`/backups?database=${encodeURIComponent(db)}`),

  tasks: (db = 'default') =>
    request<{ tasks: Task[] }>(`/tasks?database=${encodeURIComponent(db)}`),

  logs: (db = 'default', hours = 24) =>
    request<{ logs: LogEntry[] }>(`/logs?database=${encodeURIComponent(db)}&hours=${hours}`),

  databases: () =>
    request<DatabasesResponse>('/databases'),

  anomalies: (db = 'default', hours = 6) =>
    request<any>(`/monitor/anomalies?database=${encodeURIComponent(db)}&hours=${hours}`),

  capacity: (db = 'default', resource = 'disk') =>
    request<any>(`/monitor/capacity?database=${encodeURIComponent(db)}&resource=${resource}`),

  topSql: (db = 'default', limit = 10) =>
    request<any>(`/diagnose/top?database=${encodeURIComponent(db)}&limit=${limit}`),

  locks: (db = 'default') =>
    request<any>(`/diagnose/locks?database=${encodeURIComponent(db)}`),

  space: (db = 'default', top = 20) =>
    request<any>(`/diagnose/space?database=${encodeURIComponent(db)}&top=${top}`),

  connections: (db = 'default') =>
    request<any>(`/diagnose/connections?database=${encodeURIComponent(db)}`),
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

export function exportCSV(data: Record<string, any>[], filename = 'export.csv') {
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