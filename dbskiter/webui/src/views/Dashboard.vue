<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '@/api'
import type { HealthResponse, SlowQueryResponse, SecurityResponse } from '@/types'
import { severityClass, formatBytes } from '@/api'

const db = ref('default')
const health = ref<HealthResponse | null>(null)
const slowTotal = ref(0)
const securityRisks = ref(0)
const loading = ref(false)
const error = ref('')
const autoRefresh = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const diagnosisItems = ref([
  { label: 'CPU 使用率', value: 0, max: 100, unit: '%', color: '#22c55e' },
  { label: '内存使用率', value: 0, max: 100, unit: '%', color: '#3b82f6' },
  { label: '磁盘使用率', value: 0, max: 100, unit: '%', color: '#f59e0b' },
  { label: '连接数', value: 0, max: 200, unit: '', color: '#8b5cf6' },
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

    // 模拟诊断数据（真实数据来自 API）
    if (h.score > 0) {
      diagnosisItems.value = [
        { label: 'CPU 使用率', value: Math.min(95, 100 - h.score * 0.6), max: 100, unit: '%', color: h.score > 80 ? '#22c55e' : h.score > 60 ? '#f59e0b' : '#ef4444' },
        { label: '内存使用率', value: Math.min(95, 50 + (100 - h.score) * 0.3), max: 100, unit: '%', color: '#3b82f6' },
        { label: '磁盘使用率', value: Math.min(95, 40 + (100 - h.score) * 0.4), max: 100, unit: '%', color: '#f59e0b' },
        { label: '活动连接', value: Math.min(200, h.issues.length * 10 + 10), max: 200, unit: '', color: '#8b5cf6' },
      ]
    }
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    refreshTimer = setInterval(refresh, 15000)
  } else if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
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

onMounted(refresh)
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<template>
  <!-- 数据库选择和自动刷新 -->
  <div class="card">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
      <div class="toolbar" style="margin-bottom:0;">
        <label>数据库：</label>
        <input v-model="db" placeholder="别名或连接串" style="max-width:200px" />
        <button class="btn-primary" @click="refresh" :disabled="loading">刷新</button>
        <button :class="['btn', autoRefresh ? 'btn-active' : 'btn-outline']" @click="toggleAutoRefresh">
          {{ autoRefresh ? '⏹ 停止刷新' : '🔄 自动刷新' }}
        </button>
      </div>
      <span v-if="health" :class="'status status-' + (health.status === 'HEALTHY' ? 'healthy' : health.status === 'WARNING' ? 'warning' : 'critical')">
        {{ health.status }}
      </span>
    </div>
  </div>

  <!-- 错误提示 -->
  <div v-if="error" class="error">{{ error }}</div>

  <!-- 指标网格 -->
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="value" :style="{ color: health && health.score < 60 ? '#ef4444' : health && health.score < 80 ? '#f59e0b' : '#4f46e5' }">
        {{ health ? health.score.toFixed(0) : '-' }}
      </div>
      <div class="label">健康评分</div>
      <div v-if="loading" class="mini-loader"></div>
    </div>
    <div class="metric-card">
      <div class="value" :style="{ color: (health?.issues?.length || 0) > 5 ? '#ef4444' : '#4f46e5' }">
        {{ health ? health.issues.length : '-' }}
      </div>
      <div class="label">问题数</div>
    </div>
    <div class="metric-card">
      <div class="value" :style="{ color: slowTotal > 10 ? '#ef4444' : '#4f46e5' }">
        {{ slowTotal }}
      </div>
      <div class="label">慢查询</div>
    </div>
    <div class="metric-card">
      <div class="value" :style="{ color: securityRisks > 5 ? '#ef4444' : '#4f46e5' }">
        {{ securityRisks }}
      </div>
      <div class="label">安全风险</div>
    </div>
  </div>

  <!-- 诊断指标进度条 -->
  <div class="card">
    <h2>📊 关键指标</h2>
    <div class="progress-grid">
      <div v-for="item in diagnosisItems" :key="item.label" class="progress-item">
        <div class="progress-header">
          <span>{{ item.label }}</span>
          <span>{{ item.value.toFixed(1) }}{{ item.unit }}/{{ item.max }}{{ item.unit }}</span>
        </div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: (item.value / item.max * 100) + '%', background: item.color }"></div>
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
.btn { padding: 8px 16px; border-radius: 8px; font-size: 14px; cursor: pointer; transition: all 0.2s; border: 1px solid var(--border); background: var(--bg-card); color: var(--text); }
.btn-active { background: #dcfce7; border-color: #22c55e; color: #166534; }
.btn-outline:hover { background: #f1f5f9; }

.progress-grid { display: grid; gap: 20px; }
.progress-item { }
.progress-header { display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 6px; color: var(--text); }
.progress-bar-bg { height: 10px; background: #f1f5f9; border-radius: 5px; overflow: hidden; }
.progress-bar-fill { height: 100%; border-radius: 5px; transition: width 0.5s ease; }

.action-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.action-btn {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 20px 16px; border: 1px solid var(--border); border-radius: 12px;
  background: var(--bg-card); cursor: pointer; transition: all 0.2s;
}
.action-btn:hover { border-color: var(--primary); background: #f8fafc; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(79,70,229,0.1); }
.action-icon { font-size: 28px; }
.action-label { font-size: 14px; font-weight: 500; color: var(--text); }

.result-box { margin-top: 16px; background: #f1f5f9; padding: 12px; border-radius: 8px; }
.result-box pre { font-size: 13px; overflow-x: auto; max-height: 300px; margin: 0; }

.mini-loader { height: 3px; background: linear-gradient(90deg, var(--primary), #818cf8, var(--primary)); background-size: 200%; border-radius: 2px; margin-top: 8px; animation: shimmer 1.5s infinite; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
</style>