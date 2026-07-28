<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ScatterChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { AnomalyInfo } from '@/types'

use([CanvasRenderer, ScatterChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const dbStore = useDatabaseStore()
const anomalies = ref<AnomalyInfo[]>([])
const loading = ref(false)
const hours = ref(6)
const filterSeverity = ref('all')
const autoRefresh = ref(false)
const lastUpdated = ref('')
let refreshTimer: ReturnType<typeof setInterval> | null = null

const criticalCount = computed(() => anomalies.value.filter(a => a.severity === 'critical').length)
const warningCount = computed(() => anomalies.value.filter(a => a.severity === 'warning').length)
const infoCount = computed(() => anomalies.value.filter(a => a.severity === 'info' || a.severity === 'low').length)
const totalAnomalies = computed(() => anomalies.value.length)

const filtered = computed(() => {
  if (filterSeverity.value === 'all') return anomalies.value
  return anomalies.value.filter(a => a.severity === filterSeverity.value)
})

const scatterOption = computed(() => {
  const colors: Record<string, string> = { critical: '#ef4444', warning: '#f59e0b', info: '#3b82f6', low: '#22c55e' }
  const series: { name: string; type: string; data: any[]; symbolSize: number; itemStyle: { color: string } }[] = []
  const severities = ['critical', 'warning', 'info', 'low']
  for (const sev of severities) {
    const points = anomalies.value.filter(a => a.severity === sev).map(a => [
      a.timestamp || '',
      a.deviation || a.actual_value || 0,
    ])
    if (points.length) {
      series.push({
        name: sev === 'critical' ? '严重' : sev === 'warning' ? '警告' : sev === 'info' ? '提示' : '低',
        type: 'scatter',
        data: points,
        symbolSize: 12,
        itemStyle: { color: colors[sev] },
      })
    }
  }
  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: { dataIndex: number }) => {
        const idx = params.dataIndex
        const item = anomalies.value[idx]
        if (!item) return ''
        return `<b>${item.metric || ''}</b><br/>
          时间: ${item.timestamp || ''}<br/>
          实际值: ${item.actual_value ?? '-'}<br/>
          期望值: ${item.expected_value ?? '-'}<br/>
          偏差: ${(item.deviation || 0).toFixed(2)}<br/>
          描述: ${item.description || ''}`
      },
    },
    grid: { left: 60, right: 20, top: 20, bottom: 50 },
    xAxis: {
      type: 'time',
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: '偏差值',
      splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } },
    },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series,
  }
})

async function load() {
  loading.value = true
  try {
    const data: { data?: { raw_metrics?: { anomalies?: AnomalyInfo[]; detections?: AnomalyInfo[] }; anomalies?: AnomalyInfo[]; detections?: AnomalyInfo[] }; raw_data?: { anomalies?: AnomalyInfo[]; detections?: AnomalyInfo[] }; anomalies?: AnomalyInfo[]; detections?: AnomalyInfo[] } = await api.anomalies(dbStore.current, hours.value)
    const raw = data.data?.raw_metrics || data.raw_data || data
    anomalies.value = ((raw as Record<string, unknown>).anomalies || (raw as Record<string, unknown>).detections || []) as AnomalyInfo[]
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
    anomalies.value = []
  } finally {
    loading.value = false
  }
}

function toggleAuto() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    refreshTimer = setInterval(load, 30000)
    ElMessage.success('自动刷新已开启 (30s)')
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
      <el-switch v-model="autoRefresh" @change="toggleAuto" size="small" active-text="自动" inactive-text="" style="margin-left:8px" />
    </div>

    <!-- 告警横幅 -->
    <el-alert
      v-if="criticalCount > 0"
      :title="`发现 ${criticalCount} 个严重异常，请立即检查！`"
      type="error"
      show-icon
      closable
      style="margin-bottom:16px"
    />
    <el-alert
      v-else-if="warningCount > 0"
      :title="`${warningCount} 个异常警告`"
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
          <label>时间范围：</label>
          <el-select v-model="hours" size="small" style="width:100px" @change="load">
            <el-option v-for="[v,l] of [[1,'1小时'],[6,'6小时'],[24,'24小时'],[168,'7天']]" :key="v" :value="v" :label="l" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="control-right">
          <el-tag type="danger" size="small" v-if="criticalCount > 0">{{ criticalCount }} 严重</el-tag>
          <el-tag type="warning" size="small" v-if="warningCount > 0">{{ warningCount }} 警告</el-tag>
        </div>
      </div>
    </el-card>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: criticalCount > 0 ? '#ef4444' : '#6366f1' }">{{ totalAnomalies }}</div>
        <div class="kpi-label">异常总数</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#ef4444">{{ criticalCount }}</div>
        <div class="kpi-label">严重</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#f59e0b">{{ warningCount }}</div>
        <div class="kpi-label">警告</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#3b82f6">{{ infoCount }}</div>
        <div class="kpi-label">提示</div>
      </div>
    </div>

    <!-- 图表 -->
    <el-card shadow="never" class="section-card" v-if="anomalies.length > 0">
      <template #header><span>📈 异常时间线</span></template>
      <VChart :option="scatterOption" autoresize style="height: 300px" />
    </el-card>

    <!-- 详情表格 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>异常详情</span>
          <el-select v-model="filterSeverity" size="small" style="width:120px">
            <el-option label="全部级别" value="all" />
            <el-option label="严重" value="critical" />
            <el-option label="警告" value="warning" />
            <el-option label="提示" value="info" />
          </el-select>
        </div>
      </template>
      <el-table :data="filtered" v-loading="loading" stripe style="width:100%" :empty-text="'暂无异常数据 ✅'">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="metric" label="指标" width="120" />
        <el-table-column prop="timestamp" label="时间" width="170" />
        <el-table-column prop="actual_value" label="实际值" width="100" sortable />
        <el-table-column prop="expected_value" label="期望值" width="100" />
        <el-table-column prop="deviation" label="偏差" width="100" sortable>
          <template #default="{row}">
            <span :style="{ color: Math.abs(row.deviation || 0) > 50 ? '#ef4444' : '#f59e0b', fontWeight: 600 }">
              {{ (row.deviation || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="级别" width="90">
          <template #default="{row}">
            <el-tag :type="row.severity === 'critical' ? 'danger' : row.severity === 'warning' ? 'warning' : 'info'" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
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