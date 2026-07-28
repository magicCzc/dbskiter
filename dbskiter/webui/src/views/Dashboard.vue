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
import StatCard from '@/components/StatCard.vue'
import SectionCard from '@/components/SectionCard.vue'

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
const lastUpdated = ref('')
const autoRefresh = ref(false)
const recentActivity = ref<LogEntry[]>([])
let refreshTimer: ReturnType<typeof setInterval> | null = null

const healthScore = computed(() => health?.value?.score ?? 0)

const healthColor = computed(() => {
  if (healthScore.value >= 80) return 'var(--color-success-500)'
  if (healthScore.value >= 60) return 'var(--color-warning-500)'
  return 'var(--color-danger-500)'
})

const alertColor = computed(() => {
  if (alertStats.value.critical > 0) return 'var(--color-danger-500)'
  return 'var(--color-brand-500)'
})

const slowColor = computed(() => {
  if (slowTotal.value > 10) return 'var(--color-danger-500)'
  return 'var(--color-warning-500)'
})

const securityColor = computed(() => {
  if (securityRisks.value > 5) return 'var(--color-danger-500)'
  return 'var(--color-brand-500)'
})

const dbHealthOption = computed(() => {
  const dbs = dbStore.databases.map(name => ({
    name, score: name === dbStore.current ? healthScore.value : 0,
  }))
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 30, right: 10, top: 8, bottom: 25 },
    xAxis: { type: 'category', data: dbs.map(d => d.name), axisLabel: { fontSize: 10 } },
    yAxis: {
      type: 'value', min: 0, max: 100,
      splitLine: { lineStyle: { color: 'var(--color-gray-100)', type: 'dashed' } },
      axisLabel: { fontSize: 10 },
    },
    series: [{
      type: 'bar',
      data: dbs.map(d => ({
        value: d.score,
        itemStyle: {
          color: d.score >= 80 ? 'var(--color-success-500)' : d.score >= 60 ? 'var(--color-warning-500)' : 'var(--color-danger-500)',
          borderRadius: [4, 4, 0, 0],
        },
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
    <!-- 页面标题 -->
    <div class="dashboard-header">
      <div class="dashboard-header__left">
        <h1 class="dashboard-title">仪表盘</h1>
        <span class="dashboard-subtitle" v-if="lastUpdated">{{ lastUpdated }} 更新</span>
      </div>
      <div class="dashboard-header__right">
        <el-switch v-model="autoRefresh" @change="toggleAuto" size="small" active-text="自动刷新" />
        <el-button size="small" :loading="loading" @click="refresh">刷新</el-button>
      </div>
    </div>

    <!-- 告警横幅 -->
    <div v-if="alertStats.critical > 0" class="alert-banner alert-banner--critical">
      {{ alertStats.critical }} 个严重告警，{{ alertStats.open }} 个未处理
      <el-button size="small" plain @click="navigateTo('/alerts')" style="margin-left: auto">查看告警</el-button>
    </div>
    <div v-else-if="alertStats.warning > 0" class="alert-banner alert-banner--warning">
      {{ alertStats.warning }} 个警告，{{ alertStats.open }} 个未处理
      <el-button size="small" plain @click="navigateTo('/alerts')" style="margin-left: auto">查看告警</el-button>
    </div>

    <!-- KPI 卡片 -->
    <div class="stat-grid">
      <StatCard
        :value="healthScore.toFixed(0)"
        label="健康评分"
        subtitle="点击查看详情"
        :color="healthColor"
        :loading="loading"
        to="/diagnose"
        @click="navigateTo('/diagnose')"
      />
      <StatCard
        :value="alertStats.open"
        label="未处理告警"
        :subtitle="alertStats.critical > 0 ? `含 ${alertStats.critical} 个严重` : ''"
        :color="alertColor"
        :loading="loading"
        to="/alerts"
        @click="navigateTo('/alerts')"
      />
      <StatCard
        :value="slowTotal"
        label="慢查询"
        subtitle="最近 1 小时"
        :color="slowColor"
        :loading="loading"
        to="/slow-queries"
        @click="navigateTo('/slow-queries')"
      />
      <StatCard
        :value="securityRisks"
        label="安全风险"
        :subtitle="securityRisks > 0 ? '需要关注' : '安全'"
        :color="securityColor"
        :loading="loading"
        to="/security"
        @click="navigateTo('/security')"
      />
    </div>

    <!-- 第二行：系统概览 + 快速操作 -->
    <div class="row-grid">
      <SectionCard title="系统概览">
        <div class="overview-grid">
          <div class="overview-item" @click="navigateTo('/databases')">
            <span class="overview-value">{{ dbCount }}</span>
            <span class="overview-label">数据库</span>
          </div>
          <div class="overview-item" @click="navigateTo('/scheduler')">
            <span class="overview-value">{{ taskCount }}</span>
            <span class="overview-label">定时任务</span>
          </div>
          <div class="overview-item" @click="navigateTo('/users')">
            <span class="overview-value">-</span>
            <span class="overview-label">用户</span>
          </div>
          <div class="overview-item" @click="navigateTo('/alerts')">
            <span class="overview-value" :style="{ color: alertStats.open > 0 ? 'var(--color-danger-500)' : 'var(--color-success-500)' }">
              {{ alertStats.open }}
            </span>
            <span class="overview-label">告警</span>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="快速操作">
        <div class="quick-actions">
          <div class="quick-action" @click="navigateTo('/diagnose')">实时诊断</div>
          <div class="quick-action" @click="navigateTo('/slow-queries')">慢查询</div>
          <div class="quick-action" @click="navigateTo('/sql-editor')">SQL 编辑器</div>
          <div class="quick-action" @click="navigateTo('/security')">安全审计</div>
          <div class="quick-action" @click="navigateTo('/alerts')">告警管理</div>
          <div class="quick-action" @click="navigateTo('/scheduler')">定时任务</div>
        </div>
      </SectionCard>
    </div>

    <!-- 第三行：数据库健康 + 最近活动 -->
    <div class="row-grid">
      <SectionCard title="数据库健康">
        <VChart :option="dbHealthOption" autoresize style="height:200px" />
      </SectionCard>

      <SectionCard title="最近活动">
        <div v-if="recentActivity.length > 0" class="activity-list">
          <div v-for="(item, i) in recentActivity" :key="i" class="activity-item">
            <span class="activity-cmd">{{ item.command || '-' }}</span>
            <span class="activity-db">{{ item.database || '' }}</span>
            <span class="activity-time">{{ item.timestamp ? item.timestamp.replace('T', ' ').substring(11, 19) : '' }}</span>
          </div>
        </div>
        <div v-else class="activity-empty">暂无活动记录</div>
      </SectionCard>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}
.dashboard-header__left {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}
.dashboard-title {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}
.dashboard-subtitle {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.dashboard-header__right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

/* 告警横幅 */
.alert-banner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-5);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}
.alert-banner--critical {
  background: var(--color-danger-50);
  color: var(--color-danger-700);
  border: 1px solid var(--color-danger-500);
}
.alert-banner--warning {
  background: var(--color-warning-50);
  color: var(--color-warning-700);
  border: 1px solid var(--color-warning-500);
}

/* KPI 网格 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

/* 双列网格 */
.row-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
  margin-bottom: var(--space-5);
}

/* 系统概览 */
.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}
.overview-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}
.overview-item:hover {
  border-color: var(--color-brand-300);
  background: var(--color-brand-50);
}
.overview-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  color: var(--color-brand-500);
}
.overview-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

/* 快速操作 */
.quick-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}
.quick-action {
  padding: var(--space-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  text-align: center;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  transition: border-color var(--transition-fast), background var(--transition-fast);
}
.quick-action:hover {
  border-color: var(--color-brand-300);
  background: var(--color-brand-50);
  color: var(--color-brand-500);
}

/* 活动列表 */
.activity-list {
  display: flex;
  flex-direction: column;
}
.activity-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-muted);
  font-size: var(--text-xs);
}
.activity-item:last-child { border-bottom: none; }
.activity-cmd { flex: 1; font-weight: var(--font-medium); color: var(--text-primary); }
.activity-db { color: var(--text-tertiary); }
.activity-time { color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.activity-empty {
  text-align: center;
  padding: var(--space-5);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}

@media (max-width: 1024px) {
  .row-grid { grid-template-columns: 1fr; }
}
</style>