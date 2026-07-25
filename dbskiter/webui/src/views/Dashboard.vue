<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'

const db = ref('default')
const health = ref<any>(null)
const slowTotal = ref(0)
const securityRisks = ref(0)
const loading = ref(false)
const error = ref('')
const quickResult = ref('')
const showQuickResult = ref(false)

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
  } finally {
    loading.value = false
  }
}

async function quickAction(action: string) {
  showQuickResult.value = true
  quickResult.value = '执行中...'
  try {
    let data: any
    switch (action) {
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
</script>

<template>
  <div class="card">
    <div class="toolbar">
      <label>数据库：</label>
      <input v-model="db" placeholder="数据库别名" style="max-width:200px" />
      <button class="btn-primary" @click="refresh" :disabled="loading">刷新</button>
      <span v-if="health" :class="'status status-' + (health.status === 'HEALTHY' ? 'healthy' : health.status === 'WARNING' ? 'warning' : 'critical')">
        {{ health.status }}
      </span>
    </div>
  </div>

  <div class="metrics-grid">
    <div class="metric-card">
      <div class="value">{{ health ? health.score.toFixed(0) : '-' }}</div>
      <div class="label">健康评分</div>
    </div>
    <div class="metric-card">
      <div class="value">{{ health ? health.issues.length : '-' }}</div>
      <div class="label">问题数</div>
    </div>
    <div class="metric-card">
      <div class="value">{{ slowTotal }}</div>
      <div class="label">慢查询</div>
    </div>
    <div class="metric-card">
      <div class="value">{{ securityRisks }}</div>
      <div class="label">安全风险</div>
    </div>
  </div>

  <div class="card">
    <h2>⚡ 快速操作</h2>
    <div class="toolbar">
      <button class="btn-primary" @click="quickAction('health')">🏥 健康检查</button>
      <button class="btn-primary" @click="quickAction('slow')">🐢 慢查询分析</button>
      <button class="btn-primary" @click="quickAction('security')">🔒 安全审计</button>
      <button class="btn-primary" @click="quickAction('diagnose')">🔍 实时诊断</button>
    </div>
    <pre v-if="showQuickResult" style="background:#f1f5f9;padding:12px;border-radius:4px;font-size:13px;overflow-x:auto;max-height:300px;margin-top:16px;">{{ quickResult }}</pre>
  </div>
</template>