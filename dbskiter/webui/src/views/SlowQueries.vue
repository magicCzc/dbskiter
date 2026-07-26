<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api'
import type { SlowQuery } from '@/types'

const db = ref("default")
const databases = ref<string[]>(["default"])
const top = ref(10)
const hours = ref(6)
const queries = ref<SlowQuery[]>([])
const loading = ref(false)
const error = ref('')
const sortField = ref<'execution_time' | 'execution_count' | 'avg_time' | 'rows_examined'>('execution_time')
const sortDir = ref<'desc' | 'asc'>('desc')
const expandedSql = ref<number | null>(null)

const sortedQueries = computed(() => {
  return [...queries.value].sort((a, b) => {
    const val = (a[sortField.value] || 0) - (b[sortField.value] || 0)
    return sortDir.value === 'desc' ? -val : val
  })
})

function toggleSort(field: typeof sortField.value) {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortField.value = field
    sortDir.value = 'desc'
  }
}

function sortIcon(field: string) {
  if (sortField.value !== field) return '↕'
  return sortDir.value === 'desc' ? '↓' : '↑'
}

const summary = computed(() => ({
  total: queries.value.length,
  maxTime: queries.value.length ? Math.max(...queries.value.map(q => q.execution_time || 0)) : 0,
  avgTime: queries.value.length
    ? queries.value.reduce((s, q) => s + (q.execution_time || 0), 0) / queries.value.length
    : 0,
  totalRows: queries.value.reduce((s, q) => s + (q.rows_examined || 0), 0),
}))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.slowQueries(db.value, top.value, hours.value)
    queries.value = data.queries
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function formatSql(sql: string, maxLen = 60): string {
  return sql.length > maxLen ? sql.substring(0, maxLen) + '...' : sql
}

onMounted(() => {
  load()
  api.databases().then(d => { if (d.databases?.length) databases.value = d.databases }).catch(() => {})
})
</script>

<template>
  <div class="card">
    <h2>🐢 慢查询分析</h2>
    <div class="toolbar">
      <label>数据库：</label>
      <select v-model="db" style="max-width:200px"><option v-for="d in databases" :key="d" :value="d">{{ d }}</option></select>
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
    <div class="metric-card"><div class="value">{{ summary.total }}</div><div class="label">慢查询总数</div></div>
    <div class="metric-card"><div class="value">{{ summary.maxTime ? summary.maxTime.toFixed(2) + 's' : '-' }}</div><div class="label">最慢耗时</div></div>
    <div class="metric-card"><div class="value">{{ summary.avgTime ? summary.avgTime.toFixed(2) + 's' : '-' }}</div><div class="label">平均耗时</div></div>
    <div class="metric-card"><div class="value">{{ summary.totalRows.toLocaleString() }}</div><div class="label">总扫描行数</div></div>
  </div>

  <div class="card">
    <h2>慢查询列表 <span class="count-badge">{{ queries.length }}</span></h2>
    <div v-if="loading" class="loading">
      <div class="skeleton-row" v-for="i in 5" :key="i"></div>
    </div>
    <table v-else>
      <thead>
        <tr>
          <th>#</th>
          <th>SQL</th>
          <th class="sortable" @click="toggleSort('execution_time')">总耗时 {{ sortIcon('execution_time') }}</th>
          <th class="sortable" @click="toggleSort('execution_count')">次数 {{ sortIcon('execution_count') }}</th>
          <th class="sortable" @click="toggleSort('avg_time')">平均耗时 {{ sortIcon('avg_time') }}</th>
          <th class="sortable" @click="toggleSort('rows_examined')">扫描行数 {{ sortIcon('rows_examined') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="queries.length === 0"><td colspan="6" class="empty">暂无数据</td></tr>
        <template v-for="(q, i) in sortedQueries" :key="i">
          <tr @click="expandedSql = expandedSql === i ? null : i" class="clickable">
            <td>{{ i + 1 }}</td>
            <td><code>{{ formatSql(q.sql || '') }}</code></td>
            <td class="num">{{ q.execution_time.toFixed(2) }}s</td>
            <td class="num">{{ q.execution_count }}</td>
            <td class="num">{{ q.avg_time.toFixed(2) }}s</td>
            <td class="num">{{ q.rows_examined.toLocaleString() }}</td>
          </tr>
          <tr v-if="expandedSql === i" class="expanded-row">
            <td colspan="6">
              <div class="expanded-sql">
                <strong>完整 SQL:</strong>
                <pre>{{ q.sql }}</pre>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.count-badge { background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-left: 8px; }
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--primary); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.clickable { cursor: pointer; }
.expanded-row td { background: #f8fafc; padding: 0; }
.expanded-sql { padding: 16px; }
.expanded-sql pre { background: #f1f5f9; padding: 12px; border-radius: 4px; font-size: 13px; overflow-x: auto; margin-top: 8px; white-space: pre-wrap; }
.empty { text-align: center; color: #64748b; padding: 40px; }
.skeleton-row { height: 48px; background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%); background-size: 200%; border-radius: 4px; margin-bottom: 8px; animation: shimmer 1.5s infinite; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
</style>