/**
 * Mock API 路由分发器
 *
 * 根据 URL 路径分发到对应的 mock 数据生成函数
 * 在 vite.config.ts 中通过 VITE_DEMO_MODE 环境变量控制是否启用
 */

import type { SqlExecuteResponse, SchemaResponse, TrendResponse } from '@/types'
import {
  mockDelay,
  mockHealth, mockAllHealth,
  mockSlowQueries, mockSecurity,
  mockRealtimeDiagnose, mockTopSql, mockLocks, mockSpace, mockConnections,
  mockAnomalies, mockCapacity, mockTrends, mockInspectorReport,
  mockBackups, mockCreateBackup, mockTasks, mockTaskTypes,
  mockExecuteSQL, mockSchema,
  mockAlerts, mockAlertStats,
  mockLogs, mockUsers, mockDatabasesList,
  mockStatus, mockDbConfigs, mockAddDbConfig, mockUpdateDbConfig, mockDeleteDbConfig, mockTestConnection,
} from './data'

// 是否为演示模式（由 Vite 编译时注入）
export const IS_DEMO = import.meta.env.VITE_DEMO_MODE === 'true' ||
  typeof window !== 'undefined' && window.location.hostname.endsWith('github.io')

/**
 * 判断是否为 mock 请求
 */
export function shouldMock(path: string): boolean {
  if (!IS_DEMO) return false
  // 始终 mock 所有 /api/ 请求
  return path.startsWith('/api/')
}

/**
 * 根据路径和选项返回 mock 数据
 */
export async function handleMock(path: string, options?: RequestInit): Promise<any> {
  await mockDelay(80, 300)

  // 解析路径和方法
  const url = new URL(path, 'http://localhost')
  const method = options?.method || 'GET'
  const db = url.searchParams.get('database') || 'default'
  const params = options?.body ? JSON.parse(options.body.toString()) : {}

  // 路由分发
  if (path === '/api/status') return mockStatus()
  if (path.startsWith('/api/health/all')) return mockAllHealth()
  if (path.startsWith('/api/health')) return mockHealth(db)
  if (path.startsWith('/api/slow-queries')) return mockSlowQueries(Number(url.searchParams.get('top')) || 10, Number(url.searchParams.get('hours')) || 1)
  if (path.startsWith('/api/security')) return mockSecurity()
  if (path.startsWith('/api/diagnose/realtime')) return mockRealtimeDiagnose(db)
  if (path.startsWith('/api/diagnose/top')) return mockTopSql(Number(url.searchParams.get('limit')) || 10)
  if (path.startsWith('/api/diagnose/locks')) return mockLocks()
  if (path.startsWith('/api/diagnose/connection')) return mockTestConnection()
  if (path.startsWith('/api/diagnose/space')) return mockSpace(Number(url.searchParams.get('top')) || 20)
  if (path.startsWith('/api/diagnose/connections')) return mockConnections()
  if (path.startsWith('/api/inspector/report')) return mockInspectorReport()
  if (path.startsWith('/api/monitor/anomalies')) return mockAnomalies(Number(url.searchParams.get('hours')) || 6)
  if (path.startsWith('/api/monitor/capacity')) return mockCapacity(url.searchParams.get('resource') || 'disk')
  if (path.startsWith('/api/monitor/trends')) return mockTrends()
  if (path.startsWith('/api/backup') && method === 'POST') return mockCreateBackup()
  if (path.startsWith('/api/backups')) return mockBackups()
  if (path.startsWith('/api/tasks') && path.endsWith('/types')) return mockTaskTypes()
  if (path.startsWith('/api/tasks') && method === 'POST') return { success: true, id: Date.now(), message: '任务已创建（演示模式）' }
  if (path.startsWith('/api/tasks') && method === 'DELETE') return { success: true, message: '任务已删除（演示模式）' }
  if (path.match(/\/api\/tasks\/\d+\/toggle/)) return { success: true, is_enabled: true, message: '任务状态已切换（演示模式）' }
  if (path.startsWith('/api/tasks')) return mockTasks()
  if (path.startsWith('/api/logs')) return mockLogs(Number(url.searchParams.get('hours')) || 24)
  if (path.startsWith('/api/databases')) return mockDatabasesList()
  if (path.startsWith('/api/config/databases') && method === 'GET') return mockDbConfigs()
  if (path.startsWith('/api/config/databases') && method === 'POST') return mockAddDbConfig(params)
  if (path.match(/\/api\/config\/databases\/\w+/) && method === 'PUT') return mockUpdateDbConfig(path.split('/').pop() || '', params)
  if (path.match(/\/api\/config\/databases\/\w+/) && method === 'DELETE') return mockDeleteDbConfig(path.split('/').pop() || '')
  if (path.startsWith('/api/config/databases/test')) return mockTestConnection()
  if (path.startsWith('/api/sql/execute') && method === 'POST') return mockExecuteSQL(url.searchParams.get('sql') || 'select 1')
  if (path.startsWith('/api/sql/schema')) return mockSchema(url.searchParams.get('table') || undefined)
  if (path.startsWith('/api/alerts/stats')) return mockAlertStats()
  if (path.startsWith('/api/alerts/history')) return mockAlerts()
  if (path.match(/\/api\/alerts\/\d+\/resolve/)) return { success: true, message: '告警已解决（演示模式）' }
  if (path.match(/\/api\/alerts\/\d+\/acknowledge/)) return { success: true, message: '告警已确认（演示模式）' }
  if (path.startsWith('/api/alerts/resolve-all')) return { success: true, resolved_count: 3 }
  if (path.startsWith('/api/alerts')) return mockAlerts()
  if (path.startsWith('/api/auth/users') && method === 'GET') return mockUsers()
  if (path.match(/\/api\/auth\/users\/\d+\/role/)) return { success: true, message: '角色已更新（演示模式）' }
  if (path.match(/\/api\/auth\/users\/\d+\/toggle/)) return { success: true, is_active: true, message: '用户状态已切换（演示模式）' }
  if (path.startsWith('/api/auth/me')) return { id: 1, username: 'demo', role: 'admin', email: 'demo@example.com', last_login: new Date().toISOString() }
  if (path.startsWith('/api/auth/login') && method === 'POST') return { access_token: 'demo-token', token_type: 'bearer', username: 'demo', role: 'admin' }
  if (path.startsWith('/api/auth/register')) return { access_token: 'demo-token', token_type: 'bearer', username: params.username, role: 'editor' }
  if (path.startsWith('/api/auth/logout')) return { success: true, message: '已退出登录' }

  // 兜底
  return { success: true, message: '演示模式（模拟数据）' }
}