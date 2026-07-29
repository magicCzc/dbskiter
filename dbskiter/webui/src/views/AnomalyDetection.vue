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
import SectionCard from '@/components/SectionCard.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'

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
  const colors: Record<string, string> = {
    critical: 'var(--color-danger-500)',
    warning: 'var(--color-warning-500)',
    info: 'var(--color-info-500)',
    low: 'var(--color-success-500)',
  }
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
        const item = anomalies.value[params.dataIndex]
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
    xAxis: { type: 'time', axisLabel: { fontSize: 11 } },
    yAxis: {
      type: 'value',
      name: '偏差值',
      splitLine: { lineStyle: { color: 'var(--color-gray-100)', type: 'dashed' } },
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
    <el-alert
      v-if="criticalCount > 0"
      :title="`发现 ${criticalCount} 个严重异常，请立即检查！`"
      type="error"
      show-icon
      closable
      class="anomaly-alert"
    />
    <el-alert
      v-else-if="warningCount > 0"
      :title="`${warningCount} 个异常警告`"
      type="warning"
      show-icon
      closable
      class="anomaly-alert"
    />

    <SectionCard padding>
      <div class="anomaly-controls">
        <div class="anomaly-controls__left">
          <label>数据库</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <label>时间范围</label>
          <el-select v-model="hours" size="small" style="width:110px" @change="load">
            <el-option v-for="[v,l] of [[1,'1小时'],[6,'6小时'],[24,'24小时'],[168,'7天']]" :key="v" :value="v" :label="l" />
          </el-select>
          <el-switch v-model="autoRefresh" @change="toggleAuto" size="small" active-text="自动" />
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="anomaly-controls__right">
          <StatusTag v-if="criticalCount > 0" status="critical" :label="`${criticalCount} 严重`" />
          <StatusTag v-if="warningCount > 0" status="warning" :label="`${warningCount} 警告`" />
        </div>
      </div>
    </SectionCard>

    <div class="stat-grid">
      <StatCard
        :value="totalAnomalies"
        label="异常总数"
        size="sm"
        :color="criticalCount > 0 ? 'var(--color-danger-500)' : 'var(--color-brand-500)'"
      />
      <StatCard :value="criticalCount" label="严重" size="sm" color="var(--color-danger-500)" />
      <StatCard :value="warningCount" label="警告" size="sm" color="var(--color-warning-500)" />
      <StatCard :value="infoCount" label="提示" size="sm" color="var(--color-info-500)" />
    </div>

    <SectionCard v-if="anomalies.length > 0" title="异常时间线">
      <VChart :option="scatterOption" autoresize style="height: 300px" />
    </SectionCard>

    <SectionCard title="异常详情">
      <template #actions>
        <el-select v-model="filterSeverity" size="small" style="width:120px">
          <el-option label="全部级别" value="all" />
          <el-option label="严重" value="critical" />
          <el-option label="警告" value="warning" />
          <el-option label="提示" value="info" />
        </el-select>
      </template>
      <el-table :data="filtered" v-loading="loading" stripe style="width:100%">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="metric" label="指标" width="120" />
        <el-table-column prop="timestamp" label="时间" width="170" />
        <el-table-column prop="actual_value" label="实际值" width="100" sortable />
        <el-table-column prop="expected_value" label="期望值" width="100" />
        <el-table-column prop="deviation" label="偏差" width="100" sortable>
          <template #default="{row}">
            <span :class="`anomaly-deviation--${Math.abs(row.deviation || 0) > 50 ? 'critical' : 'warning'}`">
              {{ (row.deviation || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="级别" width="90">
          <template #default="{row}">
            <StatusTag :status="row.severity" />
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      </el-table>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.anomaly-alert { margin-bottom: var(--space-4); }

.anomaly-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.anomaly-controls__left, .anomaly-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.anomaly-controls label { font-size: var(--text-sm); color: var(--text-secondary); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.anomaly-deviation--critical { color: var(--color-danger-500); font-weight: var(--font-semibold); }
.anomaly-deviation--warning { color: var(--color-warning-500); font-weight: var(--font-semibold); }
</style>