<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useDatabaseStore } from '@/stores/database'
import { useAuthStore } from '@/stores/auth'
import { ElMessageBox } from 'element-plus'
import { IS_DEMO } from '@/mock'
import {
  Monitor, Search, Warning, WarningFilled, Download,
  Clock, Monitor as ServerIcon, Setting, Expand, Fold, Moon, Sunny,
  Bell, Lock, DataBoard, Connection, DataLine, Document, EditPen,
  Timer,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const databaseStore = useDatabaseStore()
const auth = useAuthStore()
const isCollapsed = ref(false)
const isMobile = ref(false)

const isLoginPage = computed(() => route.path === '/login')

const menuGroups = [
  {
    title: '监控',
    items: [
      { path: '/', label: '仪表盘', icon: Monitor },
      { path: '/diagnose', label: '诊断', icon: Search },
      { path: '/alerts', label: '告警管理', icon: WarningFilled },
      { path: '/anomalies', label: '异常检测', icon: WarningFilled },
      { path: '/capacity', label: '容量预测', icon: DataLine },
    ],
  },
  {
    title: '分析',
    items: [
      { path: '/slow-queries', label: '慢查询', icon: Warning },
      { path: '/locks', label: '锁分析', icon: Lock },
      { path: '/space', label: '空间分析', icon: DataBoard },
      { path: '/security', label: '安全审计', icon: WarningFilled },
      { path: '/inspector', label: '巡检报告', icon: Document },
    ],
  },
  {
    title: '管理',
    items: [
      { path: '/connections', label: '连接管理', icon: Connection },
      { path: '/backup', label: '备份管理', icon: Download },
      { path: '/scheduler', label: '任务调度', icon: Clock },
      { path: '/history', label: '操作历史', icon: Timer },
      { path: '/databases', label: '数据库', icon: ServerIcon },
      { path: '/users', label: '用户管理', icon: ServerIcon },
    ],
  },
  {
    title: '工具',
    items: [
      { path: '/sql-editor', label: 'SQL 编辑器', icon: EditPen },
      { path: '/configuration', label: '系统配置', icon: Setting },
    ],
  },
]

const dbOptions = computed(() =>
  databaseStore.databases.map(d => ({ label: d, value: d }))
)

function handleDbChange(val: string) {
  databaseStore.setCurrent(val)
  window.dispatchEvent(new CustomEvent('db-changed', { detail: val }))
}

databaseStore.loadDatabases()

function handleResize() {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) isCollapsed.value = true
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  handleResize()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出', {
      confirmButtonText: '退出', cancelButtonText: '取消', type: 'info',
    })
    auth.logout()
    router.push('/login')
  } catch { /* 用户取消 */ }
}
</script>

<template>
  <div :class="['app-container', { dark: userStore.isDark }]">
    <!-- 登录页：不显示侧边栏和顶栏 -->
    <template v-if="isLoginPage">
      <router-view />
    </template>

    <!-- 主应用 -->
    <template v-else>
    <el-container style="height: 100vh">
      <!-- 演示模式横幅 -->
      <div v-if="IS_DEMO" class="demo-banner">
        🎮 演示模式 · 所有数据为模拟数据 ·
        <a href="https://magiczc.github.io/dbskiter" target="_blank" style="color:inherit;text-decoration:underline">返回文档 ↗</a>
      </div>
      <el-aside :width="isCollapsed ? '64px' : '220px'" class="sidebar" :style="{ marginTop: IS_DEMO ? '32px' : '0' }">
        <div class="logo" :class="{ collapsed: isCollapsed }">
          <span class="logo-icon">🗄️</span>
          <span v-if="!isCollapsed" class="logo-text">DBSKiter</span>
        </div>
        <el-menu :default-active="route.path" :collapse="isCollapsed" :router="true" class="sidebar-menu">
          <template v-for="group in menuGroups" :key="group.title">
            <el-menu-item-group v-if="!isCollapsed" :title="group.title">
              <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
                <el-icon><component :is="item.icon" /></el-icon>
                <template #title>{{ item.label }}</template>
              </el-menu-item>
            </el-menu-item-group>
            <template v-else>
              <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
                <el-icon><component :is="item.icon" /></el-icon>
              </el-menu-item>
            </template>
          </template>
        </el-menu>
        <div class="collapse-btn" @click="isCollapsed = !isCollapsed">
          <el-icon><Fold v-if="!isCollapsed" /><Expand v-else /></el-icon>
        </div>
      </el-aside>

      <el-container>
        <el-header class="topbar" :style="{ marginTop: IS_DEMO ? '32px' : '0' }">
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
            <!-- 用户信息 -->
            <el-dropdown v-if="auth.isLoggedIn" trigger="click">
              <el-button text size="small">
                <span style="margin-right:4px">👤</span>
                {{ auth.username }}
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item disabled>角色: {{ auth.role }}</el-dropdown-item>
                  <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-tag size="small" type="info" effect="plain">v{{ userStore.version }}</el-tag>
          </div>
        </el-header>

        <el-main class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <keep-alive :max="10">
                <component :is="Component" />
              </keep-alive>
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
    </template>
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
.sidebar-menu { flex: 1; border-right: none; overflow-y: auto; overflow-x: hidden; }
.sidebar-menu::-webkit-scrollbar { width: 4px; }
.sidebar-menu::-webkit-scrollbar-thumb { background: var(--el-border-color-light); border-radius: 2px; }
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

.demo-banner {
  position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
  height: 32px; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #fff; font-size: 13px; font-weight: 500;
  gap: 8px; cursor: default;
}
</style>