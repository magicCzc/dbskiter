<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { AlertItem, AlertStatsResponse } from '@/types'

const dbStore = useDatabaseStore()
const alerts = ref<AlertItem[]>([])
const loading = ref(false)
const filterLevel = ref('all')
const filterStatus = ref('open')
const lastUpdated = ref('')
const stats = ref<AlertStatsResponse['stats']>({ total: 0, open: 0, critical: 0, warning: 0 })

const filtered = computed(() => {
  let list = alerts.value
  if (filterLevel.value !== 'all') {
    list = list.filter(a => a.level === filterLevel.value)
  }
  return list
})

async function load() {
  loading.value = true
  try {
    const [data, statsData] = await Promise.all([
      api.listAlerts({ status: filterStatus.value === 'all' ? 'all' : filterStatus.value, limit: 100 }),
      api.getAlertStats(),
    ])
    alerts.value = data.alerts || []
    stats.value = statsData.stats || { total: 0, open: 0, critical: 0, warning: 0 }
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

async function acknowledge(id: number) {
  try {
    await api.acknowledgeAlert(id)
    ElMessage.success('告警已确认')
    await load()
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

async function resolve(id: number) {
  try {
    await api.resolveAlert(id)
    ElMessage.success('告警已解决')
    await load()
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

async function resolveAll() {
  try {
    const data = await api.resolveAllAlerts()
    ElMessage.success(`已解决 ${data.resolved_count} 个告警`)
    await load()
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

function levelClass(level: string): string {
  return level === 'critical' ? 'danger' : level === 'warning' ? 'warning' : 'info'
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
          <h2 style="margin:0;font-size:16px;display:flex;align-items:center;gap:8px">🔔 告警管理</h2>
        </div>
        <div class="control-right">
          <label>级别：</label>
          <el-select v-model="filterLevel" size="small" style="width:100px" @change="load">
            <el-option label="全部" value="all" />
            <el-option label="严重" value="critical" />
            <el-option label="警告" value="warning" />
            <el-option label="提示" value="info" />
          </el-select>
          <label>状态：</label>
          <el-select v-model="filterStatus" size="small" style="width:110px" @change="load">
            <el-option label="未处理" value="open" />
            <el-option label="已确认" value="acknowledged" />
            <el-option label="已解决" value="resolved" />
            <el-option label="全部" value="all" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">刷新</el-button>
          <el-button size="small" @click="resolveAll" v-if="stats.open > 0">全部解决</el-button>
        </div>
      </div>
    </el-card>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-value" style="color:#6366f1">{{ stats.total }}</div>
        <div class="kpi-label">告警总数</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: stats.open > 0 ? '#ef4444' : '#22c55e' }">{{ stats.open }}</div>
        <div class="kpi-label">未处理</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#ef4444">{{ stats.critical }}</div>
        <div class="kpi-label">严重</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#f59e0b">{{ stats.warning }}</div>
        <div class="kpi-label">警告</div>
      </div>
    </div>

    <!-- 告警列表 -->
    <el-card shadow="never" class="section-card">
      <el-table :data="filtered" v-loading="loading" stripe style="width:100%" :empty-text="'暂无告警 ✅'"
        :default-sort="{ prop: 'created_at', order: 'descending' }">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="created_at" label="时间" width="170" sortable>
          <template #default="{row}">
            <span style="font-size:12px">{{ row.created_at ? row.created_at.replace('T', ' ').substring(0, 19) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="db_alias" label="数据库" width="100" />
        <el-table-column prop="metric" label="指标" width="100" />
        <el-table-column prop="level" label="级别" width="80">
          <template #default="{row}">
            <el-tag :type="levelClass(row.level) as 'danger' | 'warning' | 'info'" size="small">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_value" label="当前值" width="100" sortable>
          <template #default="{row}">
            <span :style="{ color: row.level === 'critical' ? '#ef4444' : row.level === 'warning' ? '#f59e0b' : '', fontWeight: 600 }">
              {{ typeof row.current_value === 'number' ? row.current_value.toFixed(1) : row.current_value }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="threshold" label="阈值" width="80">
          <template #default="{row}">{{ row.threshold }}</template>
        </el-table-column>
        <el-table-column prop="message" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{row}">
            <el-tag :type="row.status === 'open' ? 'danger' : row.status === 'acknowledged' ? 'warning' : 'success'" size="small">
              {{ row.status === 'open' ? '未处理' : row.status === 'acknowledged' ? '已确认' : '已解决' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{row}">
            <el-button v-if="row.status === 'open'" size="small" @click="acknowledge(row.id)">确认</el-button>
            <el-button v-if="row.status !== 'resolved'" size="small" type="success" plain @click="resolve(row.id)">解决</el-button>
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