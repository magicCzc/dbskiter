<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'
import type { SlowQuery } from '@/types'

const db = ref('default')
const top = ref(10)
const hours = ref(6)
const queries = ref<SlowQuery[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.slowQueries(db.value, top.value, hours.value)
    queries.value = data.queries
    total.value = data.total
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const maxTime = () => queries.value.length ? Math.max(...queries.value.map(q => q.execution_time || 0)) : 0
const avgTime = () => queries.value.length
  ? queries.value.reduce((s, q) => s + (q.execution_time || 0), 0) / queries.value.length
  : 0
const totalRows = () => queries.value.reduce((s, q) => s + (q.rows_examined || 0), 0)

onMounted(load)
</script>

<template>
  <div class="card">
    <h2>🐢 慢查询分析</h2>
    <div class="toolbar">
      <label>数据库：</label>
      <input v-model="db" style="max-width:200px" />
      <label>数量：</label>
      <select v-model="top">
        <option :value="5">Top 5</option>
        <option :value="10">Top 10</option>
        <option :value="20">Top 20</option>
        <option :value="50">Top 50</option>
      </select>
      <label>时间：</label>
      <select v-model="hours">
        <option :value="1">1 小时</option>
        <option :value="6">6 小时</option>
        <option :value="24">24 小时</option>
        <option :value="72">3 天</option>
      </select>
      <button class="btn-primary" @click="load" :disabled="loading">查询</button>
    </div>
  </div>

  <div class="metrics-grid">
    <div class="metric-card"><div class="value">{{ total }}</div><div class="label">慢查询总数</div></div>
    <div class="metric-card"><div class="value">{{ maxTime() ? maxTime().toFixed(2) + 's' : '-' }}</div><div class="label">最慢耗时</div></div>
    <div class="metric-card"><div class="value">{{ avgTime() ? avgTime().toFixed(2) + 's' : '-' }}</div><div class="label">平均耗时</div></div>
    <div class="metric-card"><div class="value">{{ totalRows().toLocaleString() }}</div><div class="label">总扫描行数</div></div>
  </div>

  <div class="card">
    <h2>慢查询列表</h2>
    <table>
      <thead>
        <tr><th>#</th><th>SQL</th><th>总耗时</th><th>次数</th><th>平均耗时</th><th>扫描行数</th></tr>
      </thead>
      <tbody>
        <tr v-if="queries.length === 0"><td colspan="6" style="text-align:center;color:#64748b;">暂无数据</td></tr>
        <tr v-for="(q, i) in queries" :key="i">
          <td>{{ i + 1 }}</td>
          <td><code style="font-size:12px;">{{ (q.sql || '').substring(0, 80) }}{{ (q.sql || '').length > 80 ? '...' : '' }}</code></td>
          <td>{{ q.execution_time.toFixed(2) }}s</td>
          <td>{{ q.execution_count }}</td>
          <td>{{ q.avg_time.toFixed(2) }}s</td>
          <td>{{ q.rows_examined.toLocaleString() }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>