<script setup lang="ts">
/**
 * SidebarMenu — 左侧深色侧边栏(Bytebase 风格)
 * 包含 logo、分组菜单、折叠按钮、演示模式标签
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  Monitor, Search, Warning, WarningFilled, Download,
  Clock, Monitor as ServerIcon, Setting, Expand, Fold,
  Bell, Lock, DataBoard, Connection, DataLine, Document, EditPen,
  Timer,
} from '@element-plus/icons-vue'
import DemoBanner from './DemoBanner.vue'

const route = useRoute()

const props = withDefaults(defineProps<{
  collapsed?: boolean
}>(), {
  collapsed: false,
})

const isMobile = ref(false)

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

const sidebarWidth = computed(() =>
  props.collapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)'
)

function handleResize() {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) emit('update:collapsed', true)
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  handleResize()
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

const emit = defineEmits<{
  toggle: []
  (e: 'update:collapsed', val: boolean): void
}>()

function toggle() {
  emit('update:collapsed', !props.collapsed)
}
</script>

<template>
  <el-aside :width="sidebarWidth" class="sidebar">
    <!-- Logo -->
    <div class="sidebar__logo" :class="{ 'sidebar__logo--collapsed': collapsed }">
      <svg class="sidebar__logo-icon" viewBox="0 0 24 24" fill="none" width="22" height="22">
        <rect x="3" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.35"/>
        <rect x="14" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55"/>
        <rect x="3" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55"/>
        <rect x="14" y="14" width="7" height="7" rx="1.5" fill="currentColor"/>
      </svg>
      <span v-if="!collapsed" class="sidebar__logo-text">DBSKiter</span>
    </div>

    <!-- 菜单 -->
    <el-menu
      :default-active="route.path"
      :collapse="collapsed"
      :router="true"
      class="sidebar__menu"
      text-color="var(--text-on-dark)"
      active-text-color="var(--color-gray-0)"
      background-color="var(--bg-sidebar)"
    >
      <template v-for="group in menuGroups" :key="group.title">
        <el-menu-item-group v-if="!collapsed" :title="group.title">
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

    <!-- 底部区域:折叠按钮 + 演示标签 -->
    <div class="sidebar__footer">
      <div class="sidebar__collapse-btn" @click="toggle">
        <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
      </div>
      <DemoBanner />
    </div>
  </el-aside>
</template>

<style scoped>
.sidebar {
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width var(--transition-normal);
  z-index: var(--z-sticky);
}

/* Logo */
.sidebar__logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-4);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  flex-shrink: 0;
}
.sidebar__logo--collapsed {
  justify-content: center;
  padding: 0;
}
.sidebar__logo-icon {
  color: var(--color-brand-400);
  flex-shrink: 0;
}
.sidebar__logo-text {
  font-weight: var(--font-bold);
  font-size: var(--text-lg);
  color: var(--color-gray-0);
  letter-spacing: 0.5px;
}

/* 菜单 */
.sidebar__menu {
  flex: 1;
  border-right: none;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--space-2) 0;
}
.sidebar__menu::-webkit-scrollbar { width: 4px; }
.sidebar__menu::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

/* 覆盖 Element Plus 的菜单组默认样式 */
:deep(.el-menu-item-group__title) {
  color: var(--text-on-dark-mute) !important;
  font-size: var(--text-xs);
  padding: var(--space-3) var(--space-4) var(--space-1);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: var(--font-medium);
}
:deep(.el-menu-item) {
  border-radius: 0;
  margin: 0 var(--space-2);
  padding: 0 var(--space-3);
  height: 36px;
  line-height: 36px;
  font-size: var(--text-sm);
  transition: background var(--transition-fast);
}
:deep(.el-menu-item:hover) {
  background: var(--bg-sidebar-hover) !important;
}
:deep(.el-menu-item.is-active) {
  background: var(--color-brand-600) !important;
  color: var(--color-gray-0) !important;
}

/* 底部 */
.sidebar__footer {
  border-top: 1px solid rgba(255,255,255,0.06);
  flex-shrink: 0;
}
.sidebar__collapse-btn {
  padding: var(--space-3);
  text-align: center;
  cursor: pointer;
  color: var(--text-on-dark-mute);
  transition: color var(--transition-fast);
}
.sidebar__collapse-btn:hover {
  color: var(--color-gray-0);
}
</style>