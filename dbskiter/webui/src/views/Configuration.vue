<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  NCard, NButton, NSpace, NSelect, NText, NTag, NAlert, NSpin,
  NIcon, NDivider, NList, NListItem, NThing,
} from 'naive-ui'
import { SettingsOutline, ReloadOutline, CodeSlashOutline, BookOutline } from '@vicons/ionicons5'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'

const dbStore = useDatabaseStore()

const status = ref<any>(null)
const testResult = ref<{ success: boolean; message: string } | null>(null)
const testing = ref(false)
const loading = ref(false)

async function loadStatus() {
  loading.value = true
  try {
    status.value = await api.status()
    await dbStore.loadDatabases()
  } catch { /* 静默 */ }
  finally { loading.value = false }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const resp = await fetch(`/api/diagnose/connection?database=${encodeURIComponent(dbStore.current)}`)
    const data = await resp.json()
    testResult.value = {
      success: data.success,
      message: data.message || (data.success ? '连接成功' : '连接失败：无法连接到数据库'),
    }
    if (data.success) console.log("SUCCESS:", '连接成功')
    else console.warn("WARN:", '连接失败')
  } catch (e: any) {
    testResult.value = { success: false, message: `请求失败: ${e.message}` }
  } finally {
    testing.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <NSpace vertical :size="16">
    <NCard>
      <NSpace align="center">
        <NIcon size="20" color="#4F46E5"><SettingsOutline /></NIcon>
        <NText style="font-weight:600;font-size:16px">系统配置</NText>
      </NSpace>
    </NCard>

    <!-- API 服务状态 -->
    <NCard title="API 服务状态">
      <NList v-if="status">
        <NListItem>
          <template #prefix>🟢</template>
          <NThing title="服务状态" description="运行中" />
        </NListItem>
        <NListItem>
          <template #prefix>📦</template>
          <NThing title="版本" :description="'v' + status.version" />
        </NListItem>
        <NListItem>
          <template #prefix>🔗</template>
          <NThing :title="'API 端点'" :description="status.api_endpoints?.length + ' 个'" />
        </NListItem>
      </NList>
      <div v-else style="padding:20px;text-align:center;color:var(--text-secondary)">加载中...</div>
    </NCard>

    <!-- 连接测试 -->
    <NCard title="🔌 数据库连接测试">
      <NSpace vertical :size="12">
        <NText depth="3">选择一个数据库别名，测试是否能正常连接。</NText>
        <NSpace align="center">
          <NSelect
            :value="dbStore.current"
            :options="dbStore.databases.map((d: string) => ({ label: d, value: d }))"
            style="width:300px" size="small"
            @update:value="(v: string) => dbStore.setCurrent(v)"
          />
          <NButton type="primary" size="small" :loading="testing" @click="testConnection">
            <template #icon><NIcon><ReloadOutline /></NIcon></template>
            测试连接
          </NButton>
        </NSpace>
        <NAlert v-if="testResult" :type="testResult.success ? 'success' : 'error'" closable>
          {{ testResult.message }}
        </NAlert>
      </NSpace>
    </NCard>

    <!-- 已配置数据库 -->
    <NCard title="📋 已配置数据库">
      <NList v-if="dbStore.databases.length">
        <NListItem v-for="d in dbStore.databases" :key="d" @click="dbStore.setCurrent(d)" style="cursor:pointer">
          <template #prefix>🗄️</template>
          <NThing :title="d" :description="d === dbStore.current ? '当前选中' : '点击切换'" />
          <template #suffix>
            <NTag v-if="d === dbStore.current" type="primary" size="small">当前</NTag>
          </template>
        </NListItem>
      </NList>
      <NText v-else depth="3">暂无已配置的数据库</NText>
    </NCard>

    <!-- 快速链接 -->
    <NCard title="快速链接">
      <NSpace>
        <NButton tag="a" href="/docs" target="_blank" ghost>
          <template #icon><NIcon><CodeSlashOutline /></NIcon></template>
          Swagger API 文档
        </NButton>
        <NButton tag="a" href="/redoc" target="_blank" ghost>
          <template #icon><NIcon><BookOutline /></NIcon></template>
          ReDoc 文档
        </NButton>
      </NSpace>
    </NCard>
  </NSpace>
</template>