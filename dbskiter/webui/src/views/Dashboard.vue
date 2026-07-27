<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const dbStore = useDatabaseStore()
const loading = ref(false)
const health = ref<any>(null)
const slowTotal = ref(0)
const securityRisks = ref(0)
const autoRefresh = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const trendData = ref({
  cpu: [45, 52, 78, 85, 72, 55, 48],
  memory: [62, 65, 70, 75, 73, 68, 64],
  disk: [55, 55, 56, 56, 57, 57, 58],
})

const lineOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { bottom: 0 },
  grid: { left: 40, right: 20, top: 20, bottom: 40 },
  xAxis: { type: 'category', data: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '现在'] },
  yAxis: { type: 'value', min: 0, max: 100 },
  series: [
    { name: 'CPU %', type: 'line', data: trendData.value.cpu, smooth: true, lineStyle: { color: '#EF4444', width: 2 }, areaStyle: { color: 'rgba(239,68,68,0.1)' } },
    { name: '内存 %', type: 'line', data: trendData.value.memory, smooth: true, lineStyle: { color: '#3B82F6', width: 2 }, areaStyle: { color: 'rgba(59,130,246,0.1)' } },
    { name: '磁盘 %', type: 'line', data: trendData.value.disk, smooth: true, lineStyle: { color: '#F59E0B', width: 2 }, areaStyle: { color: 'rgba(245,158,11,0.1)' } },
  ],
}))

const pieOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [{
    type: 'pie', radius: ['55%', '75%'],
    data: [
      { value: health.value ? Math.max(0, health.value.score) : 0, name: '健康', itemStyle: { color: '#22C55E' } },
      { value: health.value ? Math.max(0, 100 - health.value.score - (health.value.issues.length * 5)) : 0, name: '警告', itemStyle: { color: '#F59E0B' } },
      { value: health.value ? Math.min(100, health.value.issues.length * 5) : 0, name: '严重', itemStyle: { color: '#EF4444' } },
    ],
    label: { formatter: '{b}\n{d}%' },
  }],
}))

const healthTag = computed(() => {
  if (!health.value) return { type: 'info', text: '加载中' }
  const s = health.value.status
  if (s === 'HEALTHY' || health.value.score >= 80) return { type: 'success', text: '健康' }
  if (s === 'WARNING' || health.value.score >= 60) return { type: 'warning', text: '警告' }
  return { type: 'danger', text: '异常' }
})

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
    ElMessage.error(`数据加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

function toggleAuto() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    ElMessage.success('自动刷新已开启 (15s)')
    refreshTimer = setInterval(refresh, 15000)
  } else {
    ElMessage.info('自动刷新已关闭')
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  }
}

onMounted(() => { dbStore.loadDatabases(); refresh() })
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<template>
  <div class="dashboard">
    <div class="control-bar">
      <div class="control-left">
        <label>数据库：</label>
        <el-select v-model="dbStore.current" size="small" style="width:180px" @change="refresh">
          <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button type="primary" size="small" :loading="loading" @click="refresh">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-switch v-model="autoRefresh" @change="toggleAuto" active-text="自动" />
      </div>
      <el-tag :type="healthTag.type" size="large">{{ healthTag.text }}</el-tag>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: health && health.score < 60 ? '#ef4444' : health && health.score < 80 ? '#f59e0b' : '#22c55e' }">
          {{ health ? health.score.toFixed(0) : '-' }}
        </div>
        <div class="kpi-label">健康评分</div>
        <el-progress :percentage="health?.score || 0" :stroke-width="4" :show-text="false"
          :color="health && health.score > 80 ? '#22C55E' : health && health.score > 60 ? '#F59E0B' : '#EF4444'" />
      </div>
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: (health?.issues?.length || 0) > 5 ? '#ef4444' : '#6366f1' }">
          {{ health ? health.issues.length : '-' }}
        </div>
        <div class="kpi-label">问题数</div>
        <div class="kpi-trend">{{ health?.issues?.length > 0 ? '需要关注' : '一切正常' }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: slowTotal > 10 ? '#ef4444' : '#6366f1' }">{{ slowTotal }}</div>
        <div class="kpi-label">慢查询</div>
        <div class="kpi-trend">最近 1 小时</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: securityRisks > 5 ? '#ef4444' : '#6366f1' }">{{ securityRisks }}</div>
        <div class="kpi-label">安全风险</div>
        <el-tag :type="securityRisks > 5 ? 'danger' : securityRisks > 0 ? 'warning' : 'success'" size="small">
          {{ securityRisks > 5 ? '需立即处理' : securityRisks > 0 ? '需关注' : '安全' }}
        </el-tag>
      </div>
    </div>

    <div class="chart-grid">
      <el-card shadow="hover" class="chart-card">
        <template #header><span>📈 资源趋势 (24h)</span></template>
        <VChart :option="lineOption" autoresize style="height:280px" />
      </el-card>
      <el-card shadow="hover" class="chart-card">
        <template #header><span>🎯 健康分布</span></template>
        <VChart :option="pieOption" autoresize style="height:280px" />
      </el-card>
    </div>

    <el-card shadow="hover">
      <template #header><span>⚡ 快速操作</span></template>
      <div class="action-grid">
        <el-button @click="$router.push('/diagnose')" class="action-btn">🔍 实时诊断</el-button>
        <el-button @click="$router.push('/slow-queries')" class="action-btn">🐢 慢查询分析</el-button>
        <el-button @click="$router.push('/security')" class="action-btn">🔒 安全审计</el-button>
        <el-button @click="$router.push('/backup')" class="action-btn">💾 备份管理</el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.dashboard { max-width: 1200px; margin: 0 auto; }
.control-bar {
  display: flex; justify-content: space-between; align-items: center;
  background: var(--el-bg-color); padding: 16px; border-radius: 8px;
  border: 1px solid var(--el-border-color-light); margin-bottom: 20px;
}
.control-left { display: flex; align-items: center; gap: 12px; }
.control-left label { font-size: 14px; color: var(--el-text-color-secondary); }
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 20px; }
.kpi-card {
  background: var(--el-bg-color); border-radius: 8px; padding: 20px;
  border: 1px solid var(--el-border-color-light); text-align: center;
  transition: box-shadow 0.2s;
}
.kpi-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.kpi-value { font-size: 36px; font-weight: 700; margin-bottom: 4px; }
.kpi-label { font-size: 14px; color: var(--el-text-color-secondary); margin-bottom: 8px; }
.kpi-trend { font-size: 12px; color: var(--el-text-color-placeholder); }
.chart-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 20px; }
.action-grid { display: flex; gap: 12px; flex-wrap: wrap; }
.action-btn { font-size: 14px; }
@media (max-width: 768px) { .chart-grid { grid-template-columns: 1fr; } .kpi-grid { grid-template-columns: 1fr 1fr; } }
</style>