<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { ConnectionInfo } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const dbStore = useDatabaseStore()
const connections = ref<ConnectionInfo[]>([])
const loading = ref(false)
const autoRefresh = ref(false)
const lastUpdated = ref('')
const maxConnections = ref(0)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const totalConnections = computed(() => connections.value.length)
const activeQueries = computed(() => connections.value.filter(c => {
  const s = (c.state || '').toLowerCase()
  return s === 'active' || s === 'running' || s === 'executing'
}).length)
const idleConnections = computed(() => connections.value.filter(c => {
  const s = (c.state || '').toLowerCase()
  return s === 'sleep' || s === 'idle'
}).length)

const connPercent = computed(() => {
  if (!maxConnections.value) return 0
  return (totalConnections.value / maxConnections.value) * 100
})

const connColor = computed(() => {
  if (connPercent.value > 80) return 'var(--color-danger-500)'
  if (connPercent.value > 60) return 'var(--color-warning-500)'
  return 'var(--color-info-500)'
})

async function load() {
  loading.value = true
  try {
    const data = await api.connections(dbStore.current)
    const raw = data.data?.raw_metrics || data.raw_data || data
    connections.value = (raw.connections || raw.processes || []).slice(0, 100)
    maxConnections.value = raw.max_connections || raw.maxConnections || 0
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
    connections.value = []
  } finally {
    loading.value = false
  }
}

async function killConnection(pid: number) {
  try {
    await ElMessageBox.confirm(
      `确定要终止连接 ${pid} 吗？`,
      '终止连接',
      { confirmButtonText: '确认终止', cancelButtonText: '取消', type: 'warning' }
    )
    const result = await api.executeSQL(dbStore.current, `KILL ${pid}`, 1, false)
    if (result.success || result.data?.success) {
      ElMessage.success(`已终止连接 ${pid}`)
      await load()
    } else {
      ElMessage.error(`终止失败: ${result.error || '未知错误'}`)
    }
  } catch { /* 用户取消 */ }
}

function toggleAuto() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    refreshTimer = setInterval(load, 10000)
    ElMessage.success('自动刷新已开启 (10s)')
  } else {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
    ElMessage.info('自动刷新已关闭')
  }
}

onMounted(() => { dbStore.loadDatabases(); load() })
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<template>
  <div class="page">
    <el-alert
      v-if="connPercent > 80"
      :title="`连接数已达 ${totalConnections}/${maxConnections} (${connPercent.toFixed(0)}%)，接近上限！`"
      type="error"
      show-icon
      closable
      class="conn-alert"
    />
    <el-alert
      v-else-if="connPercent > 60"
      :title="`连接数 ${totalConnections}/${maxConnections}`"
      type="warning"
      show-icon
      closable
      class="conn-alert"
    />

    <SectionCard padding>
      <div class="conn-controls">
        <div class="conn-controls__left">
          <label>数据库</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <el-switch v-model="autoRefresh" @change="toggleAuto" size="small" active-text="自动(10s)" />
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="conn-controls__right">
          <el-tag v-if="maxConnections > 0" :type="connPercent > 80 ? 'danger' : connPercent > 60 ? 'warning' : 'info'">
            {{ totalConnections }} / {{ maxConnections }} ({{ connPercent.toFixed(0) }}%)
          </el-tag>
        </div>
      </div>
    </SectionCard>

    <div class="stat-grid">
      <StatCard :value="totalConnections" label="总连接数" size="sm" :color="connColor" />
      <StatCard :value="activeQueries" label="活跃查询" size="sm" color="var(--color-warning-500)" />
      <StatCard :value="idleConnections" label="空闲连接" size="sm" color="var(--color-success-500)" />
      <StatCard :value="maxConnections" label="最大连接数" size="sm" color="var(--color-brand-500)" />
    </div>

    <SectionCard title="连接详情">
      <template #actions>
        <el-button size="small" @click="load" :loading="loading">刷新</el-button>
      </template>
      <el-table :data="connections" v-loading="loading" stripe style="width:100%" :default-sort="{ prop: 'duration', order: 'descending' }">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="pid" label="PID" width="80" sortable />
        <el-table-column prop="user" label="用户" width="100" />
        <el-table-column prop="host" label="主机" width="150" show-overflow-tooltip />
        <el-table-column prop="database" label="数据库" width="120" />
        <el-table-column prop="state" label="状态" width="100">
          <template #default="{row}">
            <StatusTag :status="row.state || 'unknown'" />
          </template>
        </el-table-column>
        <el-table-column prop="query" label="当前 SQL" min-width="300" show-overflow-tooltip>
          <template #default="{row}"><code class="conn-sql">{{ row.query || '-' }}</code></template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="90" sortable>
          <template #default="{row}">
            <span :class="`conn-time--${(row.duration || 0) > 30 ? 'critical' : (row.duration || 0) > 10 ? 'warning' : 'ok'}`">
              {{ row.duration ? row.duration.toFixed(1) + 's' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{row}">
            <el-button size="small" type="danger" plain @click="killConnection(row.pid)" :disabled="(row.state || '').toLowerCase() === 'sleep'">
              KILL
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.conn-alert { margin-bottom: var(--space-4); }

.conn-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.conn-controls__left, .conn-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.conn-controls label { font-size: var(--text-sm); color: var(--text-secondary); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.conn-sql { font-size: var(--text-xs); font-family: var(--font-mono); }
.conn-time--critical { color: var(--color-danger-500); font-weight: var(--font-semibold); font-variant-numeric: tabular-nums; }
.conn-time--warning { color: var(--color-warning-500); font-weight: var(--font-semibold); font-variant-numeric: tabular-nums; }
.conn-time--ok { color: var(--text-secondary); font-variant-numeric: tabular-nums; }
</style>