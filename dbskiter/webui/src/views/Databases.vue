<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'

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
      name,
      status: 'unknown' as const,
      message: '未检测',
    }))
  } catch { /* 静默 */ }
  finally { loading.value = false }
}

async function testAll() {
  testing.value = true
  for (let i = 0; i < databases.value.length; i++) {
    const db = databases.value[i]
    db.status = 'unknown'
    db.message = '检测中...'
    try {
      const resp = await fetch(`/api/diagnose/connection?database=${encodeURIComponent(db.name)}`)
      const data = await resp.json()
      db.status = data.success ? 'online' : 'offline'
      db.message = data.message || (data.success ? '连接正常' : '连接失败')
    } catch {
      db.status = 'offline'
      db.message = '请求失败'
    }
  }
  testing.value = false
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
  } catch {
    db.status = 'offline'
    db.message = '请求失败'
  }
}

const statusIcon = (status: string) => {
  if (status === 'online') return '🟢'
  if (status === 'offline') return '🔴'
  return '⚪'
}

onMounted(loadDatabases)
</script>

<template>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
      <h2 style="margin:0;">🗄️ 数据库管理</h2>
      <div class="toolbar" style="margin-bottom:0;">
        <button class="btn-primary" @click="testAll" :disabled="testing || loading">
          {{ testing ? '检测中...' : '🔄 全部检测' }}
        </button>
        <button class="btn-ghost" @click="loadDatabases" :disabled="loading">刷新列表</button>
      </div>
    </div>
  </div>

  <!-- 加载中 -->
  <div v-if="loading" class="card">
    <div class="loading">加载中...</div>
  </div>

  <!-- 数据库列表 -->
  <div v-else class="db-grid">
    <div v-for="db in databases" :key="db.name" class="db-card">
      <div class="db-header">
        <span class="db-status-icon">{{ statusIcon(db.status) }}</span>
        <span class="db-name">{{ db.name }}</span>
        <span :class="'status status-' + (db.status === 'online' ? 'healthy' : db.status === 'offline' ? 'critical' : 'warning')">
          {{ db.status === 'online' ? '在线' : db.status === 'offline' ? '离线' : '未知' }}
        </span>
      </div>
      <div class="db-message">{{ db.message }}</div>
      <div class="db-actions">
        <button class="btn-sm" @click="testOne(db.name)" :disabled="testing">检测连接</button>
      </div>
    </div>
    <div v-if="databases.length === 0" class="card" style="text-align:center;padding:40px;color:var(--text-secondary);">
      暂无已配置的数据库
    </div>
  </div>
</template>

<style scoped>
.db-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.db-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
  padding: 20px; box-shadow: var(--shadow); transition: all 0.2s;
}
.db-card:hover { border-color: var(--primary); }
.db-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.db-status-icon { font-size: 20px; }
.db-name { font-weight: 600; font-size: 16px; flex: 1; }
.db-message { font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; padding: 8px 12px; background: var(--table-hover); border-radius: 6px; }
.db-actions { display: flex; gap: 8px; }
.btn-sm { padding: 6px 14px; font-size: 13px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-card); cursor: pointer; }
.btn-sm:hover { border-color: var(--primary); }
.btn-ghost { background: transparent; color: var(--text-secondary); border: 1px solid var(--border); padding: 8px 16px; border-radius: 8px; cursor: pointer; }
.btn-ghost:hover { background: var(--table-hover); color: var(--text); }
</style>