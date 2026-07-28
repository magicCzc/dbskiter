/**
 * Mock 数据生成器
 *
 * 模拟真实数据库的演示数据，用于 GitHub Pages 静态部署
 * 数据基于 dbskiter/shared/mock_connector.py 中的 TABLES
 */

import type {
  HealthResponse, SlowQueryResponse, SecurityResponse,
  SlowQuery, Risk, BackupRecord, Task, LogEntry,
  AlertItem, DiagnoseResult, ConnectionInfo, SpaceInfo, LockInfo,
  AnomalyInfo, CapacityInfo, TrendResponse, InspectorResponse,
  UserInfo, ScheduledTaskInfo, ApiStatus, DatabasesResponse,
} from '@/types'

// ── 基础数据 ──────────────────────────────────────────────

const FIRST_NAMES = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Henry', 'Ivy', 'Jack', 'Kate', 'Leo', 'Mia', 'Noah', 'Olivia', 'Peter', 'Quinn', 'Ryan', 'Sara', 'Tom']
const LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
const DB_TYPES = ['MySQL 8.0', 'PostgreSQL 15', 'Oracle 19c', 'SQL Server 2022', 'ClickHouse 23', 'MongoDB 7']

const SQL_TEMPLATES = [
  'SELECT * FROM users WHERE created_at > ? AND status = ?',
  'SELECT u.id, u.username, COUNT(o.order_id) as order_count FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id ORDER BY order_count DESC',
  'UPDATE products SET stock = stock - ? WHERE product_id = ?',
  'SELECT * FROM orders WHERE amount > 1000 AND status IN ("completed", "shipped") ORDER BY created_at DESC LIMIT 100',
  'SELECT DATE(created_at) as day, SUM(amount) as revenue FROM orders WHERE created_at >= ? GROUP BY DATE(created_at)',
  'SELECT * FROM audit_logs WHERE user_id = ? AND action = ? ORDER BY created_at DESC LIMIT 50',
  'INSERT INTO notifications (user_id, type, content, created_at) VALUES (?, ?, ?, NOW())',
  'DELETE FROM sessions WHERE last_active < ?',
  'SELECT p.category, AVG(p.price) as avg_price, COUNT(*) as cnt FROM products p GROUP BY p.category',
  'SELECT u.*, p.last_login FROM users u JOIN profiles p ON u.id = p.user_id WHERE u.email LIKE ?',
]

const ISSUE_MESSAGES = [
  'CPU 使用率持续 90% 以上，建议排查慢查询',
  'InnoDB Buffer Pool 命中率仅 87%（建议 ≥ 95%）',
  '存在 5 个未使用的索引，可安全删除',
  '连接数使用率 78%，接近 max_connections 上限',
  '慢查询日志中发现 12 条超过 10 秒的查询',
  '表 users 碎片率 35%，建议 OPTIMIZE TABLE',
  '数据库版本 5.7.30 已停止维护，建议升级到 8.0',
  'binlog 占用磁盘 47GB，建议清理历史日志',
  '存在 3 个无密码的数据库用户',
  '字符集配置不一致（utf8 vs utf8mb4）',
]

// ── 工具函数 ──────────────────────────────────────────────

function randomItem<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function randomFloat(min: number, max: number, decimals = 2): number {
  return parseFloat((Math.random() * (max - min) + min).toFixed(decimals))
}

function randomDate(daysAgo: number): string {
  const date = new Date()
  date.setDate(date.getDate() - randomInt(0, daysAgo))
  return date.toISOString()
}

function formatDate(date: Date): string {
  return date.toISOString().replace('T', ' ').substring(0, 19)
}

// 模拟网络延迟
export function mockDelay(min = 150, max = 500): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, randomInt(min, max)))
}

// ── 数据库配置 ────────────────────────────────────────────

export const MOCK_DATABASES: Record<string, any> = {
  default: {
    host: '127.0.0.1', port: 3306, user: 'root',
    password: '********', database: 'demo_db', dialect: 'mysql+pymysql', pool_size: 5,
  },
  production: {
    host: 'prod-mysql.example.com', port: 3306, user: 'app_user',
    password: '********', database: 'production', dialect: 'mysql+pymysql', pool_size: 20,
  },
  analytics: {
    host: '10.0.5.10', port: 8123, user: 'analyst',
    password: '********', database: 'analytics', dialect: 'clickhouse+clickhouse_driver', pool_size: 10,
  },
  legacy: {
    host: '192.168.1.50', port: 1521, user: 'legacy',
    password: '********', database: 'ORCL', dialect: 'oracle+oracledb', pool_size: 8,
  },
}

// ── 1. 健康检查 ────────────────────────────────────────────

export function mockHealth(database: string = 'default'): HealthResponse {
  const score = randomInt(72, 98)
  const issues: string[] = []
  if (score < 80) issues.push(ISSUE_MESSAGES[0])
  if (score < 90) issues.push(ISSUE_MESSAGES[1])
  if (Math.random() > 0.6) issues.push(ISSUE_MESSAGES[3])

  return {
    status: score >= 90 ? 'HEALTHY' : score >= 75 ? 'WARNING' : 'CRITICAL',
    score,
    issues: issues.slice(0, 3),
    collected_at: new Date().toISOString(),
  }
}

export function mockAllHealth(): { databases: { name: string; status: string; score: number; issues: string[] }[] } {
  const dbs = Object.keys(MOCK_DATABASES)
  return {
    databases: dbs.map(name => {
      const h = mockHealth(name)
      return { name, status: h.status, score: h.score, issues: h.issues }
    }),
  }
}

// ── 2. 慢查询 ──────────────────────────────────────────────

export function mockSlowQueries(top: number = 10, hours: number = 1): SlowQueryResponse {
  const queries: SlowQuery[] = []
  for (let i = 0; i < top; i++) {
    const executionTime = randomFloat(1.2, 30.0)
    const executionCount = randomInt(10, 5000)
    queries.push({
      sql: randomItem(SQL_TEMPLATES),
      execution_time: executionTime,
      execution_count: executionCount,
      avg_time: randomFloat(0.5, executionTime),
      rows_examined: randomInt(1000, 1000000),
    })
  }
  // 按耗时降序
  queries.sort((a, b) => b.execution_time - a.execution_time)
  return { total: queries.length, queries }
}

// ── 3. 安全审计 ────────────────────────────────────────────

export function mockSecurity(): SecurityResponse {
  const risks: Risk[] = [
    {
      severity: 'critical', description: '检测到 3 个无密码数据库账户',
      category: 'permissions', current_value: '3 个用户', recommended_value: '立即禁用或设置强密码',
      module: 'permissions',
    },
    {
      severity: 'high', description: 'root 账户允许从任意主机登录',
      category: 'permissions', current_value: 'root@%',
      recommended_value: '限制为 localhost 或特定 IP',
      module: 'permissions',
    },
    {
      severity: 'high', description: '未启用 SSL/TLS 加密连接',
      category: 'config', current_value: 'have_ssl = DISABLED',
      recommended_value: '启用 SSL 加密',
      module: 'config',
    },
    {
      severity: 'medium', description: '检测到 5 个未使用的索引',
      category: 'performance', current_value: '5 indexes',
      recommended_value: 'DROP INDEX 清理',
      module: 'index',
    },
    {
      severity: 'medium', description: '日志表已积累 30GB 数据',
      category: 'storage', current_value: '30.2 GB',
      recommended_value: '归档 6 个月前的数据',
      module: 'storage',
    },
    {
      severity: 'low', description: '审计日志未配置轮转',
      category: 'config', current_value: 'manual rotation',
      recommended_value: '启用 logrotate',
      module: 'config',
    },
    {
      severity: 'low', description: '存在 2 个使用弱密码的用户',
      category: 'permissions', current_value: 'weak: 2 users',
      recommended_value: '强制修改为强密码',
      module: 'permissions',
    },
  ]
  return {
    total_risks: risks.length,
    critical_count: risks.filter(r => r.severity === 'critical').length,
    high_count: risks.filter(r => r.severity === 'high').length,
    risks,
  }
}

// ── 4. 实时诊断 ────────────────────────────────────────────

export function mockRealtimeDiagnose(database: string = 'default'): DiagnoseResult {
  const issues = mockHealth(database).issues.map((msg, i) => ({
    severity: i === 0 ? 'critical' : 'medium',
    message: msg,
    type: randomItem(['performance', 'config', 'security']),
  }))

  return {
    success: true,
    database,
    score: randomInt(75, 95),
    status: 'WARNING',
    issues,
    ai_hints: {
      recommendations: [
        '优化表 user_profile 的 idx_email 索引',
        '将 max_connections 从 151 提升到 300',
        '启用慢查询日志（slow_query_log = ON）',
      ],
    },
    raw_data: {
      connections: randomInt(50, 140),
      max_connections: 151,
      slow_queries: randomInt(5, 20),
      lock_waits: randomInt(0, 3),
    },
  }
}

// ── 5. TOP SQL ─────────────────────────────────────────────

export function mockTopSql(limit: number = 10): { success: boolean; data: any } {
  return {
    success: true,
    data: {
      top_queries: Array.from({ length: limit }, (_, i) => ({
        id: i + 1,
        sql: randomItem(SQL_TEMPLATES),
        execution_time: randomFloat(0.5, 15.0),
        rows_examined: randomInt(100, 50000),
        user: randomItem(['app_user', 'analyst', 'report_user']),
        database: randomItem(['production', 'analytics', 'reports']),
      })),
    },
  }
}

// ── 6. 锁分析 ──────────────────────────────────────────────

export function mockLocks(): { success: boolean; data: { locks: LockInfo[]; deadlocks: any[] } } {
  return {
    success: true,
    data: {
      locks: [
        {
          blocking_pid: 1234,
          blocked_pid: 5678,
          blocking_query: 'UPDATE users SET last_login = NOW() WHERE id = 100',
          blocked_query: 'SELECT * FROM users WHERE id = 100 FOR UPDATE',
          blocking_duration: 45.2,
          database: 'production',
        },
        {
          blocking_pid: 2345,
          blocked_pid: 6789,
          blocking_query: 'INSERT INTO audit_logs (user_id, action) VALUES (?, ?)',
          blocked_query: 'DELETE FROM sessions WHERE user_id = ?',
          blocking_duration: 12.8,
          database: 'production',
        },
      ],
      deadlocks: [
        {
          time: new Date(Date.now() - 3600000).toISOString(),
          transactions: ['tx-001', 'tx-002'],
        },
      ],
    },
  }
}

// ── 7. 空间分析 ────────────────────────────────────────────

export function mockSpace(top: number = 20): { success: boolean; data: { raw_metrics: any } } {
  const tables = ['users', 'orders', 'products', 'audit_logs', 'sessions', 'notifications',
    'user_profile', 'payment_records', 'order_items', 'inventory', 'messages', 'comments',
    'attachments', 'tags', 'categories', 'addresses', 'coupons', 'refunds', 'reports', 'analytics_events']
  const data: SpaceInfo[] = tables.slice(0, top).map((name, i) => ({
    table_name: name,
    table_schema: i < 3 ? 'public' : 'archive',
    total_size: randomInt(100, 50000),
    data_size: randomInt(80, 40000),
    index_size: randomInt(20, 10000),
    free_space: randomFloat(5, 35),
  }))
  return {
    success: true,
    data: {
      raw_metrics: {
        total_space: 128,
        tables: data,
        table_count: data.length,
      },
    },
  }
}

// ── 8. 连接管理 ────────────────────────────────────────────

export function mockConnections(): { success: boolean; data: { raw_metrics: { connections: ConnectionInfo[]; max_connections: number } } } {
  const states = ['Sleep', 'Sleep', 'Sleep', 'Query', 'Locked', 'Sending data', 'Sorting result']
  const users = ['app_user', 'analyst', 'report_user', 'backup_user']
  const dbs = ['production', 'analytics', 'reports', 'backup']

  const connections: ConnectionInfo[] = Array.from({ length: 87 }, (_, i) => ({
    pid: 1000 + i,
    user: randomItem(users),
    host: `10.0.${randomInt(1, 5)}.${randomInt(1, 254)}:${randomInt(10000, 65535)}`,
    database: randomItem(dbs),
    state: randomItem(states),
    query: i % 5 === 0 ? randomItem(SQL_TEMPLATES) : 'SELECT SLEEP(0.1)',
    duration: randomFloat(0.1, 60),
  }))
  return {
    success: true,
    data: {
      raw_metrics: { connections, max_connections: 151 },
    },
  }
}

// ── 9. 异常检测 ────────────────────────────────────────────

export function mockAnomalies(hours: number = 6): { data: { raw_metrics: { anomalies: AnomalyInfo[] } } } {
  const metrics = ['cpu', 'memory', 'disk', 'qps', 'connections', 'slow_queries']
  const anomalies: AnomalyInfo[] = []
  for (let i = 0; i < 12; i++) {
    const metric = randomItem(metrics)
    anomalies.push({
      metric,
      timestamp: new Date(Date.now() - randomInt(0, hours * 3600) * 1000).toISOString(),
      actual_value: randomFloat(85, 99),
      expected_value: randomFloat(40, 70),
      deviation: randomFloat(15, 50),
      severity: randomItem(['warning', 'warning', 'critical']),
      description: `${metric} 突增超过历史均值 2.5 个标准差`,
    })
  }
  return { data: { raw_metrics: { anomalies } } }
}

// ── 10. 容量预测 ────────────────────────────────────────────

export function mockCapacity(resource: string = 'disk'): { data: CapacityInfo } {
  const usage = randomFloat(60, 85)
  return {
    data: {
      resource,
      current_usage: usage,
      total_capacity: 100,
      growth_rate: randomFloat(0.5, 5.0),
      estimated_exhaustion: new Date(Date.now() + randomInt(30, 365) * 86400000).toISOString().substring(0, 10),
      days_remaining: randomInt(30, 365),
    },
  }
}

// ── 11. 趋势数据 ────────────────────────────────────────────

export function mockTrends(): TrendResponse {
  const hours = 24
  const timestamps: string[] = []
  const cpu: number[] = []
  const memory: number[] = []
  const disk: number[] = []
  const qps: number[] = []

  for (let i = hours - 1; i >= 0; i--) {
    const date = new Date()
    date.setHours(date.getHours() - i)
    timestamps.push(formatDate(date))
    cpu.push(randomFloat(20, 80))
    memory.push(randomFloat(40, 85))
    disk.push(60 + (i / hours) * 10)
    qps.push(randomInt(100, 5000))
  }
  return { timestamps, cpu, memory, disk, qps }
}

// ── 12. 巡检报告 ────────────────────────────────────────────

export function mockInspectorReport(): InspectorResponse {
  return {
    success: true,
    data: {
      raw_metrics: {
        health_score: 87,
        items: [
          { type: 'configuration', status: 'pass', message: '配置参数符合最佳实践' },
          { type: 'configuration', status: 'warning', message: 'binlog 过期时间设置为 30 天，建议 7 天' },
          { type: 'performance', status: 'pass', message: 'QPS 在正常范围内' },
          { type: 'performance', status: 'fail', message: '检测到 5 条慢查询超过 10 秒' },
          { type: 'storage', status: 'pass', message: '磁盘使用率 65%' },
          { type: 'storage', status: 'warning', message: '表 users 碎片率 28%' },
          { type: 'security', status: 'pass', message: '所有用户设置了密码' },
          { type: 'security', status: 'warning', message: '存在 3 个弱密码用户' },
          { type: 'capacity', status: 'pass', message: '连接数使用率 60%' },
          { type: 'replication', status: 'pass', message: '主从同步延迟 < 1s' },
        ],
      },
    },
  }
}

// ── 13. 备份 ──────────────────────────────────────────────

export function mockBackups(): { backups: BackupRecord[] } {
  return {
    backups: Array.from({ length: 6 }, (_, i) => ({
      backup_id: `bk-${Date.now() - i * 86400000}`,
      backup_type: randomItem(['full', 'incremental', 'full', 'full']),
      file_path: `/backups/demo_db_${['full', 'inc'][i % 2]}_${formatDate(new Date(Date.now() - i * 86400000))}.sql.gz`,
      file_size: randomInt(50, 500) * 1024 * 1024,
      success: Math.random() > 0.1,
      created_at: new Date(Date.now() - i * 86400000).toISOString(),
    })),
  }
}

export function mockCreateBackup(): any {
  return {
    success: true,
    backup_id: `bk-${Date.now()}`,
    file_path: `/backups/demo_db_full_${formatDate(new Date())}.sql.gz`,
    file_size: randomInt(80, 300) * 1024 * 1024,
  }
}

// ── 14. 任务 ──────────────────────────────────────────────

export function mockTasks(): { tasks: ScheduledTaskInfo[] } {
  return {
    tasks: [
      { id: 1, name: '每日健康诊断', task_type: 'diagnose', db_alias: 'production', cron_expr: '0 9 * * *', is_enabled: true, last_run: new Date(Date.now() - 86400000).toISOString() },
      { id: 2, name: '周度巡检', task_type: 'inspect', db_alias: 'production', cron_expr: '0 2 * * 0', is_enabled: true, last_run: new Date(Date.now() - 3 * 86400000).toISOString() },
      { id: 3, name: '指标采集', task_type: 'collect', db_alias: 'default', cron_expr: '*/5 * * * *', is_enabled: true, last_run: new Date(Date.now() - 300000).toISOString() },
      { id: 4, name: '月报生成', task_type: 'report', db_alias: 'analytics', cron_expr: '0 10 1 * *', is_enabled: false, last_run: null },
    ],
  }
}

export function mockTaskTypes(): { success: boolean; types: any } {
  return {
    success: true,
    types: {
      diagnose: { label: '定时诊断', description: '定期执行数据库诊断', default_cron: '0 9 * * *' },
      inspect: { label: '定时巡检', description: '定期执行综合巡检', default_cron: '0 2 * * 0' },
      report: { label: '定时报告', description: '定期生成健康报告', default_cron: '0 10 1 * *' },
      collect: { label: '指标采集', description: '定期采集数据库指标', default_cron: '*/5 * * * *' },
    },
  }
}

// ── 15. SQL 执行 ────────────────────────────────────────────

export function mockExecuteSQL(sql: string): any {
  const sqlLower = sql.toLowerCase().trim()
  if (sqlLower.startsWith('select')) {
    return {
      success: true,
      execution_time: randomFloat(0.001, 0.5),
      row_count: randomInt(5, 100),
      columns: ['id', 'name', 'value', 'created_at'],
      rows: Array.from({ length: 8 }, (_, i) => [
        i + 1,
        randomItem(FIRST_NAMES) + ' ' + randomItem(LAST_NAMES),
        randomInt(100, 9999),
        formatDate(new Date(Date.now() - i * 86400000)),
      ]),
    }
  }
  return {
    success: true,
    execution_time: randomFloat(0.001, 0.2),
    row_count: 0,
    columns: [],
    rows: [],
  }
}

export function mockSchema(table?: string): any {
  if (table) {
    return {
      success: true,
      table,
      columns: [
        { name: 'id', type: 'INT', nullable: false, default: 'AUTO_INCREMENT' },
        { name: 'name', type: 'VARCHAR(100)', nullable: false },
        { name: 'email', type: 'VARCHAR(255)', nullable: true },
        { name: 'created_at', type: 'DATETIME', nullable: false, default: 'CURRENT_TIMESTAMP' },
      ],
      indexes: [
        { name: 'PRIMARY', columns: ['id'], unique: true },
        { name: 'idx_email', columns: ['email'], unique: false },
      ],
    }
  }
  return {
    success: true,
    tables: ['users', 'orders', 'products', 'audit_logs', 'sessions', 'notifications', 'user_profile', 'payment_records'],
  }
}

// ── 16. 告警 ──────────────────────────────────────────────

export function mockAlerts(): { alerts: AlertItem[]; total: number } {
  return {
    total: 4,
    alerts: [
      { id: 1, db_alias: 'production', metric: 'cpu', level: 'critical', current_value: 94, threshold: 90, message: 'CPU 使用率 94.2%，超过阈值 90%', status: 'open', created_at: new Date(Date.now() - 600000).toISOString() },
      { id: 2, db_alias: 'production', metric: 'memory', level: 'warning', current_value: 82, threshold: 80, message: '内存使用率 82.0%，超过阈值 80%', status: 'open', created_at: new Date(Date.now() - 1800000).toISOString() },
      { id: 3, db_alias: 'analytics', metric: 'disk', level: 'warning', current_value: 88, threshold: 85, message: '磁盘使用率 88.0%，超过阈值 85%', status: 'acknowledged', created_at: new Date(Date.now() - 7200000).toISOString() },
      { id: 4, db_alias: 'default', metric: 'connections', level: 'warning', current_value: 78, threshold: 75, message: '连接数使用率 78.0%', status: 'open', created_at: new Date(Date.now() - 10800000).toISOString() },
    ],
  }
}

export function mockAlertStats(): { stats: any } {
  return {
    stats: { total: 12, open: 4, critical: 1, warning: 3 },
  }
}

// ── 17. 操作历史 ────────────────────────────────────────────

export function mockLogs(hours: number = 24): { logs: LogEntry[] } {
  const commands = ['diagnose', 'monitor', 'security', 'sql', 'inspector']
  const actions = ['realtime', 'health', 'audit', 'execute', 'anomalies', 'capacity', 'inspect', 'report']
  const dbs = ['default', 'production', 'analytics', 'legacy']
  const logs: LogEntry[] = Array.from({ length: 30 }, (_, i) => ({
    timestamp: new Date(Date.now() - i * 1800000).toISOString(),
    command: randomItem(commands),
    action: randomItem(actions),
    database: randomItem(dbs),
    status_code: Math.random() > 0.05 ? 0 : 1,
    execution_time_ms: randomInt(50, 5000),
    args: { hours: randomInt(1, 24), top: randomInt(5, 50) },
  }))
  return { logs }
}

// ── 18. 用户管理 ────────────────────────────────────────────

export function mockUsers(): { users: UserInfo[] } {
  return {
    users: [
      { id: 1, username: 'admin', email: 'admin@example.com', role: 'admin', is_active: true, created_at: '2026-01-15', last_login: new Date(Date.now() - 3600000).toISOString() },
      { id: 2, username: 'alice', email: 'alice@example.com', role: 'editor', is_active: true, created_at: '2026-03-20', last_login: new Date(Date.now() - 7200000).toISOString() },
      { id: 3, username: 'bob', email: 'bob@example.com', role: 'editor', is_active: true, created_at: '2026-04-10', last_login: new Date(Date.now() - 86400000).toISOString() },
      { id: 4, username: 'viewer1', email: 'viewer1@example.com', role: 'viewer', is_active: true, created_at: '2026-05-01', last_login: null },
      { id: 5, username: 'old_user', email: 'old@example.com', role: 'viewer', is_active: false, created_at: '2025-12-01', last_login: new Date(Date.now() - 30 * 86400000).toISOString() },
    ],
  }
}

// ── 19. 数据库列表 ────────────────────────────────────────────

export function mockDatabasesList(): DatabasesResponse {
  return { databases: Object.keys(MOCK_DATABASES) }
}

// ── 20. 测试连接 ────────────────────────────────────────────

export function mockTestConnection(): any {
  return {
    success: true,
    database: 'default',
    message: '连接成功 🎉 (演示模式)',
  }
}

// ── 21. 状态 ──────────────────────────────────────────────

export function mockStatus(): ApiStatus {
  return {
    status: 'ok',
    version: '3.0.43-demo',
    api_endpoints: [
      '/api/health', '/api/health/all', '/api/slow-queries', '/api/security',
      '/api/diagnose/realtime', '/api/diagnose/top', '/api/diagnose/locks',
      '/api/inspector/report', '/api/backup', '/api/backups', '/api/tasks',
      '/api/logs', '/api/databases', '/api/monitor/anomalies', '/api/monitor/capacity',
      '/api/monitor/trends', '/api/sql/execute', '/api/sql/schema',
      '/api/config/databases', '/api/config/databases/test',
      '/api/auth/login', '/api/auth/register', '/api/auth/me',
      '/api/auth/users', '/api/alerts', '/api/alerts/stats',
    ],
  }
}

// ── 22. 数据库配置 CRUD ──────────────────────────────────────

export function mockDbConfigs(): { databases: Record<string, any>; count: number } {
  return { databases: MOCK_DATABASES, count: Object.keys(MOCK_DATABASES).length }
}

export function mockAddDbConfig(config: any): any {
  MOCK_DATABASES[config.alias] = { ...config, password: '********' }
  return { success: true, alias: config.alias, message: `数据库 '${config.alias}' 已添加（演示模式）`, connection: mockTestConnection() }
}

export function mockUpdateDbConfig(alias: string, config: any): any {
  MOCK_DATABASES[alias] = { ...MOCK_DATABASES[alias], ...config, password: '********' }
  return { success: true, alias, message: `数据库 '${alias}' 已更新（演示模式）` }
}

export function mockDeleteDbConfig(alias: string): any {
  delete MOCK_DATABASES[alias]
  return { success: true, alias, message: `数据库 '${alias}' 已删除（演示模式）` }
}