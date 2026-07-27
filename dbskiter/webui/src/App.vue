<script setup lang="ts">
import { ref, inject, computed, h } from 'vue'
import {
  NConfigProvider, NMessageProvider, NDialogProvider, NNotificationProvider,
  NLayout, NLayoutHeader, NLayoutSider, NLayoutContent, NLayoutFooter,
  NMenu, NIcon, NSwitch, NSpace, NSelect, NText, NSpin, darkTheme,
  zhCN, dateZhCN,
} from 'naive-ui'
import { RouterView, useRoute, useRouter } from 'vue-router'
import {
  SpeedometerOutline, SearchOutline, FlashOutline,
  CloudUploadOutline, ShieldCheckmarkOutline, TimeOutline,
  ServerOutline, SettingsOutline, MoonOutline,
  SunnyOutline, NotificationsOutline, CodeSlashOutline,
} from '@vicons/ionicons5'
import { useUserStore } from '@/stores/user'
import { useDatabaseStore } from '@/stores/database'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const databaseStore = useDatabaseStore()
const message = inject('naive-message') as any

const collapsed = ref(false)
const showNotifications = ref(false)

// 菜单配置
const menuOptions = [
  { label: '仪表盘', key: '/', icon: () => h(NIcon, null, { default: () => h(SpeedometerOutline) }) },
  { label: '诊断', key: '/diagnose', icon: () => h(NIcon, null, { default: () => h(SearchOutline) }) },
  { label: '慢查询', key: '/slow-queries', icon: () => h(NIcon, null, { default: () => h(FlashOutline) }) },
  { label: '安全审计', key: '/security', icon: () => h(NIcon, null, { default: () => h(ShieldCheckmarkOutline) }) },
  { label: '备份管理', key: '/backup', icon: () => h(NIcon, null, { default: () => h(CloudUploadOutline) }) },
  { label: '任务调度', key: '/scheduler', icon: () => h(NIcon, null, { default: () => h(TimeOutline) }) },
  { label: '数据库', key: '/databases', icon: () => h(NIcon, null, { default: () => h(ServerOutline) }) },
  { label: '配置', key: '/configuration', icon: () => h(NIcon, null, { default: () => h(SettingsOutline) }) },
]

// 顶部下拉菜单
const databaseOptions = computed(() =>
  databaseStore.databases.map(d => ({ label: d, value: d }))
)

function handleMenuSelect(key: string) {
  router.push(key)
}

function handleDbChange(value: string) {
  databaseStore.setCurrent(value)
  message?.success(`已切换到 ${value}`)
  // 通知当前页面刷新
  window.dispatchEvent(new CustomEvent('db-changed', { detail: value }))
}

function toggleTheme() {
  userStore.toggleTheme()
  message?.info(userStore.isDark ? '已切换到暗色模式' : '已切换到亮色模式')
}
</script>

<template>
  <NConfigProvider
    :theme="userStore.isDark ? darkTheme : null"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <NMessageProvider>
      <NDialogProvider>
        <NNotificationProvider>
          <NLayout has-sider style="height: 100vh">
            <!-- 侧边栏 -->
            <NLayoutSider
              bordered
              collapse-mode="width"
              :collapsed-width="64"
              :width="240"
              :native-scrollbar="false"
              show-trigger="bar"
              v-model:collapsed="collapsed"
            >
              <div class="logo" :class="{ collapsed }">
                <span class="logo-icon">🗄️</span>
                <span v-if="!collapsed" class="logo-text">DBSKiter</span>
              </div>
              <NMenu
                :value="route.path"
                :options="menuOptions"
                :collapsed="collapsed"
                :collapsed-width="64"
                :collapsed-icon-size="22"
                @update:value="handleMenuSelect"
              />
            </NLayoutSider>

            <NLayout>
              <!-- 顶部栏 -->
              <NLayoutHeader bordered class="topbar">
                <NSpace align="center" justify="space-between" style="width:100%">
                  <NSpace align="center">
                    <NText depth="3">{{ route.meta?.title || 'DBSKiter' }}</NText>
                  </NSpace>
                  <NSpace align="center" :size="12">
                    <NSelect
                      :value="databaseStore.current"
                      :options="databaseOptions"
                      size="small"
                      style="width: 180px"
                      @update:value="handleDbChange"
                    />
                    <NText code style="font-size:12px">v{{ userStore.version }}</NText>
                    <NSwitch
                      :value="userStore.isDark"
                      @update:value="toggleTheme"
                      size="small"
                    >
                      <template #icon>
                        <MoonOutline v-if="userStore.isDark" />
                        <SunnyOutline v-else />
                      </template>
                    </NSwitch>
                    <NButton text>
                      <template #icon>
                        <NotificationsOutline />
                      </template>
                    </NButton>
                    <NButton text tag="a" href="/docs" target="_blank">
                      <template #icon>
                        <CodeSlashOutline />
                      </template>
                      API
                    </NButton>
                  </NSpace>
                </NSpace>
              </NLayoutHeader>

              <!-- 主内容 -->
              <NLayoutContent content-style="padding: 24px;" :native-scrollbar="false">
                <RouterView v-slot="{ Component }">
                  <transition name="fade" mode="out-in">
                    <component :is="Component" />
                  </transition>
                </RouterView>
              </NLayoutContent>

              <!-- 底部 -->
              <NLayoutFooter bordered class="footer">
                <NText depth="3" style="font-size:12px">
                  DBSKiter v{{ userStore.version }} · 数据库 AIOps 运维助手
                </NText>
              </NLayoutFooter>
            </NLayout>
          </NLayout>
        </NNotificationProvider>
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style scoped>
.logo {
  height: 56px; display: flex; align-items: center; gap: 8px;
  padding: 0 20px; border-bottom: 1px solid var(--border-color, #eee);
}
.logo.collapsed { padding: 0; justify-content: center; }
.logo-icon { font-size: 24px; }
.logo-text { font-weight: 700; font-size: 18px; color: var(--primary-color, #4F46E5); }

.topbar { padding: 0 24px; height: 56px; }
.footer { padding: 12px 24px; text-align: center; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>