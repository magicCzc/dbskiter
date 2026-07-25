<script setup lang="ts">
import { useRoute } from 'vue-router'
import { ref, watch } from 'vue'

const route = useRoute()
const isDark = ref(localStorage.getItem('dbskiter-theme') === 'dark')

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem('dbskiter-theme', isDark.value ? 'dark' : 'light')
}

// 初始化主题
watch(isDark, () => {}, { immediate: true })
document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')

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
    <div class="nav-links">
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
    </div>
    <div class="nav-actions">
      <button class="theme-btn" @click="toggleTheme" :title="isDark ? '切换亮色模式' : '切换暗色模式'">
        {{ isDark ? '☀️' : '🌙' }}
      </button>
    </div>
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
  transition: background 0.3s, border-color 0.3s;
}
.logo {
  font-weight: 700;
  font-size: 18px;
  color: var(--primary);
  margin-right: 16px;
  text-decoration: none;
  white-space: nowrap;
}
.nav-links { display: flex; gap: 2px; flex: 1; overflow-x: auto; }
.nav-actions { margin-left: auto; display: flex; align-items: center; }
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
a:hover { background: var(--table-hover); color: var(--text); }
a.active { background: var(--primary); color: white; }
.nav-icon { font-size: 16px; }
.nav-label { font-size: 13px; }
.theme-btn {
  background: var(--table-hover);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
}
.theme-btn:hover { border-color: var(--primary); }

@media (max-width: 768px) {
  nav { padding: 0 8px; gap: 0; }
  a { padding: 8px 10px; }
  .nav-label { display: none; }
  .nav-icon { font-size: 20px; }
}
</style>