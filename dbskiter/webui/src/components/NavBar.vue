<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { path: '/', label: '仪表盘', icon: '📊' },
  { path: '/slow-queries', label: '慢查询', icon: '🐢' },
  { path: '/security', label: '安全审计', icon: '🔒' },
  { path: '/backup', label: '备份管理', icon: '💾' },
  { path: '/scheduler', label: '任务调度', icon: '⏰' },
  { path: '/configuration', label: '配置', icon: '⚙️' },
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
      :title="item.label"
    >
      <span class="nav-icon">{{ item.icon }}</span>
      <span class="nav-label">{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
nav {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 0 16px;
  display: flex;
  align-items: center;
  height: 56px;
  gap: 2px;
  box-shadow: var(--shadow);
  overflow-x: auto;
}
.logo {
  font-weight: 700;
  font-size: 18px;
  color: var(--primary);
  margin-right: 16px;
  text-decoration: none;
  white-space: nowrap;
}
a {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.2s;
  white-space: nowrap;
}
a:hover { background: #f1f5f9; color: var(--text); }
a.active { background: var(--primary); color: white; }
.nav-icon { font-size: 16px; }
.nav-label { font-size: 13px; }

@media (max-width: 768px) {
  nav { padding: 0 8px; gap: 0; }
  a { padding: 8px 10px; }
  .nav-label { display: none; }
  .nav-icon { font-size: 20px; }
}
</style>