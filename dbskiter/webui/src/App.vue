<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useDatabaseStore } from '@/stores/database'
import { useAuthStore } from '@/stores/auth'
import SidebarMenu from '@/components/SidebarMenu.vue'
import TopBar from '@/components/TopBar.vue'
import DemoBanner from '@/components/DemoBanner.vue'

const route = useRoute()
const userStore = useUserStore()
const databaseStore = useDatabaseStore()
const auth = useAuthStore()

const isLoginPage = computed(() => route.path === '/login')
const sidebarCollapsed = ref(false)

databaseStore.loadDatabases()

function handleResize() {
  if (window.innerWidth < 768) sidebarCollapsed.value = true
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  handleResize()
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
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
        <SidebarMenu
          :collapsed="sidebarCollapsed"
          @update:collapsed="sidebarCollapsed = $event"
        />
        <el-container>
          <TopBar @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed" />
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
            DBSKiter v{{ userStore.version }} ·
            <a href="/docs" target="_blank">API 文档</a> ·
            <a href="https://github.com/magicCzc/dbskiter" target="_blank">GitHub</a>
          </el-footer>
        </el-container>
      </el-container>
    </template>
  </div>
</template>

<style>
.main-content {
  background: var(--bg-page);
  padding: var(--space-6);
  overflow-y: auto;
}

.footer {
  height: var(--footer-height);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  border-top: 1px solid var(--border-default);
  background: var(--bg-elevated);
  gap: var(--space-2);
  flex-shrink: 0;
}
.footer a {
  color: var(--text-link);
  text-decoration: none;
  transition: color var(--transition-fast);
}
.footer a:hover {
  color: var(--color-brand-700);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-normal);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>