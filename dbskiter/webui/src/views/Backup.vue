<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api, formatBytes, exportCSV } from '@/api'
import { ElMessage } from 'element-plus'
import type { BackupRecord } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const dbStore = useDatabaseStore()
const backupType = ref('full')
const tables = ref('')
const backups = ref<BackupRecord[]>([])
const loading = ref(false)
const result = ref<{ type: string; msg: string } | null>(null)
const lastUpdated = ref('')

async function createBackup() {
  result.value = { type: 'info', msg: '备份执行中...' }
  try {
    const data = await api.createBackup(dbStore.current, backupType.value, tables.value || undefined)
    if (data.success) {
      result.value = { type: 'success', msg: `备份成功\nID: ${data.backup_id}\n文件: ${data.file_path}\n大小: ${formatBytes(data.file_size)}` }
      ElMessage.success('备份成功')
    } else {
      result.value = { type: 'error', msg: `备份失败: ${data.error || '未知错误'}` }
      ElMessage.error('备份失败')
    }
    await loadBackups()
  } catch (e: any) { result.value = { type: 'error', msg: `错误: ${e.message}` } }
}

async function loadBackups() {
  loading.value = true
  try {
    const data = await api.listBackups(dbStore.current)
    backups.value = data.backups || []
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch { /* 静默 */ }
  finally { loading.value = false }
}

onMounted(loadBackups)

function exportCSVData() {
  exportCSV(backups.value.map(b => ({
    备份ID: b.backup_id,
    类型: b.backup_type,
    文件路径: b.file_path,
    大小: formatBytes(b.file_size || 0),
    状态: b.success ? '成功' : '失败',
  })), `backups-${dbStore.current}.csv`)
}
</script>

<template>
  <div class="page">
    <SectionCard title="创建备份">
      <el-form :inline="true" size="small">
        <el-form-item label="数据库">
          <el-select v-model="dbStore.current" style="width:160px">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="backupType" style="width:120px">
            <el-option label="全量备份" value="full" />
            <el-option label="增量备份" value="incremental" />
            <el-option label="表级备份" value="table" />
          </el-select>
        </el-form-item>
        <el-form-item label="表名">
          <el-input v-model="tables" placeholder="users,orders" style="width:160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="createBackup">开始备份</el-button>
        </el-form-item>
      </el-form>
      <el-alert v-if="result" :title="result.msg" :type="(result.type as 'info' | 'success' | 'error' | 'warning')" show-icon style="white-space:pre-line" />
    </SectionCard>

    <SectionCard title="备份记录">
      <template #actions>
        <span v-if="lastUpdated" class="backup-updated">{{ lastUpdated }} 更新</span>
        <el-button size="small" @click="exportCSVData" :disabled="!backups.length">导出 CSV</el-button>
        <el-button size="small" @click="loadBackups" :loading="loading">刷新</el-button>
      </template>
      <el-table :data="backups" v-loading="loading" stripe style="width:100%">
        <el-table-column prop="backup_id" label="备份 ID" min-width="200">
          <template #default="{row}"><code class="backup-code">{{ row.backup_id || '-' }}</code></template>
        </el-table-column>
        <el-table-column prop="backup_type" label="类型" width="100">
          <template #default="{row}"><StatusTag :status="row.backup_type || 'full'" /></template>
        </el-table-column>
        <el-table-column prop="file_path" label="文件路径" min-width="200" show-overflow-tooltip />
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{row}">{{ formatBytes(row.file_size || 0) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{row}">
            <StatusTag :status="row.success ? 'success' : 'error'" :label="row.success ? '成功' : '失败'" />
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }
.backup-code { font-size: var(--text-xs); font-family: var(--font-mono); }
.backup-updated { font-size: var(--text-xs); color: var(--text-tertiary); }
</style>