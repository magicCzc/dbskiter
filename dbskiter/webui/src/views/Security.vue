<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, severityClass } from '@/api'
import type { Risk } from '@/types'

const db = ref('default')
const risks = ref<Risk[]>([])
const totalRisks = ref(0)
const criticalCount = ref(0)
const highCount = ref(0)
const loading = ref(false)
const error = ref('')

const score = () => Math.max(0, 100 - criticalCount.value * 20 - highCount.value * 10 - risks.value.length * 2)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.security(db.value)
    risks.value = data.risks
    totalRisks.value = data.total_risks
    criticalCount.value = data.critical_count
    highCount.value = data.high_count
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
    <div class="metric-card"><div class="value">{{ totalRisks }}</div><div class="label">风险总数</div></div>
    <div class="metric-card"><div class="value">{{ criticalCount }}</div><div class="label">严重风险</div></div>
    <div class="metric-card"><div class="value">{{ highCount }}</div><div class="label">高风险</div></div>
    <div class="metric-card"><div class="value">{{ score() }}</div><div class="label">安全评分</div></div>
  </div>

  <div class="card">
    <h2>风险列表</h2>
    <table>
      <thead><tr><th>级别</th><th>描述</th><th>分类</th><th>当前值</th><th>建议值</th></tr></thead>
      <tbody>
        <tr v-if="risks.length === 0"><td colspan="5" style="text-align:center;color:#64748b;">未发现安全风险</td></tr>
        <tr v-for="(r, i) in risks" :key="i">
          <td><span :class="'badge ' + severityClass(r.severity)">{{ r.severity }}</span></td>
          <td>{{ r.description }}</td>
          <td>{{ r.category }}</td>
          <td><code style="font-size:12px;">{{ r.current_value }}</code></td>
          <td><code style="font-size:12px;">{{ r.recommended_value }}</code></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>