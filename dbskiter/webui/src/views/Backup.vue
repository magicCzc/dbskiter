<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, formatBytes } from '@/api'
import type { BackupRecord } from '@/types'

const db = ref('default')
const backupType = ref('full')
const tables = ref('')
const backups = ref<BackupRecord[]>([])
const loading = ref(false)
const result = ref<{ type: string; msg: string } | null>(null)

async function createBackup() {
  result.value = { type: 'loading', msg: '备份执行中...' }
  try {
    const data = await api.createBackup(db.value, backupType.value, tables.value || undefined)
    if (data.success) {
      result.value = { type: 'success', msg: `备份成功！\nID: ${data.backup_id}\n文件: ${data.file_path}\n大小: ${formatBytes(data.file_size)}` }
    } else {
      result.value = { type: 'error', msg: `备份失败: ${data.error || '未知错误'}` }
    }
    await loadBackups()
  } catch (e: any) {
    result.value = { type: 'error', msg: `错误: ${e.message}` }
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
    <div class="form-row">
      <div class="form-group">
        <label>数据库</label>
        <input v-model="db" />
      </div>
      <div class="form-group">
        <label>备份类型</label>
        <select v-model="backupType">
          <option value="full">全量备份</option>
          <option value="table">表级备份</option>
          <option value="incremental">增量备份</option>
        </select>
      </div>
      <div class="form-group">
        <label>表名（可选）</label>
        <input v-model="tables" placeholder="users,orders" />
      </div>
      <div class="form-group" style="align-self:flex-end;">
        <button class="btn-primary" @click="createBackup" :disabled="loading">开始备份</button>
      </div>
    </div>
    <div v-if="result" :class="result.type" style="margin-top:12px;white-space:pre-line;">{{ result.msg }}</div>
  </div>

  <div class="card">
    <h2>备份记录 <span class="count-badge">{{ backups.length }}</span></h2>
    <table>
      <thead><tr><th>备份 ID</th><th>类型</th><th>文件路径</th><th>大小</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-if="backups.length === 0"><td colspan="6" class="empty">暂无备份记录</td></tr>
        <tr v-for="b in backups" :key="b.backup_id || b.file_path">
          <td><code>{{ b.backup_id || '-' }}</code></td>
          <td><span class="badge badge-medium">{{ b.backup_type || 'full' }}</span></td>
          <td>{{ b.file_path || '-' }}</td>
          <td>{{ formatBytes(b.file_size || 0) }}</td>
          <td><span :class="'badge ' + (b.success ? 'badge-low' : 'badge-critical')">{{ b.success ? '✅ 成功' : '❌ 失败' }}</span></td>
          <td><button class="btn-sm" @click="console.log('verify', b.backup_id)">验证</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group input, .form-group select { width: 100%; }
.count-badge { background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-left: 8px; }
.btn-sm { padding: 4px 12px; font-size: 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-card); cursor: pointer; }
.btn-sm:hover { background: #f1f5f9; }
.empty { text-align: center; color: #64748b; padding: 40px; }
</style>