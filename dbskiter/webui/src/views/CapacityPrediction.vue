<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

const dbStore = useDatabaseStore()
const loading = ref(false)
const resource = ref('disk')
const capacityData = ref<Record<string, any> | null>(null)
const lastUpdated = ref('')

const resources = [
  { value: 'disk', label: '磁盘' },
  { value: 'memory', label: '内存' },
  { value: 'connections', label: '连接数' },
]

const currentUsage = computed(() => capacityData.value?.current_value ?? capacityData.value?.current_usage ?? 0)
const totalCapacity = computed(() => capacityData.value?.threshold ?? capacityData.value?.total_capacity ?? 0)
const growthRate = computed(() => capacityData.value?.growth_rate_daily ?? capacityData.value?.growth_rate ?? 0)
const daysRemaining = computed(() => capacityData.value?.days_to_threshold ?? capacityData.value?.days_remaining ?? 999)
const exhaustionDate = computed(() => capacityData.value?.estimated_exhaustion || '')

const usagePercent = computed(() => {
  if (!totalCapacity.value) return 0
  return (currentUsage.value / totalCapacity.value) * 100
})

const urgencyColor = computed(() => {
  if (daysRemaining.value < 30) return '#ef4444'
  if (daysRemaining.value < 90) return '#f59e0b'
  return '#22c55e'
})

const urgencyText = computed(() => {
  if (daysRemaining.value < 30) return '紧急'
  if (daysRemaining.value < 90) return '需关注'
  return '正常'
})

const chartOption = computed(() => {
  const raw = capacityData.value
  const preds = raw?.predictions || {}
  const history = raw?.history || []
  const prediction = raw?.prediction || []
  const timestamps = raw?.timestamps || []

  // 如果 CLI 返回 predictions 字典，转为数组用于图表
  const predValues = typeof preds === 'object' && !Array.isArray(preds)
    ? Object.values(preds).filter((v): v is number => typeof v === 'number')
    : prediction
  const predLabels = typeof preds === 'object' && !Array.isArray(preds)
    ? Object.keys(preds)
    : timestamps

  // 当前值作为历史数据点
  const currentVal = raw?.current_value ?? 0
  const histData = history.length ? history : [currentVal]
  const histLabels = timestamps.length ? timestamps : [raw?.current_time || '当前']

  const series: { name: string; type: string; data: any[]; smooth?: boolean; lineStyle?: any; symbol?: string; symbolSize?: number; itemStyle?: any; barWidth?: string; markLine?: any }[] = [
    {
      name: '当前使用量',
      type: 'bar',
      data: [currentVal],
      barWidth: '30%',
      itemStyle: { color: '#3B82F6', borderRadius: [4, 4, 0, 0] },
    },
  ]

  if (predValues.length) {
    series.push({
      name: '预测值',
      type: 'line',
      data: predValues,
      smooth: true,
      lineStyle: { color: '#EF4444', width: 2, type: 'dashed' },
      symbol: 'circle',
      symbolSize: 8,
    })
  }

  series[0].markLine = totalCapacity.value ? {
    data: [{ yAxis: totalCapacity.value, label: { formatter: `容量上限: ${totalCapacity.value}`, color: '#ef4444' }, lineStyle: { color: '#ef4444', type: 'dashed' } }],
  } : undefined

  return {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: ['当前', ...predLabels], axisLabel: { fontSize: 10, rotate: 0 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }, axisLabel: { fontSize: 10 } },
    series,
  }
})

async function load() {
  loading.value = true
  try {
    const data = await api.capacity(dbStore.current, resource.value)
    // CLI 返回数据在 data.raw_metrics 中
    const raw = data.data?.raw_metrics || data
    capacityData.value = raw
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
    capacityData.value = null
  } finally {
    loading.value = false
  }
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

    <!-- 紧急告警 -->
    <el-alert
      v-if="daysRemaining < 30 && daysRemaining > 0"
      :title="`${resource} 将在 ${daysRemaining} 天后耗尽！建议立即扩容`"
      type="error"
      show-icon
      closable
      style="margin-bottom:16px"
    />
    <el-alert
      v-else-if="daysRemaining < 90 && daysRemaining > 0"
      :title="`${resource} 预计 ${daysRemaining} 天后耗尽，建议提前规划扩容`"
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
          <label>资源：</label>
          <el-select v-model="resource" size="small" style="width:120px" @change="load">
            <el-option v-for="r in resources" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="control-right">
          <el-tag :type="daysRemaining < 30 ? 'danger' : daysRemaining < 90 ? 'warning' : 'success'" size="medium" effect="dark">
            {{ urgencyText }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-value" style="color:#3b82f6">{{ currentUsage.toFixed(1) }}</div>
        <div class="kpi-label">当前用量</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#6366f1">{{ totalCapacity.toFixed(1) }}</div>
        <div class="kpi-label">总容量</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: growthRate > 10 ? '#ef4444' : '#f59e0b' }">{{ growthRate.toFixed(2) }}%</div>
        <div class="kpi-label">增长率</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: urgencyColor }">{{ daysRemaining > 0 ? daysRemaining + ' 天' : '未知' }}</div>
        <div class="kpi-label">预计剩余</div>
      </div>
    </div>

    <!-- 耗尽日期 -->
    <el-card shadow="never" class="section-card" v-if="exhaustionDate">
      <div class="exhaustion-banner">
        <span class="exhaustion-icon">📅</span>
        <span class="exhaustion-text">
          预计 <strong>{{ resource }}</strong> 将于
          <strong :style="{ color: urgencyColor }">{{ exhaustionDate }}</strong>
          耗尽，剩余 <strong :style="{ color: urgencyColor }">{{ daysRemaining }}</strong> 天
        </span>
      </div>
    </el-card>

    <!-- 趋势图 -->
    <el-card shadow="never" class="section-card">
      <template #header><span>📈 {{ resource }} 使用趋势与预测</span></template>
      <VChart :option="chartOption" autoresize style="height: 350px" />
      <div class="chart-note">虚线为预测趋势，红线为容量上限</div>
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
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }

.exhaustion-banner { display: flex; align-items: center; gap: 12px; padding: 16px; background: var(--el-fill-color-light); border-radius: 8px; }
.exhaustion-icon { font-size: 24px; }
.exhaustion-text { font-size: 15px; }
.chart-note { text-align: center; font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 8px; }
</style>