<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const navItems = [
  { path: '/', label: '仪表盘', icon: '📊' },
  { path: '/slow-queries', label: '慢查询', icon: '🐢' },
  { path: '/security', label: '安全审计', icon: '🔒' },
  { path: '/backup', label: '备份管理', icon: '💾' },
  { path: '/scheduler', label: '任务调度', icon: '⏰' },
]
</script>

<template>
  <nav>
    <router-link to="/" class="logo">DBSKiter</router-link>
    <router-link
      v-for="item in navItems"
      :key="item.path"
      :to="item.path"
      :class="{ active: route.path === item.path }"
    >
      {{ item.icon }} {{ item.label }}
    </router-link>
  </nav>
</template>

<style scoped>
nav {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  display: flex;
  align-items: center;
  height: 56px;
  gap: 8px;
  box-shadow: var(--shadow);
}
.logo {
  font-weight: 700;
  font-size: 18px;
  color: var(--primary);
  margin-right: 24px;
  text-decoration: none;
}
a {
  padding: 8px 16px;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: var(--radius);
  font-size: 14px;
  transition: all 0.2s;
}
a:hover { background: #f1f5f9; color: var(--text); }
a.active { background: var(--primary); color: white; }
</style>