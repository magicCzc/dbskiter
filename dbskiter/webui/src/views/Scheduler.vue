<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import {
  NCard, NDataTable, NButton, NSpace, NTag, NSelect, NTabs, NTabPane,
  NEmpty, NText, useMessage, NIcon, NGrid, NGi, NStatistic,
} from 'naive-ui'
import { TimeOutline, RefreshOutline } from '@vicons/ionicons5'
import { api, formatDuration } from '@/api'
import { useDatabaseStore } from '@/stores/database'
import type { Task, LogEntry } from '@/types'

const dbStore = useDatabaseStore()
const message = useMessage()

const tasks = ref<Task[]>([])
const logs = ref<LogEntry[]>([])
const hours = ref(72)
const activeTab = ref('tasks')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const [td, ld] = await Promise.all([
      api.tasks(dbStore.current),
      api.logs(dbStore.current, hours.value),
    ])
    tasks.value = td.tasks || []
    logs.value = ld.logs || []
  } catch (e: any) {
    message.error(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

function statusClass(status: string): string {
  const s = status?.toUpperCase() || ''
  if (s === 'SUCCESS' || s === 'ENABLED' || s === 'RUNNING') return 'success'
  if (s === 'FAILED' || s === 'DISABLED') return 'error'
  return 'warning'
}

const taskColumns = [
  {
    title: '任务名',
    key: 'name',
    width: 200,
    render: (row: Task) => h('strong', null, row.name || '-'),
  },
  {
    title: '类型',
    key: 'task_type',
    width: 120,
  },
  {
    title: '调度计划',
    key: 'schedule',
    width: 150,
    render: (row: Task) => h('code', { style: 'font-size:12px' }, row.schedule || '-'),
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row: Task) => h(NTag, { type: statusClass(row.status) as any, size: 'small' }, { default: () => row.status }),
  },
  {
    title: '上次执行',
    key: 'last_run',
    width: 180,
  },
  {
    title: '下次执行',
    key: 'next_run',
    width: 180,
  },
]

const logColumns = [
  { title: '时间', key: 'timestamp', width: 200 },
  {
    title: '命令',
    key: 'command',
    ellipsis: { tooltip: true },
    render: (row: LogEntry) => h('code', { style: 'font-size:11px' }, row.command || '-'),
  },
  { title: '数据库', key: 'database', width: 120 },
  {
    title: '状态',
    key: 'status_code',
    width: 100,
    render: (row: LogEntry) => h(NTag, {
      type: row.status_code === 0 ? 'success' : 'error', size: 'small',
    }, { default: () => row.status_code === 0 ? '✅ 成功' : '❌ 失败' }),
  },
  {
    title: '耗时',
    key: 'execution_time_ms',
    width: 100,
    render: (row: LogEntry) => row.execution_time_ms ? formatDuration(row.execution_time_ms) : '-',
  },
]

onMounted(load)
</script>

<template>
  <NSpace vertical :size="16">
    <NCard>
      <NSpace align="center" justify="space-between">
        <NSpace align="center">
          <NIcon size="20" color="#4F46E5"><TimeOutline /></NIcon>
          <NText style="font-weight:600;font-size:16px">任务调度</NText>
        </NSpace>
        <NSpace align="center">
          <NText>数据库:</NText>
          <NSelect
            :value="dbStore.current"
            :options="dbStore.databases.map((d: string) => ({ label: d, value: d }))"
            style="width:160px" size="small"
            @update:value="(v: string) => { dbStore.setCurrent(v); load() }"
          />
          <NButton type="primary" size="small" :loading="loading" @click="load">
            <template #icon><NIcon><RefreshOutline /></NIcon></template>
            刷新
          </NButton>
        </NSpace>
      </NSpace>
    </NCard>

    <NGrid :cols="3" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <NGi span="3 m:1">
        <NCard>
          <NStatistic label="定时任务" :value="tasks.length">
            <template #prefix><span style="font-size:24px">📋</span></template>
          </NStatistic>
        </NCard>
      </NGi>
      <NGi span="3 m:1">
        <NCard>
          <NStatistic label="操作日志" :value="logs.length">
            <template #prefix><span style="font-size:24px">📝</span></template>
          </NStatistic>
        </NCard>
      </NGi>
      <NGi span="3 m:1">
        <NCard>
          <NStatistic label="时间范围" :value="`${hours}h`">
            <template #prefix><span style="font-size:24px">⏱️</span></template>
          </NStatistic>
        </NCard>
      </NGi>
    </NGrid>

    <NCard>
      <NTabs v-model:value="activeTab" type="line" animated>
        <NTabPane name="tasks" tab="📋 定时任务">
          <NDataTable :columns="taskColumns" :data="tasks" :loading="loading" :bordered="false" size="medium" />
          <NEmpty v-if="!loading && tasks.length === 0" description="暂无定时任务" />
        </NTabPane>
        <NTabPane name="logs" tab="📝 操作日志">
          <NSpace align="center" style="margin-bottom:12px">
            <NText>时间范围:</NText>
            <NSelect v-model:value="hours" :options="[
              { label: '24 小时', value: 24 },
              { label: '3 天', value: 72 },
              { label: '7 天', value: 168 },
            ]" size="small" style="width:120px" @update:value="load" />
          </NSpace>
          <NDataTable :columns="logColumns" :data="logs.slice(0, 30)" :loading="loading" :bordered="false" size="medium" />
          <NEmpty v-if="!loading && logs.length === 0" description="暂无操作日志" />
        </NTabPane>
      </NTabs>
    </NCard>
  </NSpace>
</template>