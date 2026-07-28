<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { ConnectionInfo } from '@/types'

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
  } catch {
    // 用户取消
  }
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
    <!-- 实时反馈 -->
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot" :class="{ active: autoRefresh }"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
      <el-switch v-model="autoRefresh" @change="toggleAuto" size="small" active-text="自动(10s)" inactive-text="" style="margin-left:8px" />
    </div>

    <!-- 连接数告警 -->
    <el-alert
      v-if="connPercent > 80"
      :title="`连接数已达 ${totalConnections}/${maxConnections} (${connPercent.toFixed(0)}%)，接近上限！`"
      type="error"
      show-icon
      closable
      style="margin-bottom:16px"
    />
    <el-alert
      v-else-if="connPercent > 60"
      :title="`连接数 ${totalConnections}/${maxConnections}`"
      type="warning"
      show-icon
      closable
      style="margin-bottom:16px"
    />

    <!-- 控制栏 -->
    <el-card shadow="never" class="section-card">
      <div class="control-row">
        <div class="control-left">
          <label>数据库：</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="control-right">
          <el-tag v-if="maxConnections > 0" :type="connPercent > 80 ? 'danger' : connPercent > 60 ? 'warning' : 'info'" size="medium">
            {{ totalConnections }} / {{ maxConnections }} ({{ connPercent.toFixed(0) }}%)
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: connPercent > 80 ? '#ef4444' : connPercent > 60 ? '#f59e0b' : '#3b82f6' }">{{ totalConnections }}</div>
        <div class="kpi-label">总连接数</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#f59e0b">{{ activeQueries }}</div>
        <div class="kpi-label">活跃查询</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#22c55e">{{ idleConnections }}</div>
        <div class="kpi-label">空闲连接</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#6366f1">{{ maxConnections }}</div>
        <div class="kpi-label">最大连接数</div>
      </div>
    </div>

    <!-- 连接表格 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>连接详情</span>
          <el-button size="small" @click="load" :loading="loading">刷新</el-button>
        </div>
      </template>
      <el-table :data="connections" v-loading="loading" stripe style="width:100%" :empty-text="'暂无连接数据'"
        :default-sort="{ prop: 'duration', order: 'descending' }">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="pid" label="PID" width="80" sortable />
        <el-table-column prop="user" label="用户" width="100" />
        <el-table-column prop="host" label="主机" width="150" show-overflow-tooltip />
        <el-table-column prop="database" label="数据库" width="120" />
        <el-table-column prop="state" label="状态" width="100">
          <template #default="{row}">
            <el-tag
              :type="(row.state || '').toLowerCase() === 'active' || (row.state || '').toLowerCase() === 'running' ? 'warning' : (row.state || '').toLowerCase() === 'sleep' ? 'info' : 'default'"
              size="small">
              {{ row.state || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="query" label="当前 SQL" min-width="300" show-overflow-tooltip>
          <template #default="{row}"><code style="font-size:11px">{{ row.query || '-' }}</code></template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="90" sortable>
          <template #default="{row}">
            <span :style="{ color: (row.duration || 0) > 30 ? '#ef4444' : (row.duration || 0) > 10 ? '#f59e0b' : '', fontWeight: 600 }">
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
    </el-card>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.section-card { margin-bottom: 16px; }
.control-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.control-left, .control-right { display: flex; align-items: center; gap: 12px; }
.control-row label { font-size: 14px; color: var(--el-text-color-secondary); }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 16px; }
.kpi-card { background: var(--el-bg-color); border-radius: 8px; padding: 20px; border: 1px solid var(--el-border-color-light); text-align: center; }
.kpi-value { font-size: 28px; font-weight: 700; }
.kpi-label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }

.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #94a3b8; }
.live-dot.active { background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }
</style>