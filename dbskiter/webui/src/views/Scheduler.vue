<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, formatDuration, severityClass } from '@/api'
import type { Task, LogEntry } from '@/types'

const db = ref('default')
const hours = ref(72)
const tasks = ref<Task[]>([])
const logs = ref<LogEntry[]>([])
const loading = ref(false)
const activeTab = ref<'tasks' | 'logs'>('tasks')

async function load() {
  loading.value = true
  try {
    const [td, ld] = await Promise.all([
      api.tasks(db.value),
      api.logs(db.value, hours.value),
    ])
    tasks.value = td.tasks || []
    logs.value = ld.logs || []
  } catch { /* 静默 */ }
  finally { loading.value = false }
}

function statusClass(status: string) {
  const s = status.toUpperCase()
  if (s === 'SUCCESS' || s === 'ENABLED' || s === 'RUNNING') return 'badge-low'
  if (s === 'FAILED' || s === 'DISABLED') return 'badge-critical'
  return 'badge-medium'
}

onMounted(load)
</script>

<template>
  <div class="card">
    <h2>⏰ 任务调度</h2>
    <div class="toolbar">
      <label>数据库：</label>
      <input v-model="db" style="max-width:200px" />
      <button class="btn-primary" @click="load" :disabled="loading">刷新</button>
    </div>
  </div>

  <!-- Tab 切换 -->
  <div class="tabs">
    <button :class="['tab', { active: activeTab === 'tasks' }]" @click="activeTab = 'tasks'">📋 定时任务</button>
    <button :class="['tab', { active: activeTab === 'logs' }]" @click="activeTab = 'logs'">📝 操作日志</button>
  </div>

  <!-- 任务列表 -->
  <div v-if="activeTab === 'tasks'" class="card">
    <h2>任务列表 <span class="count-badge">{{ tasks.length }}</span></h2>
    <div v-if="loading" class="loading">
      <div class="skeleton-row" v-for="i in 3" :key="i"></div>
    </div>
    <table v-else>
      <thead><tr><th>任务名</th><th>类型</th><th>调度计划</th><th>状态</th><th>上次执行</th><th>下次执行</th></tr></thead>
      <tbody>
        <tr v-if="tasks.length === 0"><td colspan="6" class="empty">暂无定时任务</td></tr>
        <tr v-for="t in tasks" :key="t.name">
          <td><strong>{{ t.name || '-' }}</strong></td>
          <td><span class="cat-tag">{{ t.task_type || '-' }}</span></td>
          <td><code>{{ t.schedule || '-' }}</code></td>
          <td><span :class="'badge ' + statusClass(t.status)">{{ t.status }}</span></td>
          <td style="font-size:13px;">{{ t.last_run || '-' }}</td>
          <td style="font-size:13px;">{{ t.next_run || '-' }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- 操作日志 -->
  <div v-if="activeTab === 'logs'" class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="margin:0;">操作日志</h2>
      <select v-model="hours" @change="load" style="width:auto;">
        <option :value="24">24 小时</option>
        <option :value="72">3 天</option>
        <option :value="168">7 天</option>
      </select>
    </div>
    <table>
      <thead><tr><th>时间</th><th>命令</th><th>数据库</th><th>状态</th><th>耗时</th></tr></thead>
      <tbody>
        <tr v-if="logs.length === 0"><td colspan="5" class="empty">暂无操作日志</td></tr>
        <tr v-for="(l, i) in logs.slice(0, 30)" :key="i">
          <td style="font-size:13px;">{{ l.timestamp }}</td>
          <td><code style="font-size:12px;">{{ l.command }}</code></td>
          <td>{{ l.database }}</td>
          <td><span :class="'badge ' + (l.status_code === 0 ? 'badge-low' : 'badge-critical')">{{ l.status_code === 0 ? '✅ 成功' : '❌ 失败' }}</span></td>
          <td>{{ l.execution_time_ms ? formatDuration(l.execution_time_ms) : '-' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.tabs { display: flex; gap: 4px; margin-bottom: 16px; background: var(--bg-card); border-radius: 8px; padding: 4px; border: 1px solid var(--border); }
.tab { flex: 1; padding: 10px; border: none; border-radius: 6px; background: transparent; cursor: pointer; font-size: 14px; color: var(--text-secondary); transition: all 0.2s; }
.tab.active { background: var(--primary); color: white; }
.tab:hover:not(.active) { background: #f1f5f9; }
.count-badge { background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-left: 8px; }
.cat-tag { background: #f1f5f9; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.empty { text-align: center; color: #64748b; padding: 40px; }
.skeleton-row { height: 48px; background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%); background-size: 200%; border-radius: 4px; margin-bottom: 8px; animation: shimmer 1.5s infinite; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
</style>