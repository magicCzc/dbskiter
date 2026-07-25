import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
  },
  {
    path: '/slow-queries',
    name: 'SlowQueries',
    component: () => import('@/views/SlowQueries.vue'),
  },
  {
    path: '/security',
    name: 'Security',
    component: () => import('@/views/Security.vue'),
  },
  {
    path: '/backup',
    name: 'Backup',
    component: () => import('@/views/Backup.vue'),
  },
  {
    path: '/scheduler',
    name: 'Scheduler',
    component: () => import('@/views/Scheduler.vue'),
  },
]