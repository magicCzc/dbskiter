import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHashHistory } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', icon: '🔑', noAuth: true },
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '仪表盘', icon: '📊' },
  },
  {
    path: '/diagnose',
    name: 'Diagnose',
    component: () => import('@/views/Diagnose.vue'),
    meta: { title: '诊断', icon: '🔍' },
  },
  {
    path: '/slow-queries',
    name: 'SlowQueries',
    component: () => import('@/views/SlowQueries.vue'),
    meta: { title: '慢查询', icon: '🐢' },
  },
  {
    path: '/locks',
    name: 'LockAnalysis',
    component: () => import('@/views/LockAnalysis.vue'),
    meta: { title: '锁分析', icon: '🔒' },
  },
  {
    path: '/space',
    name: 'SpaceAnalysis',
    component: () => import('@/views/SpaceAnalysis.vue'),
    meta: { title: '空间分析', icon: '💾' },
  },
  {
    path: '/connections',
    name: 'Connections',
    component: () => import('@/views/Connections.vue'),
    meta: { title: '连接管理', icon: '🔌' },
  },
  {
    path: '/security',
    name: 'Security',
    component: () => import('@/views/Security.vue'),
    meta: { title: '安全审计', icon: '🔒' },
  },
  {
    path: '/anomalies',
    name: 'AnomalyDetection',
    component: () => import('@/views/AnomalyDetection.vue'),
    meta: { title: '异常检测', icon: '⚠️' },
  },
  {
    path: '/alerts',
    name: 'Alerts',
    component: () => import('@/views/Alerts.vue'),
    meta: { title: '告警管理', icon: '🔔' },
  },
  {
    path: '/capacity',
    name: 'CapacityPrediction',
    component: () => import('@/views/CapacityPrediction.vue'),
    meta: { title: '容量预测', icon: '📈' },
  },
  {
    path: '/inspector',
    name: 'InspectorReport',
    component: () => import('@/views/InspectorReport.vue'),
    meta: { title: '巡检报告', icon: '📋' },
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
    path: '/databases',
    name: 'Databases',
    component: () => import('@/views/Databases.vue'),
    meta: { title: '数据库管理', icon: '🗄️' },
  },
  {
    path: '/configuration',
    name: 'Configuration',
    component: () => import('@/views/Configuration.vue'),
    meta: { title: '系统配置', icon: '⚙️' },
  },
  {
    path: '/users',
    name: 'Users',
    component: () => import('@/views/Users.vue'),
    meta: { title: '用户管理', icon: '👥' },
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/History.vue'),
    meta: { title: '操作历史', icon: '📜' },
  },
  {
    path: '/sql-editor',
    name: 'SQLEditor',
    component: () => import('@/views/SQLEditor.vue'),
    meta: { title: 'SQL 编辑器', icon: '⌨️' },
  },
]

export const router = createRouter({ history: createWebHashHistory('/ui/'), routes })

// 路由守卫：检查登录状态
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('dbskiter-token')
  if (to.meta.noAuth) {
    next()
  } else if (!token && to.path !== '/login') {
    next('/login')
  } else {
    next()
  }
})
