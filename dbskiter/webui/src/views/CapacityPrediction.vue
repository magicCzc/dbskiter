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
import SectionCard from '@/components/SectionCard.vue'
import StatCard from '@/components/StatCard.vue'

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
  if (daysRemaining.value < 30) return 'var(--color-danger-500)'
  if (daysRemaining.value < 90) return 'var(--color-warning-500)'
  return 'var(--color-success-500)'
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

  const predValues = typeof preds === 'object' && !Array.isArray(preds)
    ? Object.values(preds).filter((v): v is number => typeof v === 'number')
    : prediction
  const predLabels = typeof preds === 'object' && !Array.isArray(preds)
    ? Object.keys(preds)
    : timestamps

  const currentVal = raw?.current_value ?? 0
  const histData = history.length ? history : [currentVal]
  const histLabels = timestamps.length ? timestamps : [raw?.current_time || '当前']

  const series: { name: string; type: string; data: any[]; smooth?: boolean; lineStyle?: any; symbol?: string; symbolSize?: number; itemStyle?: any; barWidth?: string; markLine?: any }[] = [
    {
      name: '当前使用量',
      type: 'bar',
      data: [currentVal],
      barWidth: '30%',
      itemStyle: { color: 'var(--color-info-500)', borderRadius: [4, 4, 0, 0] },
    },
  ]

  if (predValues.length) {
    series.push({
      name: '预测值',
      type: 'line',
      data: predValues,
      smooth: true,
      lineStyle: { color: 'var(--color-danger-500)', width: 2, type: 'dashed' },
      symbol: 'circle',
      symbolSize: 8,
    })
  }

  series[0].markLine = totalCapacity.value ? {
    data: [{ yAxis: totalCapacity.value, label: { formatter: `容量上限: ${totalCapacity.value}`, color: 'var(--color-danger-500)' }, lineStyle: { color: 'var(--color-danger-500)', type: 'dashed' } }],
  } : undefined

  return {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: ['当前', ...predLabels], axisLabel: { fontSize: 10, rotate: 0 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'var(--color-gray-100)', type: 'dashed' } }, axisLabel: { fontSize: 10 } },
    series,
  }
})

async function load() {
  loading.value = true
  try {
    const data = await api.capacity(dbStore.current, resource.value)
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
    <el-alert
      v-if="daysRemaining < 30 && daysRemaining > 0"
      :title="`${resource} 将在 ${daysRemaining} 天后耗尽！建议立即扩容`"
      type="error"
      show-icon
      closable
      class="cap-alert"
    />
    <el-alert
      v-else-if="daysRemaining < 90 && daysRemaining > 0"
      :title="`${resource} 预计 ${daysRemaining} 天后耗尽，建议提前规划扩容`"
      type="warning"
      show-icon
      closable
      class="cap-alert"
    />

    <SectionCard padding>
      <div class="cap-controls">
        <div class="cap-controls__left">
          <label>数据库</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <label>资源</label>
          <el-select v-model="resource" size="small" style="width:120px" @change="load">
            <el-option v-for="r in resources" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="cap-controls__right">
          <el-tag :type="daysRemaining < 30 ? 'danger' : daysRemaining < 90 ? 'warning' : 'success'" effect="dark">
            {{ urgencyText }}
          </el-tag>
        </div>
      </div>
    </SectionCard>

    <div class="stat-grid">
      <StatCard :value="currentUsage.toFixed(1)" label="当前用量" size="sm" color="var(--color-info-500)" />
      <StatCard :value="totalCapacity.toFixed(1)" label="总容量" size="sm" color="var(--color-brand-500)" />
      <StatCard
        :value="growthRate.toFixed(2) + '%'"
        label="增长率"
        size="sm"
        :color="growthRate > 10 ? 'var(--color-danger-500)' : 'var(--color-warning-500)'"
      />
      <StatCard
        :value="daysRemaining > 0 ? daysRemaining + ' 天' : '未知'"
        label="预计剩余"
        size="sm"
        :color="urgencyColor"
      />
    </div>

    <SectionCard v-if="exhaustionDate" title="预计耗尽">
      <div class="exhaustion-banner">
        <span class="exhaustion-text">
          预计 <strong>{{ resource }}</strong> 将于
          <strong :style="{ color: urgencyColor }">{{ exhaustionDate }}</strong>
          耗尽，剩余 <strong :style="{ color: urgencyColor }">{{ daysRemaining }}</strong> 天
        </span>
      </div>
    </SectionCard>

    <SectionCard :title="`${resource} 使用趋势与预测`">
      <VChart :option="chartOption" autoresize style="height: 350px" />
      <div class="chart-note">虚线为预测趋势，红线为容量上限</div>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.cap-alert { margin-bottom: var(--space-4); }

.cap-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.cap-controls__left, .cap-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.cap-controls label { font-size: var(--text-sm); color: var(--text-secondary); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.exhaustion-banner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-code);
  border-radius: var(--radius-md);
}
.exhaustion-text { font-size: var(--text-base); color: var(--text-primary); }
.chart-note {
  text-align: center;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-top: var(--space-2);
}
</style>