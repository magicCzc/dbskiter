<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useDialog } from 'naive-ui'
import {
  NCard, NStatistic, NGrid, NGi, NSpace, NTag, NButton, NSelect, NSwitch,
  NIcon, NText, NSpin, NDivider, NEmpty, NProgress, NTooltip,
} from 'naive-ui'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent, TitleComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import {
  SpeedometerOutline, ArrowUpOutline, ArrowDownOutline,
  FlashOutline, ShieldCheckmarkOutline, ServerOutline, RefreshOutline,
} from '@vicons/ionicons5'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const dbStore = useDatabaseStore()

// 数据状态
const health = ref<any>(null)
const slowTotal = ref(0)
const securityRisks = ref(0)
const loading = ref(false)
const autoRefresh = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

// 趋势数据
const trendData = ref({
  cpu: [45, 52, 78, 85, 72, 55, 48],
  memory: [62, 65, 70, 75, 73, 68, 64],
  disk: [55, 55, 56, 56, 57, 57, 58],
})

const healthDistribution = computed(() => ({
  labels: ['健康', '警告', '严重'],
  datasets: [{
    data: [
      health.value ? Math.max(0, health.value.score) : 0,
      health.value ? Math.max(0, 100 - health.value.score - (health.value.issues.length * 5)) : 0,
      health.value ? Math.min(100, health.value.issues.length * 5) : 0,
    ],
  }],
}))

// 折线图配置
const lineOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { bottom: 0 },
  grid: { left: 40, right: 20, top: 20, bottom: 40 },
  xAxis: {
    type: 'category',
    data: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '现在'],
  },
  yAxis: { type: 'value', min: 0, max: 100 },
  series: [
    { name: 'CPU %', type: 'line', data: trendData.value.cpu, smooth: true, lineStyle: { color: '#EF4444', width: 2 }, areaStyle: { color: 'rgba(239,68,68,0.1)' } },
    { name: '内存 %', type: 'line', data: trendData.value.memory, smooth: true, lineStyle: { color: '#3B82F6', width: 2 }, areaStyle: { color: 'rgba(59,130,246,0.1)' } },
    { name: '磁盘 %', type: 'line', data: trendData.value.disk, smooth: true, lineStyle: { color: '#F59E0B', width: 2 }, areaStyle: { color: 'rgba(245,158,11,0.1)' } },
  ],
}))

// 饼图配置
const pieOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['55%', '75%'],
    center: ['50%', '45%'],
    data: [
      { value: healthDistribution.value.datasets[0].data[0], name: '健康', itemStyle: { color: '#22C55E' } },
      { value: healthDistribution.value.datasets[0].data[1], name: '警告', itemStyle: { color: '#F59E0B' } },
      { value: healthDistribution.value.datasets[0].data[2], name: '严重', itemStyle: { color: '#EF4444' } },
    ],
    label: { formatter: '{b}\n{d}%' },
  }],
}))

async function refresh() {
  loading.value = true
  try {
    const [h, s, sec] = await Promise.all([
      api.health(dbStore.current),
      api.slowQueries(dbStore.current, 5, 1),
      api.security(dbStore.current),
    ])
    health.value = h
    slowTotal.value = s.total
    securityRisks.value = sec.total_risks
  } catch (e: any) {
    console.error("ERROR:", `数据加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    console.info("INFO:", '自动刷新已开启 (15s)')
    refreshTimer = setInterval(refresh, 15000)
  } else {
    console.info("INFO:", '自动刷新已关闭')
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  }
}

const healthTagType = computed(() => {
  if (!health.value) return 'default'
  if (health.value.status === 'HEALTHY') return 'success'
  if (health.value.status === 'WARNING') return 'warning'
  return 'error'
})

onMounted(refresh)
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<template>
  <NSpace vertical :size="16">
    <!-- 顶部状态卡 -->
    <NGrid :cols="4" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <NGi span="4 m:1">
        <NCard hoverable>
          <NSpace vertical :size="8">
            <NSpace align="center" justify="space-between">
              <NText depth="3">健康评分</NText>
              <NTag :type="healthTagType" size="small" round>
                {{ health?.status || '加载中' }}
              </NTag>
            </NSpace>
            <NStatistic :value="health ? health.score.toFixed(0) : '-'" style="font-size:32px;font-weight:700">
              <template #prefix v-if="health && health.score < 60">
                <NTag type="error" size="small">异常</NTag>
              </template>
            </NStatistic>
            <NProgress
              type="line"
              :percentage="health?.score || 0"
              :color="health && health.score > 80 ? '#22C55E' : health && health.score > 60 ? '#F59E0B' : '#EF4444'"
              :show-indicator="false"
            />
          </NSpace>
        </NCard>
      </NGi>
      <NGi span="4 m:1">
        <NCard hoverable>
          <NSpace vertical :size="8">
            <NSpace align="center" justify="space-between">
              <NText depth="3">问题数</NText>
              <NIcon size="18"><ServerOutline /></NIcon>
            </NSpace>
            <NStatistic :value="health?.issues.length || '-'" style="font-size:32px;font-weight:700" />
            <NText depth="3" style="font-size:12px">
              {{ health?.issues?.length > 0 ? '需要关注' : '一切正常' }}
            </NText>
          </NSpace>
        </NCard>
      </NGi>
      <NGi span="4 m:1">
        <NCard hoverable>
          <NSpace vertical :size="8">
            <NSpace align="center" justify="space-between">
              <NText depth="3">慢查询</NText>
              <NIcon size="18" color="#F59E0B"><FlashOutline /></NIcon>
            </NSpace>
            <NStatistic :value="slowTotal" style="font-size:32px;font-weight:700" />
            <NText depth="3" style="font-size:12px">最近 1 小时</NText>
          </NSpace>
        </NCard>
      </NGi>
      <NGi span="4 m:1">
        <NCard hoverable>
          <NSpace vertical :size="8">
            <NSpace align="center" justify="space-between">
              <NText depth="3">安全风险</NText>
              <NIcon size="18" color="#EF4444"><ShieldCheckmarkOutline /></NIcon>
            </NSpace>
            <NStatistic :value="securityRisks" style="font-size:32px;font-weight:700" />
            <NText depth="3" style="font-size:12px">
              <NTag v-if="securityRisks > 5" type="error" size="tiny">需立即处理</NTag>
              <NTag v-else-if="securityRisks > 0" type="warning" size="tiny">需关注</NTag>
              <NTag v-else type="success" size="tiny">安全</NTag>
            </NText>
          </NSpace>
        </NCard>
      </NGi>
    </NGrid>

    <!-- 控制栏 -->
    <NCard>
      <NSpace align="center" justify="space-between">
        <NSpace align="center">
          <NText>数据库:</NText>
          <NSelect
            :value="dbStore.current"
            :options="dbStore.databases.map(d => ({ label: d, value: d }))"
            style="width:180px"
            size="small"
            @update:value="(v) => { dbStore.setCurrent(v); refresh() }"
          />
          <NButton type="primary" size="small" :loading="loading" @click="refresh">
            <template #icon><NIcon><RefreshOutline /></NIcon></template>
            刷新
          </NButton>
          <NSwitch v-model:value="autoRefresh" size="small" @update:value="toggleAutoRefresh">
            <template #checked>自动</template>
            <template #unchecked>手动</template>
          </NSwitch>
        </NSpace>
        <NText depth="3" style="font-size:12px">
          数据库: <code>{{ dbStore.current }}</code>
        </NText>
      </NSpace>
    </NCard>

    <!-- 图表区 -->
    <NGrid :cols="3" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <NGi span="3 m:2">
        <NCard title="📈 资源趋势 (24h)">
          <VChart :option="lineOption" autoresize style="height:300px" />
        </NCard>
      </NGi>
      <NGi span="3 m:1">
        <NCard title="🎯 健康分布">
          <VChart :option="pieOption" autoresize style="height:300px" />
        </NCard>
      </NGi>
    </NGrid>

    <!-- 快速操作 -->
    <NCard title="⚡ 快速操作">
      <NSpace>
        <NButton type="primary" ghost @click="$router.push('/diagnose')">🏥 健康检查</NButton>
        <NButton type="primary" ghost @click="$router.push('/slow-queries')">🐢 慢查询分析</NButton>
        <NButton type="primary" ghost @click="$router.push('/security')">🔒 安全审计</NButton>
        <NButton type="primary" ghost @click="$router.push('/backup')">💾 备份管理</NButton>
        <NButton type="primary" ghost @click="$router.push('/scheduler')">⏰ 任务调度</NButton>
      </NSpace>
    </NCard>
  </NSpace>
</template>