<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api, severityClass } from '@/api'
import type { Risk } from '@/types'

const db = ref('default')
const risks = ref<Risk[]>([])
const loading = ref(false)
const error = ref('')
const filterLevel = ref('all')

const totalRisks = computed(() => risks.value.length)
const criticalCount = computed(() => risks.value.filter(r => r.severity === 'critical').length)
const highCount = computed(() => risks.value.filter(r => r.severity === 'high').length)
const score = computed(() => Math.max(0, 100 - criticalCount.value * 20 - highCount.value * 10 - risks.value.length * 2))

const filteredRisks = computed(() => {
  if (filterLevel.value === 'all') return risks.value
  return risks.value.filter(r => r.severity === filterLevel.value)
})

const riskSummary = computed(() => ({
  critical: criticalCount.value,
  high: highCount.value,
  medium: risks.value.filter(r => r.severity === 'medium').length,
  low: risks.value.filter(r => r.severity === 'low').length,
}))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.security(db.value)
    risks.value = data.risks
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="card">
    <h2>🔒 安全审计</h2>
    <div class="toolbar">
      <label>数据库：</label>
      <input v-model="db" style="max-width:200px" />
      <button class="btn-primary" @click="load" :disabled="loading">执行审计</button>
    </div>
  </div>

  <div class="metrics-grid">
    <div class="metric-card">
      <div class="value" :style="{ color: score < 60 ? '#ef4444' : score < 80 ? '#f59e0b' : '#22c55e' }">{{ score }}</div>
      <div class="label">安全评分</div>
    </div>
    <div class="metric-card"><div class="value">{{ totalRisks }}</div><div class="label">风险总数</div></div>
    <div class="metric-card"><div class="value">{{ criticalCount }}</div><div class="label">严重风险</div></div>
    <div class="metric-card"><div class="value">{{ highCount }}</div><div class="label">高风险</div></div>
  </div>

  <!-- 风险分布 -->
  <div class="card">
    <h2>风险分布</h2>
    <div class="dist-bar">
      <div v-if="criticalCount > 0" class="dist-seg" style="background:#ef4444;flex:{{ criticalCount }}">{{ criticalCount }} 严重</div>
      <div v-if="highCount > 0" class="dist-seg" style="background:#f59e0b;flex:{{ highCount }}">{{ highCount }} 高</div>
      <div v-if="riskSummary.medium > 0" class="dist-seg" style="background:#3b82f6;flex:{{ riskSummary.medium }}">{{ riskSummary.medium }} 中</div>
      <div v-if="riskSummary.low > 0" class="dist-seg" style="background:#22c55e;flex:{{ riskSummary.low }}">{{ riskSummary.low }} 低</div>
      <div v-if="totalRisks === 0" class="dist-seg" style="background:#e2e8f0;flex:1">无风险</div>
    </div>
  </div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="margin:0;">风险列表</h2>
      <select v-model="filterLevel" style="width:auto;">
        <option value="all">全部级别</option>
        <option value="critical">严重</option>
        <option value="high">高</option>
        <option value="medium">中</option>
        <option value="low">低</option>
      </select>
    </div>
    <table>
      <thead><tr><th>级别</th><th>描述</th><th>分类</th><th>当前值</th><th>建议值</th></tr></thead>
      <tbody>
        <tr v-if="filteredRisks.length === 0"><td colspan="5" class="empty">未发现匹配的风险</td></tr>
        <tr v-for="(r, i) in filteredRisks" :key="i">
          <td><span :class="'badge ' + severityClass(r.severity)">{{ r.severity }}</span></td>
          <td>{{ r.description }}</td>
          <td><span class="cat-tag">{{ r.category }}</span></td>
          <td><code>{{ r.current_value }}</code></td>
          <td><code>{{ r.recommended_value }}</code></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.dist-bar { display: flex; height: 32px; border-radius: 8px; overflow: hidden; }
.dist-seg { display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: 600; min-width: 60px; }
.cat-tag { background: #f1f5f9; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.empty { text-align: center; color: #64748b; padding: 40px; }
</style>