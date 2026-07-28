<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDatabaseStore } from '@/stores/database'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { HealthResponse, AlertStatsResponse, LogEntry } from '@/types'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const router = useRouter()
const dbStore = useDatabaseStore()
const auth = useAuthStore()

const loading = ref(false)
const health = ref<HealthResponse | null>(null)
const slowTotal = ref(0)
const securityRisks = ref(0)
const alertStats = ref<AlertStatsResponse['stats']>({ open: 0, critical: 0, warning: 0, total: 0 })
const taskCount = ref(0)
const dbCount = ref(0)
const userCount = ref(0)
const lastUpdated = ref('')
const autoRefresh = ref(false)
const recentActivity = ref<LogEntry[]>([])
let refreshTimer: ReturnType<typeof setInterval> | null = null

const healthScore = computed(() => health?.value?.score ?? 0)

const dbHealthOption = computed(() => {
  const dbs = dbStore.databases.map(name => ({
    name, score: name === dbStore.current ? healthScore.value : 0,
  }))
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 30, right: 10, top: 8, bottom: 25 },
    xAxis: { type: 'category', data: dbs.map(d => d.name), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 100, splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }, axisLabel: { fontSize: 10 } },
    series: [{
      type: 'bar', data: dbs.map(d => ({
        value: d.score, itemStyle: { color: d.score >= 80 ? '#22C55E' : d.score >= 60 ? '#F59E0B' : '#EF4444', borderRadius: [4, 4, 0, 0] },
      })),
      barWidth: '50%',
    }],
  }
})

async function loadSummary() {
  try {
    const [h, s, sec, alerts, tasks, dbs] = await Promise.all([
      api.health(dbStore.current),
      api.slowQueries(dbStore.current, 5, 1),
      api.security(dbStore.current),
      api.getAlertStats().catch(() => ({ stats: { open: 0, critical: 0, warning: 0, total: 0 } })),
      api.tasks().catch(() => ({ tasks: [] })),
      api.databases(),
    ])
    health.value = h
    slowTotal.value = s.total
    securityRisks.value = sec.total_risks
    alertStats.value = alerts.stats || { open: 0, critical: 0, warning: 0, total: 0 }
    taskCount.value = tasks.tasks?.length || 0
    dbCount.value = dbs.databases?.length || 0
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
  }
}

async function loadActivity() {
  try {
    const data: { logs?: LogEntry[]; data?: LogEntry[]; [key: string]: any } = await api.logs(dbStore.current, 24)
    const raw = data.logs || data.data || []
    recentActivity.value = (Array.isArray(raw) ? raw : []).slice(0, 8) as LogEntry[]
  } catch { /* 静默 */ }
}

async function refresh() {
  loading.value = true
  await Promise.all([loadSummary(), loadActivity()])
  loading.value = false
}

function toggleAuto() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    refreshTimer = setInterval(refresh, 30000)
  } else {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  }
}

function navigateTo(path: string) {
  router.push(path)
}

onMounted(() => { dbStore.loadDatabases(); refresh() })
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<template>
  <div class="page">
    <!-- 实时反馈 -->
    <div class="live-bar">
      <span class="live-dot" :class="{ active: autoRefresh }"></span>
      <span class="live-text" v-if="lastUpdated">{{ lastUpdated }} 更新</span>
      <el-switch v-model="autoRefresh" @change="toggleAuto" size="small" active-text="自动" inactive-text="" style="margin-left:8px" />
    </div>

    <!-- 告警横幅 -->
    <div v-if="alertStats.critical > 0" class="alert-banner error">
      🔴 {{ alertStats.critical }} 个严重告警，{{ alertStats.open }} 个未处理
      <el-button size="small" plain @click="navigateTo('/alerts')" style="margin-left:12px">查看告警</el-button>
    </div>
    <div v-else-if="alertStats.warning > 0" class="alert-banner warning">
      🟡 {{ alertStats.warning }} 个警告，{{ alertStats.open }} 个未处理
      <el-button size="small" plain @click="navigateTo('/alerts')" style="margin-left:12px">查看告警</el-button>
    </div>

    <!-- 系统状态卡片 -->
    <div class="stats-grid">
      <div class="stat-card" @click="navigateTo('/diagnose')">
        <div class="stat-value" :style="{ color: healthScore >= 80 ? '#22c55e' : healthScore >= 60 ? '#f59e0b' : '#ef4444' }">
          {{ healthScore.toFixed(0) }}
        </div>
        <div class="stat-label">健康评分</div>
        <div class="stat-sub">点击查看详情</div>
      </div>
      <div class="stat-card" @click="navigateTo('/alerts')">
        <div class="stat-value" :style="{ color: alertStats.critical > 0 ? '#ef4444' : '#6366f1' }">{{ alertStats.open }}</div>
        <div class="stat-label">未处理告警</div>
        <div class="stat-sub" v-if="alertStats.critical > 0">含 {{ alertStats.critical }} 个严重</div>
      </div>
      <div class="stat-card" @click="navigateTo('/slow-queries')">
        <div class="stat-value" :style="{ color: slowTotal > 10 ? '#ef4444' : '#f59e0b' }">{{ slowTotal }}</div>
        <div class="stat-label">慢查询</div>
        <div class="stat-sub">最近 1 小时</div>
      </div>
      <div class="stat-card" @click="navigateTo('/security')">
        <div class="stat-value" :style="{ color: securityRisks > 5 ? '#ef4444' : '#6366f1' }">{{ securityRisks }}</div>
        <div class="stat-label">安全风险</div>
        <div class="stat-sub">{{ securityRisks > 0 ? '需要关注' : '安全' }}</div>
      </div>
    </div>

    <!-- 第二行：系统概览 + 快速操作 -->
    <div class="row-grid">
      <!-- 系统概览 -->
      <el-card shadow="never" class="section-card">
        <template #header><span>📊 系统概览</span></template>
        <div class="overview-grid">
          <div class="overview-item" @click="navigateTo('/databases')">
            <span class="overview-icon">🗄️</span>
            <span class="overview-value">{{ dbCount }}</span>
            <span class="overview-label">数据库</span>
          </div>
          <div class="overview-item" @click="navigateTo('/scheduler')">
            <span class="overview-icon">⏰</span>
            <span class="overview-value">{{ taskCount }}</span>
            <span class="overview-label">定时任务</span>
          </div>
          <div class="overview-item" @click="navigateTo('/users')">
            <span class="overview-icon">👥</span>
            <span class="overview-value" v-if="auth.isAdmin">-</span>
            <span class="overview-label">用户</span>
          </div>
          <div class="overview-item" @click="navigateTo('/alerts')">
            <span class="overview-icon">🔔</span>
            <span class="overview-value" :style="{ color: alertStats.open > 0 ? '#ef4444' : '#22c55e' }">{{ alertStats.open }}</span>
            <span class="overview-label">告警</span>
          </div>
        </div>
      </el-card>

      <!-- 快速操作 -->
      <el-card shadow="never" class="section-card">
        <template #header><span>⚡ 快速操作</span></template>
        <div class="quick-actions">
          <div class="quick-action" @click="navigateTo('/diagnose')">🔍 实时诊断</div>
          <div class="quick-action" @click="navigateTo('/slow-queries')">🐢 慢查询</div>
          <div class="quick-action" @click="navigateTo('/sql-editor')">⌨️ SQL 编辑器</div>
          <div class="quick-action" @click="navigateTo('/security')">🔒 安全审计</div>
          <div class="quick-action" @click="navigateTo('/alerts')">🔔 告警管理</div>
          <div class="quick-action" @click="navigateTo('/scheduler')">⏰ 定时任务</div>
        </div>
      </el-card>
    </div>

    <!-- 第三行：数据库健康 + 最近活动 -->
    <div class="row-grid">
      <el-card shadow="never" class="section-card">
        <template #header><span>🏥 数据库健康</span></template>
        <VChart :option="dbHealthOption" autoresize style="height:200px" />
      </el-card>

      <el-card shadow="never" class="section-card">
        <template #header><span>🕐 最近活动</span></template>
        <div v-if="recentActivity.length > 0">
          <div v-for="(item, i) in recentActivity" :key="i" class="activity-item">
            <span class="activity-cmd">{{ item.command || '-' }}</span>
            <span class="activity-db">{{ item.database || '' }}</span>
            <span class="activity-time">{{ item.timestamp ? item.timestamp.replace('T', ' ').substring(11, 19) : '' }}</span>
          </div>
        </div>
        <div v-else class="empty-state">暂无活动记录</div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }

.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #94a3b8; }
.live-dot.active { background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }

.alert-banner {
  display: flex; align-items: center; padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px;
}
.alert-banner.error { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
.alert-banner.warning { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }
.stat-card {
  background: var(--el-bg-color); border-radius: 10px; padding: 20px; border: 1px solid var(--el-border-color-light);
  text-align: center; cursor: pointer; transition: all 0.2s;
}
.stat-card:hover { border-color: var(--el-color-primary); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.stat-value { font-size: 36px; font-weight: 700; }
.stat-label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }
.stat-sub { font-size: 11px; color: var(--el-text-color-placeholder); margin-top: 4px; }

.row-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
.section-card { margin-bottom: 0; }

.overview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.overview-item {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 16px; border: 1px solid var(--el-border-color-light); border-radius: 8px;
  cursor: pointer; transition: all 0.15s;
}
.overview-item:hover { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.overview-icon { font-size: 24px; }
.overview-value { font-size: 24px; font-weight: 700; color: var(--el-color-primary); }
.overview-label { font-size: 12px; color: var(--el-text-color-secondary); }

.quick-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.quick-action {
  padding: 12px; border: 1px solid var(--el-border-color-light); border-radius: 8px;
  cursor: pointer; text-align: center; font-size: 13px; transition: all 0.15s;
}
.quick-action:hover { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }

.activity-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--el-border-color-lighter); font-size: 12px; }
.activity-item:last-child { border-bottom: none; }
.activity-cmd { flex: 1; font-weight: 500; }
.activity-db { color: var(--el-text-color-placeholder); }
.activity-time { color: var(--el-text-color-placeholder); }

.empty-state { text-align: center; padding: 20px; color: var(--el-text-color-placeholder); }

@media (max-width: 1024px) { .row-grid { grid-template-columns: 1fr; } }
</style>