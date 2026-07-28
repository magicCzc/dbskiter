<script setup lang="ts">
/**
 * TopBar — 顶部栏(Bytebase 风格)
 * 左:面包屑 + 折叠按钮; 右:数据库选择器 + 主题切换 + 用户菜单
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDatabaseStore } from '@/stores/database'
import { useUserStore } from '@/stores/user'
import { ElMessageBox } from 'element-plus'
import { Moon, Sunny, Bell, Expand, Fold } from '@element-plus/icons-vue'

const route = useRoute()
const auth = useAuthStore()
const dbStore = useDatabaseStore()
const userStore = useUserStore()

const pageTitle = computed(() => (route.meta?.title as string) || '')

const dbOptions = computed(() =>
  dbStore.databases.map(d => ({ label: d, value: d }))
)

function handleDbChange(val: string) {
  dbStore.setCurrent(val)
  window.dispatchEvent(new CustomEvent('db-changed', { detail: val }))
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出', {
      confirmButtonText: '退出', cancelButtonText: '取消', type: 'info',
    })
    auth.logout()
    window.location.href = '/login'
  } catch { /* 用户取消 */ }
}

const emit = defineEmits<{
  toggleSidebar: []
}>()
</script>

<template>
  <el-header class="topbar">
    <div class="topbar__left">
      <el-button text class="topbar__toggle" @click="emit('toggleSidebar')">
        <el-icon size="18"><Fold /></el-icon>
      </el-button>
      <span class="topbar__title">{{ pageTitle }}</span>
    </div>

    <div class="topbar__right">
      <!-- 数据库选择器 -->
      <el-select
        :model-value="dbStore.current"
        size="small"
        style="width: 180px"
        @change="handleDbChange"
        class="topbar__db-select"
      >
        <el-option
          v-for="o in dbOptions"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>

      <!-- 主题切换 -->
      <el-button text @click="userStore.toggleTheme()">
        <el-icon size="18">
          <Moon v-if="userStore.isDark" />
          <Sunny v-else />
        </el-icon>
      </el-button>

      <!-- 通知 -->
      <el-button text>
        <el-icon size="18"><Bell /></el-icon>
      </el-button>

      <!-- 用户菜单 -->
      <el-dropdown v-if="auth.isLoggedIn" trigger="click" class="topbar__user">
        <el-button text size="small">
          <el-avatar :size="24" class="topbar__avatar">{{ auth.username?.[0]?.toUpperCase() }}</el-avatar>
          <span class="topbar__username">{{ auth.username }}</span>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>
              <span class="text-secondary">{{ auth.role }}</span>
            </el-dropdown-item>
            <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <!-- 版本号 -->
      <span class="topbar__version">v{{ userStore.version }}</span>
    </div>
  </el-header>
</template>

<style scoped>
.topbar {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-elevated);
  flex-shrink: 0;
}

.topbar__left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}
.topbar__toggle {
  color: var(--text-secondary);
  padding: var(--space-1);
}
.topbar__title {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topbar__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.topbar__db-select {
  margin-right: var(--space-1);
}

.topbar__user {
  margin-left: var(--space-1);
}
.topbar__avatar {
  background: var(--color-brand-500);
  color: var(--text-on-brand);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  vertical-align: middle;
  margin-right: var(--space-1);
}
.topbar__username {
  font-size: var(--text-sm);
  color: var(--text-primary);
}
.topbar__version {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  padding-left: var(--space-2);
  border-left: 1px solid var(--border-default);
}
</style>