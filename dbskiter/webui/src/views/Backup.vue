<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, formatBytes, severityClass } from '@/api'
import type { BackupRecord } from '@/types'

const db = ref('default')
const backupType = ref('full')
const tables = ref('')
const backups = ref<BackupRecord[]>([])
const loading = ref(false)
const error = ref('')
const resultMsg = ref('')
const resultClass = ref('')

async function createBackup() {
  error.value = ''
  resultMsg.value = '备份中...'
  resultClass.value = 'status-loading'
  try {
    const data = await api.createBackup(db.value, backupType.value, tables.value || undefined)
    if (data.success) {
      resultClass.value = 'success'
      resultMsg.value = `备份成功！\nID: ${data.backup_id}\n文件: ${data.file_path}\n大小: ${formatBytes(data.file_size)}`
    } else {
      resultClass.value = 'error'
      resultMsg.value = `备份失败: ${data.error || '未知错误'}`
    }
    await loadBackups()
  } catch (e: any) {
    resultClass.value = 'error'
    resultMsg.value = `错误: ${e.message}`
  }
}

async function loadBackups() {
  loading.value = true
  try {
    const data = await api.listBackups(db.value)
    backups.value = data.backups || []
  } catch { /* 静默 */ }
  finally { loading.value = false }
}

onMounted(loadBackups)
</script>

<template>
  <div class="card">
    <h2>💾 创建备份</h2>
    <div class="toolbar">
      <label>数据库：</label>
      <input v-model="db" style="max-width:200px" />
      <label>类型：</label>
      <select v-model="backupType">
        <option value="full">全量备份</option>
        <option value="table">表级备份</option>
      </select>
      <label>表名：</label>
      <input v-model="tables" placeholder="users,orders" style="max-width:200px" />
      <button class="btn-primary" @click="createBackup" :disabled="loading">开始备份</button>
    </div>
    <div v-if="resultMsg" :class="resultClass" style="margin-top:12px;white-space:pre-line;">{{ resultMsg }}</div>
  </div>

  <div class="card">
    <h2>备份记录</h2>
    <table>
      <thead><tr><th>备份 ID</th><th>类型</th><th>文件路径</th><th>大小</th><th>状态</th></tr></thead>
      <tbody>
        <tr v-if="backups.length === 0"><td colspan="5" style="text-align:center;color:#64748b;">暂无备份记录</td></tr>
        <tr v-for="b in backups" :key="b.backup_id || b.file_path">
          <td><code>{{ b.backup_id || '-' }}</code></td>
          <td>{{ b.backup_type || 'full' }}</td>
          <td>{{ b.file_path || '-' }}</td>
          <td>{{ formatBytes(b.file_size || 0) }}</td>
          <td><span :class="'badge ' + (b.success ? 'badge-low' : 'badge-critical')">{{ b.success ? 'success' : 'failed' }}</span></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>