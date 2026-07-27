<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, PieChart, BarChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const router = useRouter()
const dbStore = useDatabaseStore()
const loading = ref(false)
const health = ref<any>(null)
const slowTotal = ref(0)
const securityRisks = ref(0)
const topSqlData = ref<any[]>([])
const allDatabases = ref<any[]>([])
const loadingAll = ref(false)
const autoRefresh = ref(false)
const activeTab = ref('overview')
let refreshTimer: ReturnType<typeof setInterval> | null = null

const trendData = ref({
  cpu: [45, 52, 78, 85, 72, 55, 48],
  memory: [62, 65, 70, 75, 73, 68, 64],
  disk: [55, 55, 56, 56, 57, 57, 58],
  qps: [1200, 1500, 3200, 4500, 3800, 2500, 1800],
})

const lineOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { bottom: 0, textStyle: { fontSize: 11 } },
  grid: { left: 36, right: 12, top: 16, bottom: 36 },
  xAxis: { type: 'category', data: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '现在'], axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', min: 0, max: 100, splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }, axisLabel: { fontSize: 10 } },
  series: [
    { name: 'CPU', type: 'line', data: trendData.value.cpu, smooth: true, lineStyle: { color: '#EF4444', width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(239,68,68,0.2)' }, { offset: 1, color: 'rgba(239,68,68,0)' }] } }, symbol: 'none' },
    { name: '内存', type: 'line', data: trendData.value.memory, smooth: true, lineStyle: { color: '#3B82F6', width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(59,130,246,0.2)' }, { offset: 1, color: 'rgba(59,130,246,0)' }] } }, symbol: 'none' },
    { name: '磁盘', type: 'line', data: trendData.value.disk, smooth: true, lineStyle: { color: '#F59E0B', width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(245,158,11,0.2)' }, { offset: 1, color: 'rgba(245,158,11,0)' }] } }, symbol: 'none' },
  ],
}))

const barOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 36, right: 12, top: 12, bottom: 28 },
  xAxis: { type: 'category', data: allDatabases.value.map((d: any) => d.name), axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', min: 0, max: 100, splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }, axisLabel: { fontSize: 10 } },
  series: [{
    type: 'bar', data: allDatabases.value.map((d: any) => ({
      value: d.score || 0,
      itemStyle: { color: d.score >= 80 ? '#22C55E' : d.score >= 60 ? '#F59E0B' : '#EF4444', borderRadius: [4, 4, 0, 0] }
    })),
    barWidth: '60%',
    label: { show: true, position: 'top', formatter: '{c}', fontSize: 10 },
  }],
}))

const quickActions = [
  { label: '实时诊断', icon: '🔍', path: '/diagnose', color: '#6366f1' },
  { label: '慢查询', icon: '🐢', path: '/slow-queries', color: '#f59e0b' },
  { label: '安全审计', icon: '🔒', path: '/security', color: '#ef4444' },
  { label: '备份管理', icon: '💾', path: '/backup', color: '#22c55e' },
  { label: '任务调度', icon: '⏰', path: '/scheduler', color: '#3b82f6' },
  { label: '数据库', icon: '🗄️', path: '/databases', color: '#8b5cf6' },
]

async function loadAllDatabases() {
  loadingAll.value = true
  try {
    const resp = await fetch('/api/health/all')
    const data = await resp.json()
    allDatabases.value = data.databases || []
  } catch { /* 静默 */ }
  finally { loadingAll.value = false }
}

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
    try { const top = await api.topSql(dbStore.current, 5); topSqlData.value = top.data?.raw_metrics?.top_sql || [] } catch {}
  } catch (e: any) { ElMessage.error(`加载失败: ${e.message}`) }
  finally { loading.value = false }
}

async function refreshAll() {
  await Promise.all([refresh(), loadAllDatabases()])
}

function toggleAuto() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) { ElMessage.success('自动刷新已开启 (15s)'); refreshTimer = setInterval(refreshAll, 15000) }
  else { ElMessage.info('自动刷新已关闭'); if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null } }
}

onMounted(() => { dbStore.loadDatabases(); refreshAll() })
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<template>
  <div class="page">
    <div class="control-bar">
      <div class="control-left">
        <label>数据库：</label>
        <el-select v-model="dbStore.current" size="small" style="width:180px" @change="refresh">
          <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button type="primary" size="small" :loading="loading" @click="refreshAll">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-switch v-model="autoRefresh" @change="toggleAuto" active-text="自动刷新" />
      </div>
      <el-tag v-if="health" :type="health.score >= 80 ? 'success' : health.score >= 60 ? 'warning' : 'danger'" size="large" effect="dark" round>
        {{ health.score >= 80 ? '🟢 健康' : health.score >= 60 ? '🟡 警告' : '🔴 异常' }}
      </el-tag>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" type="border-card" style="margin-bottom:20px">
      <!-- 概览 Tab -->
      <el-tab-pane label="📊 概览" name="overview">
        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-value" :style="{ color: health && health.score < 60 ? '#ef4444' : health && health.score < 80 ? '#f59e0b' : '#22c55e' }">
              {{ health ? health.score.toFixed(0) : '-' }}
            </div>
            <div class="kpi-label">健康评分</div>
            <el-progress :percentage="health?.score || 0" :stroke-width="4" :show-text="false"
              :color="health && health.score > 80 ? '#22C55E' : health && health.score > 60 ? '#F59E0B' : '#EF4444'" />
            <div class="kpi-sub">CPU · 内存 · 磁盘 · 连接</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value" :style="{ color: (health?.issues?.length || 0) > 5 ? '#ef4444' : '#6366f1' }">
              {{ health ? health.issues.length : '-' }}
            </div>
            <div class="kpi-label">待处理问题</div>
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
            <el-tag :type="securityRisks > 5 ? 'danger' : securityRisks > 0 ? 'warning' : 'success'" size="small" effect="dark">
              {{ securityRisks > 5 ? '需立即处理' : securityRisks > 0 ? '需关注' : '安全' }}
            </el-tag>
          </div>
        </div>

        <div class="chart-grid" style="margin-bottom:20px">
          <el-card shadow="never" class="section-card">
            <template #header><span>📈 资源趋势 (24h)</span></template>
            <VChart :option="lineOption" autoresize style="height:260px" />
          </el-card>
          <el-card shadow="never" class="section-card">
            <template #header><span>⚡ 快速操作</span></template>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div v-for="a in quickActions" :key="a.path" class="action-item" @click="router.push(a.path)">
                <span class="action-icon">{{ a.icon }}</span>
                <span class="action-label">{{ a.label }}</span>
              </div>
            </div>
          </el-card>
        </div>

        <!-- TOP SQL -->
        <el-card shadow="never" class="section-card">
          <template #header><span>🏆 TOP SQL（按耗时降序）</span></template>
          <div v-if="topSqlData.length > 0">
            <div v-for="(sql, i) in topSqlData.slice(0, 5)" :key="i" class="sql-item">
              <span class="sql-rank">{{ i + 1 }}</span>
              <code class="sql-text">{{ (sql.sql || sql.query || '').substring(0, 80) }}{{ (sql.sql || '').length > 80 ? '...' : '' }}</code>
              <span class="sql-time">{{ (sql.execution_time || sql.total_time || 0).toFixed(2) }}s</span>
              <span class="sql-count">{{ sql.execution_count || 0 }} 次</span>
            </div>
          </div>
          <div v-else class="empty-state" style="padding:20px">
            <div class="icon">📊</div>
            <div class="desc">暂无 TOP SQL 数据</div>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 全部数据库 Tab -->
      <el-tab-pane label="🗄️ 全部数据库" name="all">
        <div v-loading="loadingAll" style="min-height:200px">
          <div class="kpi-grid">
            <div v-for="db in allDatabases" :key="db.name" class="kpi-card" @click="dbStore.setCurrent(db.name); refresh()" style="cursor:pointer">
              <div class="kpi-value" :style="{ color: db.score >= 80 ? '#22c55e' : db.score >= 60 ? '#f59e0b' : '#ef4444' }">
                {{ db.score.toFixed(0) }}
              </div>
              <div class="kpi-label">{{ db.name }}</div>
              <el-tag :type="db.status === 'HEALTHY' ? 'success' : db.status === 'WARNING' ? 'warning' : 'danger'" size="small" effect="dark">
                {{ db.status || 'UNKNOWN' }}
              </el-tag>
              <div v-if="db.issues?.length" class="kpi-issues">{{ db.issues.length }} 个问题</div>
            </div>
          </div>
          <!-- 对比柱状图 -->
          <el-card shadow="never" class="section-card" style="margin-top:16px">
            <template #header><span>📊 数据库健康对比</span></template>
            <VChart :option="barOption" autoresize style="height:250px" />
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.action-item {
  display: flex; align-items: center; gap: 10px; padding: 14px 12px;
  border: 1px solid var(--el-border-color-light); border-radius: 10px;
  cursor: pointer; transition: all 0.2s;
}
.action-item:hover { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); transform: translateY(-1px); }
.action-icon { font-size: 22px; }
.action-label { font-size: 14px; font-weight: 500; }

.sql-item { display: flex; align-items: center; gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.sql-item:last-child { border-bottom: none; }
.sql-rank { width: 24px; height: 24px; border-radius: 50%; background: var(--el-color-primary-light-8); color: var(--el-color-primary); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; flex-shrink: 0; }
.sql-text { font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--el-text-color-secondary); }
.sql-time { font-size: 13px; font-weight: 600; color: var(--el-color-warning); white-space: nowrap; margin-left: 12px; }
.sql-count { font-size: 12px; color: var(--el-text-color-placeholder); white-space: nowrap; }

.kpi-trend { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 4px; }
.kpi-sub { font-size: 11px; color: var(--el-text-color-placeholder); margin-top: 8px; }
.kpi-issues { font-size: 11px; color: var(--el-color-danger); margin-top: 4px; }

@media (max-width: 768px) {
  [style*="grid-template-columns: 1fr 1fr"] { grid-template-columns: 1fr !important; }
}
</style>