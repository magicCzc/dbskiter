<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, formatDuration, severityClass } from '@/api'
import type { Task, LogEntry } from '@/types'

const db = ref('default')
const hours = ref(72)
const tasks = ref<Task[]>([])
const logs = ref<LogEntry[]>([])
const loading = ref(false)

async function loadTasks() {
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

onMounted(loadTasks)
</script>

<template>
  <div class="card">
    <h2>⏰ 定时任务</h2>
    <div class="toolbar">
      <label>数据库：</label>
      <input v-model="db" style="max-width:200px" />
      <button class="btn-primary" @click="loadTasks" :disabled="loading">刷新</button>
    </div>
  </div>

  <div class="card">
    <h2>任务列表</h2>
    <table>
      <thead><tr><th>任务名</th><th>类型</th><th>调度计划</th><th>状态</th><th>上次执行</th><th>下次执行</th></tr></thead>
      <tbody>
        <tr v-if="tasks.length === 0"><td colspan="6" style="text-align:center;color:#64748b;">暂无定时任务</td></tr>
        <tr v-for="t in tasks" :key="t.name">
          <td>{{ t.name || '-' }}</td>
          <td>{{ t.task_type || '-' }}</td>
          <td><code>{{ t.schedule || '-' }}</code></td>
          <td><span :class="'badge ' + severityClass(t.status)">{{ t.status }}</span></td>
          <td>{{ t.last_run || '-' }}</td>
          <td>{{ t.next_run || '-' }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>📋 操作日志</h2>
    <div class="toolbar">
      <label>时间范围：</label>
      <select v-model="hours" @change="loadTasks">
        <option :value="24">24 小时</option>
        <option :value="72">3 天</option>
        <option :value="168">7 天</option>
      </select>
    </div>
    <table>
      <thead><tr><th>时间</th><th>命令</th><th>数据库</th><th>状态</th><th>耗时</th></tr></thead>
      <tbody>
        <tr v-if="logs.length === 0"><td colspan="5" style="text-align:center;color:#64748b;">暂无操作日志</td></tr>
        <tr v-for="(l, i) in logs.slice(0, 20)" :key="i">
          <td style="font-size:13px;">{{ l.timestamp }}</td>
          <td><code style="font-size:12px;">{{ l.command }}</code></td>
          <td>{{ l.database }}</td>
          <td>
            <span :class="'badge ' + (l.status_code === 0 ? 'badge-low' : 'badge-critical')">
              {{ l.status_code === 0 ? 'success' : 'failed' }}
            </span>
          </td>
          <td>{{ l.execution_time_ms ? formatDuration(l.execution_time_ms) : '-' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>