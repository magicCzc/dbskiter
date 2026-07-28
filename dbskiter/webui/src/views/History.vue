<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { LogEntry } from '@/types'

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
    <!-- 实时反馈 -->
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
    </div>

    <!-- 控制栏 -->
    <el-card shadow="never" class="section-card">
      <div class="control-row">
        <div class="control-left">
          <h2 style="margin:0;font-size:16px;display:flex;align-items:center;gap:8px">📜 操作历史</h2>
        </div>
        <div class="control-right">
          <label>命令：</label>
          <el-select v-model="filterCmd" size="small" style="width:140px" @change="load">
            <el-option label="全部命令" value="all" />
            <template v-for="cmd in commands" :key="cmd">
              <el-option v-if="cmd !== 'all'" :label="cmd" :value="cmd" />
            </template>
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>
    </el-card>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-value" style="color:#6366f1">{{ stats.total }}</div><div class="kpi-label">总操作数</div></div>
      <div class="kpi-card"><div class="kpi-value" style="color:#3b82f6">{{ stats.diagnose }}</div><div class="kpi-label">诊断</div></div>
      <div class="kpi-card"><div class="kpi-value" style="color:#22c55e">{{ stats.monitor }}</div><div class="kpi-label">监控</div></div>
      <div class="kpi-card"><div class="kpi-value" style="color:#f59e0b">{{ stats.security }}</div><div class="kpi-label">安全审计</div></div>
      <div class="kpi-card"><div class="kpi-value" style="color:#ef4444">{{ stats.failed }}</div><div class="kpi-label">失败</div></div>
    </div>

    <!-- 历史表格 -->
    <el-card shadow="never" class="section-card">
      <el-table :data="filtered" v-loading="loading" stripe style="width:100%" :empty-text="'暂无历史记录'"
        :default-sort="{ prop: 'timestamp', order: 'descending' }">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="timestamp" label="时间" width="180" sortable>
          <template #default="{row}">
            <span style="font-size:12px">{{ row.timestamp ? row.timestamp.replace('T', ' ').substring(0, 19) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="command" label="命令" width="100">
          <template #default="{row}">
            <el-tag :type="row.command === 'diagnose' ? 'primary' : row.command === 'monitor' ? 'success' : row.command === 'security' ? 'warning' : 'info'" size="small">
              {{ row.command || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="动作" width="120" />
        <el-table-column prop="database" label="数据库" width="120" />
        <el-table-column label="参数" min-width="200" show-overflow-tooltip>
          <template #default="{row}"><code style="font-size:11px">{{ formatArgs(row.args) }}</code></template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{row}">
            <el-tag :type="row.status_code === 0 ? 'success' : 'danger'" size="small">
              {{ row.status_code === 0 ? '✅' : '❌' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="100" sortable>
          <template #default="{row}">
            <span v-if="row.execution_time_ms">{{ (row.execution_time_ms / 1000).toFixed(2) }}s</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.section-card { margin-bottom: 16px; }
.control-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.control-left, .control-right { display: flex; align-items: center; gap: 12px; }
.control-row label { font-size: 14px; color: var(--el-text-color-secondary); }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 16px; }
.kpi-card { background: var(--el-bg-color); border-radius: 8px; padding: 20px; border: 1px solid var(--el-border-color-light); text-align: center; }
.kpi-value { font-size: 28px; font-weight: 700; }
.kpi-label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }

.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }
</style>