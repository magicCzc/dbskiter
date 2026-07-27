<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'

const db = ref('default')
const databases = ref<string[]>(['default'])
const loading = ref(false)
const error = ref('')
const result = ref<any>(null)
const activeTab = ref<'realtime' | 'locks' | 'connections' | 'space'>('realtime')

async function runDiagnose() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const data = await api.diagnose(db.value)
    result.value = data
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function formatJson(data: any): string {
  return JSON.stringify(data, null, 2)
}

const tabs = [
  { key: 'realtime' as const, label: '实时诊断', icon: '🔍' },
  { key: 'locks' as const, label: '锁分析', icon: '🔒' },
  { key: 'connections' as const, label: '连接', icon: '🔗' },
  { key: 'space' as const, label: '空间', icon: '💾' },
]

onMounted(() => {
  api.databases().then(d => { if (d.databases?.length) databases.value = d.databases }).catch(() => {})
})
</script>

<template>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
      <h2 style="margin:0;">🔍 数据库诊断</h2>
      <div class="toolbar" style="margin-bottom:0;">
        <label>数据库：</label>
        <select v-model="db" style="max-width:200px">
          <option v-for="d in databases" :key="d" :value="d">{{ d }}</option>
        </select>
        <button class="btn-primary" @click="runDiagnose" :disabled="loading">
          {{ loading ? '诊断中...' : '▶ 开始诊断' }}
        </button>
      </div>
    </div>
  </div>

  <div v-if="error" class="error">{{ error }}</div>

  <!-- 诊断结果 -->
  <div v-if="result" class="card">
    <h2>诊断结果</h2>

    <!-- 摘要指标 -->
    <div class="metrics-grid" v-if="result.data">
      <div class="metric-card">
        <div class="value">{{ result.data.score || result.data.health_score || '-' }}</div>
        <div class="label">健康评分</div>
      </div>
      <div class="metric-card">
        <div class="value">{{ result.data.issues?.length || result.data.warnings?.length || 0 }}</div>
        <div class="label">问题数</div>
      </div>
      <div class="metric-card">
        <div class="value">{{ result.data.slow_queries?.length || 0 }}</div>
        <div class="label">慢查询</div>
      </div>
      <div class="metric-card">
        <div class="value">{{ result.data.locks?.length || result.data.lock_waits || 0 }}</div>
        <div class="label">锁等待</div>
      </div>
    </div>

    <!-- 原始数据 -->
    <div class="result-box">
      <pre>{{ formatJson(result) }}</pre>
    </div>
  </div>

  <!-- 无结果提示 -->
  <div v-if="!result && !loading && !error" class="card" style="text-align:center;padding:60px;color:var(--text-secondary);">
    <div style="font-size:48px;margin-bottom:16px;">🔍</div>
    <div style="font-size:16px;">选择数据库并点击"开始诊断"</div>
    <div style="font-size:14px;margin-top:8px;">将显示数据库实时健康状态、锁、连接和空间信息</div>
  </div>

  <!-- 加载中 -->
  <div v-if="loading" class="card">
    <div class="loading">
      <div class="skeleton" style="height:200px;width:100%;"></div>
    </div>
  </div>
</template>

<style scoped>
.result-box { margin-top: 16px; background: var(--table-hover); padding: 16px; border-radius: 8px; overflow-x: auto; }
.result-box pre { font-size: 13px; margin: 0; max-height: 500px; overflow-y: auto; }
.skeleton { background: linear-gradient(90deg, var(--skeleton-from) 25%, var(--skeleton-to) 50%, var(--skeleton-from) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 8px; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
</style>