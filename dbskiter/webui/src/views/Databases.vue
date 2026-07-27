<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  NCard, NButton, NSpace, NSelect, NText, NGrid, NGi, NStatistic,
  NTag, NEmpty, NSpin, NAlert, NIcon, NDataTable,
} from 'naive-ui'
import { ServerOutline, ReloadOutline } from '@vicons/ionicons5'
import { api } from '@/api'
import { useDatabaseStore } from '@/stores/database'

const dbStore = useDatabaseStore()

interface DbInfo {
  name: string
  status: 'unknown' | 'online' | 'offline'
  message: string
}

const databases = ref<DbInfo[]>([])
const loading = ref(false)
const testing = ref(false)

async function loadDatabases() {
  loading.value = true
  try {
    const dbs = await api.databases()
    databases.value = (dbs.databases || ['default']).map(name => ({
      name, status: 'unknown' as const, message: '未检测',
    }))
  } catch { /* 静默 */ }
  finally { loading.value = false }
}

async function testOne(name: string) {
  const db = databases.value.find(d => d.name === name)
  if (!db) return
  db.status = 'unknown'
  db.message = '检测中...'
  try {
    const resp = await fetch(`/api/diagnose/connection?database=${encodeURIComponent(name)}`)
    const data = await resp.json()
    db.status = data.success ? 'online' : 'offline'
    db.message = data.message || (data.success ? '连接正常' : '连接失败')
    if (data.success) console.log("SUCCESS:", `${name}: 连接正常`)
    else console.warn("WARN:", `${name}: ${data.message}`)
  } catch {
    db.status = 'offline'
    db.message = '请求失败'
  }
}

async function testAll() {
  testing.value = true
  for (const db of databases.value) {
    await testOne(db.name)
  }
  testing.value = false
}

onMounted(loadDatabases)
</script>

<template>
  <NSpace vertical :size="16">
    <NCard>
      <NSpace align="center" justify="space-between">
        <NSpace align="center">
          <NIcon size="20" color="#4F46E5"><ServerOutline /></NIcon>
          <NText style="font-weight:600;font-size:16px">数据库管理</NText>
        </NSpace>
        <NSpace align="center">
          <NButton size="small" :loading="testing" @click="testAll">
            <template #icon><NIcon><ReloadOutline /></NIcon></template>
            全部检测
          </NButton>
        </NSpace>
      </NSpace>
    </NCard>

    <div v-if="loading" class="loading" style="padding:40px;text-align:center;color:var(--text-secondary)">加载中...</div>

    <div v-else class="db-grid">
      <NCard v-for="db in databases" :key="db.name" :hoverable="true" size="small" class="db-card">
        <NSpace vertical :size="12">
          <NSpace align="center" justify="space-between">
            <NSpace align="center">
              <span style="font-size:24px">{{ db.status === 'online' ? '🟢' : db.status === 'offline' ? '🔴' : '⚪' }}</span>
              <NText strong style="font-size:16px">{{ db.name }}</NText>
            </NSpace>
            <NTag :type="db.status === 'online' ? 'success' : db.status === 'offline' ? 'error' : 'default'" size="small">
              {{ db.status === 'online' ? '在线' : db.status === 'offline' ? '离线' : '未知' }}
            </NTag>
          </NSpace>
          <NText depth="3" style="font-size:13px;background:var(--table-hover);padding:8px 12px;border-radius:6px;display:block">
            {{ db.message }}
          </NText>
          <NButton size="tiny" :loading="testing" @click="testOne(db.name)">检测连接</NButton>
        </NSpace>
      </NCard>

      <NCard v-if="databases.length === 0" style="text-align:center;padding:40px">
        <NEmpty description="暂无已配置的数据库" />
      </NCard>
    </div>
  </NSpace>
</template>

<style scoped>
.db-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
</style>