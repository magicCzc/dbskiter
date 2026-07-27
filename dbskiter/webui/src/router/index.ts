import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '仪表盘', icon: '📊' },
  },
  {
    path: '/slow-queries',
    name: 'SlowQueries',
    component: () => import('@/views/SlowQueries.vue'),
    meta: { title: '慢查询', icon: '🐢' },
  },
  {
    path: '/security',
    name: 'Security',
    component: () => import('@/views/Security.vue'),
    meta: { title: '安全审计', icon: '🔒' },
  },
  {
    path: '/backup',
    name: 'Backup',
    component: () => import('@/views/Backup.vue'),
    meta: { title: '备份管理', icon: '💾' },
  },
  {
    path: '/scheduler',
    name: 'Scheduler',
    component: () => import('@/views/Scheduler.vue'),
    meta: { title: '任务调度', icon: '⏰' },
  },
  {
    path: '/configuration',
    name: 'Configuration',
    component: () => import('@/views/Configuration.vue'),
    meta: { title: '系统配置', icon: '⚙️' },
  },
  {
    path: '/databases',
    name: 'Databases',
    component: () => import('@/views/Databases.vue'),
    meta: { title: '数据库管理', icon: '🗄️' },
  },
  {
    path: '/diagnose',
    name: 'Diagnose',
    component: () => import('@/views/Diagnose.vue'),
    meta: { title: '诊断', icon: '🔍' },
  },
]