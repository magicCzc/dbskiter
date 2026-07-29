<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { LogEntry } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const dbStore = useDatabaseStore()
const entries = ref<LogEntry[]>([])
const loading = ref(false)
const filterCmd = ref('all')
const lastUpdated = ref('')

const commands = computed(() => {
  const cmds = new Set(entries.value.map(e => e.command || ''))
  return ['all', ...Array.from(cmds).filter(Boolean)]
})

const filtered = computed(() => {
  if (filterCmd.value === 'all') return entries.value
  return entries.value.filter(e => e.command === filterCmd.value)
})

const stats = computed(() => ({
  total: entries.value.length,
  diagnose: entries.value.filter(e => e.command === 'diagnose').length,
  monitor: entries.value.filter(e => e.command === 'monitor').length,
  security: entries.value.filter(e => e.command === 'security').length,
  sql: entries.value.filter(e => e.command === 'sql').length,
  failed: entries.value.filter(e => e.status_code !== 0 && e.status_code !== undefined).length,
}))

async function load() {
  loading.value = true
  try {
    const data: { logs?: LogEntry[]; data?: LogEntry[]; entries?: LogEntry[]; [key: string]: any } = await api.logs(dbStore.current, 168)
    const raw = data.logs || data.data || data.entries || []
    entries.value = (Array.isArray(raw) ? raw : []).slice(0, 200)
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
    entries.value = []
  } finally {
    loading.value = false
  }
}

function formatArgs(args: Record<string, any> | string | undefined | null): string {
  if (!args) return '-'
  if (typeof args === 'object') {
    return Object.entries(args)
      .filter(([k, v]) => v && !['version', 'json', 'quiet', 'no_color', 'output_mode', 'show_trace', 'ai_depth', 'mask_sensitive', 'no_mask', 'password', 'password_file', 'password_stdin'].includes(k))
      .map(([k, v]) => `${k}=${v}`)
      .join(', ')
  }
  return String(args)
}

onMounted(() => { dbStore.loadDatabases(); load() })
</script>

<template>
  <div class="page">
    <SectionCard padding>
      <div class="history-controls">
        <div class="history-controls__left">
          <h2 class="history-title">操作历史</h2>
        </div>
        <div class="history-controls__right">
          <label>命令</label>
          <el-select v-model="filterCmd" size="small" style="width:140px" @change="load">
            <el-option label="全部命令" value="all" />
            <template v-for="cmd in commands" :key="cmd">
              <el-option v-if="cmd !== 'all'" :label="cmd" :value="cmd" />
            </template>
          </el-select>
          <span v-if="lastUpdated" class="history-updated">{{ lastUpdated }} 更新</span>
          <el-button type="primary" size="small" :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>
    </SectionCard>

    <div class="stat-grid">
      <div class="stat-item"><div class="stat-item__value">{{ stats.total }}</div><div class="stat-item__label">总操作数</div></div>
      <div class="stat-item"><div class="stat-item__value" style="color:var(--color-brand-500)">{{ stats.diagnose }}</div><div class="stat-item__label">诊断</div></div>
      <div class="stat-item"><div class="stat-item__value" style="color:var(--color-success-500)">{{ stats.monitor }}</div><div class="stat-item__label">监控</div></div>
      <div class="stat-item"><div class="stat-item__value" style="color:var(--color-warning-500)">{{ stats.security }}</div><div class="stat-item__label">安全审计</div></div>
      <div class="stat-item"><div class="stat-item__value" style="color:var(--color-danger-500)">{{ stats.failed }}</div><div class="stat-item__label">失败</div></div>
    </div>

    <SectionCard padding>
      <el-table :data="filtered" v-loading="loading" stripe style="width:100%"
        :default-sort="{ prop: 'timestamp', order: 'descending' }">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="timestamp" label="时间" width="180" sortable>
          <template #default="{row}">
            <span class="history-time">{{ row.timestamp ? row.timestamp.replace('T', ' ').substring(0, 19) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="command" label="命令" width="100">
          <template #default="{row}">
            <StatusTag :status="row.command || 'info'" />
          </template>
        </el-table-column>
        <el-table-column prop="action" label="动作" width="120" />
        <el-table-column prop="database" label="数据库" width="120" />
        <el-table-column label="参数" min-width="200" show-overflow-tooltip>
          <template #default="{row}"><code class="history-code">{{ formatArgs(row.args) }}</code></template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{row}">
            <StatusTag :status="row.status_code === 0 ? 'success' : 'error'" :label="row.status_code === 0 ? '成功' : '失败'" />
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="100" sortable>
          <template #default="{row}">
            <span v-if="row.execution_time_ms">{{ (row.execution_time_ms / 1000).toFixed(2) }}s</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }

.history-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.history-controls__left, .history-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.history-controls label { font-size: var(--text-sm); color: var(--text-secondary); }
.history-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}
.history-updated {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.history-time { font-size: var(--text-xs); }
.history-code { font-size: var(--text-xs); font-family: var(--font-mono); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}
.stat-item {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  text-align: center;
}
.stat-item__value {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  margin-bottom: var(--space-1);
}
.stat-item__label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
</style>