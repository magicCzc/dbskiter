<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import { api } from '@/api'
import type { HealthResponse } from '@/types'
import ChartWidget from '@/components/ChartWidget.vue'

const toast = inject('toast') as ((msg: string, type?: string) => void) | undefined

const db = ref('default')
const databases = ref<string[]>(['default'])
const health = ref<HealthResponse | null>(null)
const slowTotal = ref(0)
const securityRisks = ref(0)
const loading = ref(false)
const error = ref('')
const autoRefresh = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

// 模拟趋势数据（真实场景从 API 获取）
const trendLabels = ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '现在']
const trendData = ref({
  cpu: [45, 52, 78, 85, 72, 55, 48],
  memory: [62, 65, 70, 75, 73, 68, 64],
  disk: [55, 55, 56, 56, 57, 57, 58],
  qps: [1200, 1500, 3200, 4500, 3800, 2500, 1800],
})

const lineChartData = computed(() => ({
  labels: trendLabels,
  datasets: [
    { label: 'CPU %', data: trendData.value.cpu, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', fill: true, tension: 0.4, pointRadius: 3 },
    { label: '内存 %', data: trendData.value.memory, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', fill: true, tension: 0.4, pointRadius: 3 },
    { label: '磁盘 %', data: trendData.value.disk, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)', fill: true, tension: 0.4, pointRadius: 3 },
  ],
}))

const lineOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'bottom' as const, labels: { boxWidth: 12, padding: 16 } } },
  scales: {
    y: { beginAtZero: true, max: 100, grid: { color: 'rgba(0,0,0,0.05)' } },
    x: { grid: { display: false } },
  },
  interaction: { intersect: false, mode: 'index' as const },
}

const doughnutData = computed(() => ({
  labels: ['健康', '警告', '严重'],
  datasets: [{
    data: [
      health.value ? Math.max(0, health.value.score) : 0,
      health.value ? Math.max(0, 100 - health.value.score - (health.value.issues.length * 5)) : 0,
      health.value ? Math.min(100, health.value.issues.length * 5) : 0,
    ],
    backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
    borderWidth: 0,
    hoverOffset: 4,
  }],
}))

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'bottom' as const, labels: { boxWidth: 12, padding: 16 } } },
  cutout: '70%',
}

const diagnosisItems = computed(() => [
  { label: 'CPU 使用率', value: health.value ? Math.min(95, 100 - health.value.score * 0.6) : 0, max: 100, unit: '%', color: health.value && health.value.score > 80 ? '#22c55e' : health.value && health.value.score > 60 ? '#f59e0b' : '#ef4444' },
  { label: '内存使用率', value: health.value ? Math.min(95, 50 + (100 - health.value.score) * 0.3) : 0, max: 100, unit: '%', color: '#3b82f6' },
  { label: '磁盘使用率', value: health.value ? Math.min(95, 40 + (100 - health.value.score) * 0.4) : 0, max: 100, unit: '%', color: '#f59e0b' },
  { label: '活动连接', value: health.value ? Math.min(200, health.value.issues.length * 10 + 10) : 0, max: 200, unit: '', color: '#8b5cf6' },
])

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [h, s, sec] = await Promise.all([
      api.health(db.value),
      api.slowQueries(db.value, 5),
      api.security(db.value),
    ])
    health.value = h
    slowTotal.value = s.total
    securityRisks.value = sec.total_risks
  } catch (e: any) {
    error.value = e.message
    toast?.('数据加载失败: ' + e.message, 'error')
  } finally {
    loading.value = false
  }
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    toast?.('自动刷新已开启 (15s)', 'success')
    refreshTimer = setInterval(refresh, 15000)
  } else {
    toast?.('自动刷新已关闭', 'info')
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  }
}

const quickActions = [
  { key: 'health', label: '健康检查', icon: '🏥' },
  { key: 'slow', label: '慢查询分析', icon: '🐢' },
  { key: 'security', label: '安全审计', icon: '🔒' },
  { key: 'diagnose', label: '实时诊断', icon: '🔍' },
]
const quickResult = ref('')
const showQuickResult = ref(false)

async function runQuickAction(key: string) {
  showQuickResult.value = true
  quickResult.value = '执行中...'
  try {
    let data: any
    switch (key) {
      case 'health': data = await api.health(db.value); break
      case 'slow': data = await api.slowQueries(db.value, 5); break
      case 'security': data = await api.security(db.value); break
      case 'diagnose': data = await api.diagnose(db.value); break
    }
    quickResult.value = JSON.stringify(data, null, 2)
  } catch (e: any) {
    quickResult.value = `错误: ${e.message}`
  }
}

onMounted(() => {
  refresh()
  api.databases().then(d => { if (d.databases?.length) databases.value = d.databases }).catch(() => {})
})
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<template>
  <div class="card">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
      <div class="toolbar" style="margin-bottom:0;">
        <label>数据库：</label>
        <select v-model="db" style="max-width:200px">
          <option v-for="d in databases" :key="d" :value="d">{{ d }}</option>
        </select>
        <button class="btn-primary" @click="refresh" :disabled="loading">刷新</button>
        <button :class="['btn-ghost', { 'btn-active': autoRefresh }]" @click="toggleAutoRefresh">
          {{ autoRefresh ? '⏹' : '🔄' }} 自动
        </button>
      </div>
      <span v-if="health" :class="'status status-' + (health.status === 'HEALTHY' ? 'healthy' : health.status === 'WARNING' ? 'warning' : 'critical')">
        {{ health.status }}
      </span>
    </div>
  </div>

  <div v-if="error" class="error">{{ error }}</div>

  <div class="metrics-grid">
    <div class="metric-card">
      <div class="value" :style="{ color: health && health.score < 60 ? '#ef4444' : health && health.score < 80 ? '#f59e0b' : '#4f46e5' }">
        {{ health ? health.score.toFixed(0) : '-' }}
      </div>
      <div class="label">健康评分</div>
    </div>
    <div class="metric-card">
      <div class="value" :style="{ color: (health?.issues?.length || 0) > 5 ? '#ef4444' : '#4f46e5' }">
        {{ health ? health.issues.length : '-' }}
      </div>
      <div class="label">问题数</div>
    </div>
    <div class="metric-card">
      <div class="value" :style="{ color: slowTotal > 10 ? '#ef4444' : '#4f46e5' }">{{ slowTotal }}</div>
      <div class="label">慢查询</div>
    </div>
    <div class="metric-card">
      <div class="value" :style="{ color: securityRisks > 5 ? '#ef4444' : '#4f46e5' }">{{ securityRisks }}</div>
      <div class="label">安全风险</div>
    </div>
  </div>

  <!-- 图表区域 -->
  <div class="chart-grid">
    <div class="card">
      <h2>📈 资源趋势 (24h)</h2>
      <div class="chart-container" v-if="health">
        <ChartWidget type="line" :data="lineChartData" :options="lineOptions" />
      </div>
      <div v-else class="loading">加载中...</div>
    </div>
    <div class="card">
      <h2>🎯 健康分布</h2>
      <div class="chart-container chart-container-sm" v-if="health">
        <ChartWidget type="doughnut" :data="doughnutData" :options="doughnutOptions" />
      </div>
      <div v-else class="loading">加载中...</div>
    </div>
  </div>

  <!-- 进度条 -->
  <div class="card">
    <h2>📊 关键指标</h2>
    <div class="progress-grid">
      <div v-for="item in diagnosisItems" :key="item.label" class="progress-item">
        <div class="progress-header">
          <span>{{ item.label }}</span>
          <span>{{ item.value.toFixed(0) }}{{ item.unit }}/{{ item.max }}{{ item.unit }}</span>
        </div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: Math.min(100, item.value / item.max * 100) + '%', background: item.color }"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- 快速操作 -->
  <div class="card">
    <h2>⚡ 快速操作</h2>
    <div class="action-grid">
      <button v-for="a in quickActions" :key="a.key" class="action-btn" @click="runQuickAction(a.key)">
        <span class="action-icon">{{ a.icon }}</span>
        <span class="action-label">{{ a.label }}</span>
      </button>
    </div>
    <div v-if="showQuickResult" class="result-box">
      <pre>{{ quickResult }}</pre>
    </div>
  </div>
</template>

<style scoped>
.btn-active { background: #dcfce7; border-color: #22c55e; color: #166534; }
[data-theme="dark"] .btn-active { background: #0a2613; color: #4ade80; border-color: #22c55e; }

.chart-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart-container { height: 250px; }
.chart-container-sm { height: 250px; max-width: 300px; margin: 0 auto; }

.progress-grid { display: grid; gap: 20px; }
.progress-header { display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 6px; color: var(--text); }
.progress-bar-bg { height: 10px; background: var(--border); border-radius: 5px; overflow: hidden; }
.progress-bar-fill { height: 100%; border-radius: 5px; transition: width 0.5s ease; }

.action-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.action-btn {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 20px 16px; border: 1px solid var(--border); border-radius: 12px;
  background: var(--bg-card); cursor: pointer; transition: all 0.2s;
}
.action-btn:hover { border-color: var(--primary); background: var(--table-hover); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(79,70,229,0.1); }
.action-icon { font-size: 28px; }
.action-label { font-size: 14px; font-weight: 500; color: var(--text); }
.result-box { margin-top: 16px; background: var(--table-hover); padding: 12px; border-radius: 8px; }
.result-box pre { font-size: 13px; overflow-x: auto; max-height: 300px; margin: 0; }

@media (max-width: 768px) {
  .chart-grid { grid-template-columns: 1fr; }
  .chart-container-sm { max-width: 250px; }
}
</style>