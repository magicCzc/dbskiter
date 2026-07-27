<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useDatabaseStore } from '@/stores/database'
import {
  Monitor, Search, Warning, WarningFilled, Download,
  Clock, Monitor as ServerIcon, Setting, Expand, Fold, Moon, Sunny,
  Bell,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const databaseStore = useDatabaseStore()
const isCollapsed = ref(false)
const isMobile = ref(window.innerWidth < 768)

window.addEventListener('resize', () => {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) isCollapsed.value = true
})

const menuItems = [
  { path: '/', label: '仪表盘', icon: Monitor },
  { path: '/diagnose', label: '诊断', icon: Search },
  { path: '/slow-queries', label: '慢查询', icon: Warning },
  { path: '/security', label: '安全审计', icon: WarningFilled },
  { path: '/backup', label: '备份管理', icon: Download },
  { path: '/scheduler', label: '任务调度', icon: Clock },
  { path: '/databases', label: '数据库', icon: ServerIcon },
  { path: '/configuration', label: '配置', icon: Setting },
]

const dbOptions = computed(() =>
  databaseStore.databases.map(d => ({ label: d, value: d }))
)

function handleDbChange(val: string) {
  databaseStore.setCurrent(val)
  window.dispatchEvent(new CustomEvent('db-changed', { detail: val }))
}

databaseStore.loadDatabases()
</script>

<template>
  <div :class="['app-container', { dark: userStore.isDark }]">
    <el-container style="height: 100vh">
      <el-aside :width="isCollapsed ? '64px' : '220px'" class="sidebar">
        <div class="logo" :class="{ collapsed: isCollapsed }">
          <span class="logo-icon">🗄️</span>
          <span v-if="!isCollapsed" class="logo-text">DBSKiter</span>
        </div>
        <el-menu :default-active="route.path" :collapse="isCollapsed" :router="true" class="sidebar-menu">
          <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.label }}</template>
          </el-menu-item>
        </el-menu>
        <div class="collapse-btn" @click="isCollapsed = !isCollapsed">
          <el-icon><Fold v-if="!isCollapsed" /><Expand v-else /></el-icon>
        </div>
      </el-aside>

      <el-container>
        <el-header class="topbar">
          <div class="topbar-left">
            <el-button text @click="isCollapsed = !isCollapsed">
              <el-icon size="20"><Fold v-if="!isCollapsed" /><Expand v-else /></el-icon>
            </el-button>
          </div>
          <div class="topbar-right">
            <el-select :model-value="databaseStore.current" size="small" style="width:180px" @change="handleDbChange">
              <el-option v-for="o in dbOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-button text @click="userStore.toggleTheme()">
              <el-icon size="18"><Moon v-if="userStore.isDark" /><Sunny v-else /></el-icon>
            </el-button>
            <el-button text>
              <el-icon size="18"><Bell /></el-icon>
            </el-button>
            <el-tag size="small" type="info" effect="plain">v{{ userStore.version }}</el-tag>
          </div>
        </el-header>

        <el-main class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>

        <el-footer class="footer">
          DBSKiter v{{ userStore.version }} · 数据库 AIOps 运维助手 ·
          <a href="/docs" target="_blank">API 文档</a> ·
          <a href="https://github.com/magicCzc/dbskiter" target="_blank">GitHub</a>
        </el-footer>
      </el-container>
    </el-container>
  </div>
</template>

<style scoped>
.sidebar {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  display: flex; flex-direction: column;
  transition: width var(--transition-normal); overflow: hidden;
}
.logo {
  height: 56px; display: flex; align-items: center; gap: 8px;
  padding: 0 16px; border-bottom: 1px solid var(--el-border-color-light);
}
.logo.collapsed { justify-content: center; padding: 0; }
.logo-icon { font-size: 24px; }
.logo-text { font-weight: 700; font-size: 18px; color: var(--el-color-primary); }
.sidebar-menu { flex: 1; border-right: none; }
.collapse-btn {
  padding: 12px; text-align: center; cursor: pointer;
  border-top: 1px solid var(--el-border-color-light);
  color: var(--el-text-color-secondary); transition: color var(--transition-fast);
}
.collapse-btn:hover { color: var(--el-color-primary); }

.topbar {
  height: 48px; display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px; border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}
.topbar-left, .topbar-right { display: flex; align-items: center; gap: 12px; }

.main-content {
  background: var(--el-bg-color-page);
  padding: 20px; overflow-y: auto;
}
.footer {
  height: 40px; display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: var(--el-text-color-secondary);
  border-top: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}
.footer a { color: var(--el-color-primary); text-decoration: none; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>