<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import {
  NCard, NDataTable, NButton, NSpace, NTag, NSelect,
  NStatistic, NGrid, NGi, NEmpty, NInput,
} from 'naive-ui'
import { SearchOutline, RefreshOutline } from '@vicons/ionicons5'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import type { SlowQuery } from '@/types'
import {  } from 'naive-ui'

const dbStore = useDatabaseStore()

const queries = ref<SlowQuery[]>([])
const top = ref(10)
const hours = ref(1)
const loading = ref(false)
const searchText = ref('')

const filteredQueries = computed(() => {
  if (!searchText.value) return queries.value
  return queries.value.filter(q => q.sql?.toLowerCase().includes(searchText.value.toLowerCase()))
})

const summary = computed(() => {
  const total = filteredQueries.value.length
  const maxTime = total ? Math.max(...filteredQueries.value.map(q => q.execution_time || 0)) : 0
  const avgTime = total
    ? filteredQueries.value.reduce((s, q) => s + (q.execution_time || 0), 0) / total
    : 0
  const totalRows = filteredQueries.value.reduce((s, q) => s + (q.rows_examined || 0), 0)
  return { total, maxTime, avgTime, totalRows }
})

async function load() {
  loading.value = true
  try {
    const data = await api.slowQueries(dbStore.current, top.value, hours.value)
    queries.value = data.queries
  } catch (e: any) {
    console.error("ERROR:", `加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

const columns = [
  {
    title: '#',
    key: 'index',
    width: 60,
    render: (_: any, index: number) => index + 1,
  },
  {
    title: 'SQL',
    key: 'sql',
    ellipsis: { tooltip: true },
    render: (row: SlowQuery) => h('code', { style: 'font-size:12px;' }, row.sql),
  },
  {
    title: '总耗时',
    key: 'execution_time',
    width: 110,
    sorter: (a: any, b: any) => a.execution_time - b.execution_time,
    render: (row: SlowQuery) => h('span', {
      style: `color: ${row.execution_time > 5 ? '#EF4444' : row.execution_time > 2 ? '#F59E0B' : '#22C55E'}; font-weight: 600;`,
    }, `${row.execution_time.toFixed(2)}s`),
  },
  {
    title: '次数',
    key: 'execution_count',
    width: 80,
    sorter: (a: any, b: any) => a.execution_count - b.execution_count,
  },
  {
    title: '平均耗时',
    key: 'avg_time',
    width: 100,
    render: (row: SlowQuery) => `${row.avg_time.toFixed(2)}s`,
  },
  {
    title: '扫描行数',
    key: 'rows_examined',
    width: 100,
    sorter: (a: any, b: any) => a.rows_examined - b.rows_examined,
    render: (row: SlowQuery) => row.rows_examined.toLocaleString(),
  },
]

onMounted(load)
</script>

<template>
  <NSpace vertical :size="16">
    <NCard>
      <NSpace align="center" wrap>
        <NText>数据库:</NText>
        <NSelect
          :value="dbStore.current"
          :options="dbStore.databases.map((d: string) => ({ label: d, value: d }))"
          style="width:160px" size="small"
          @update:value="(v: string) => { dbStore.setCurrent(v); load() }"
        />
        <NText>数量:</NText>
        <NSelect v-model:value="top" :options="[
          { label: 'Top 5', value: 5 },
          { label: 'Top 10', value: 10 },
          { label: 'Top 20', value: 20 },
          { label: 'Top 50', value: 50 },
        ]" style="width:100px" size="small" @update:value="load" />
        <NText>时间:</NText>
        <NSelect v-model:value="hours" :options="[
          { label: '1 小时', value: 1 },
          { label: '6 小时', value: 6 },
          { label: '24 小时', value: 24 },
          { label: '3 天', value: 72 },
        ]" style="width:100px" size="small" @update:value="load" />
        <NButton type="primary" size="small" :loading="loading" @click="load">
          <template #icon><NIcon><RefreshOutline /></NIcon></template>
          查询
        </NButton>
        <NInput v-model:value="searchText" placeholder="搜索 SQL" size="small" style="width:200px" clearable>
          <template #prefix><NIcon><SearchOutline /></NIcon></template>
        </NInput>
      </NSpace>
    </NCard>

    <NGrid :cols="4" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <NGi span="4 m:1"><NCard><NStatistic label="慢查询数" :value="summary.total" /></NCard></NGi>
      <NGi span="4 m:1"><NCard><NStatistic label="最慢耗时" :value="summary.maxTime ? summary.maxTime.toFixed(2) + 's' : '-'" /></NCard></NGi>
      <NGi span="4 m:1"><NCard><NStatistic label="平均耗时" :value="summary.avgTime ? summary.avgTime.toFixed(2) + 's' : '-'" /></NCard></NGi>
      <NGi span="4 m:1"><NCard><NStatistic label="总扫描行" :value="summary.totalRows.toLocaleString()" /></NCard></NGi>
    </NGrid>

    <NCard title="慢查询列表">
      <NDataTable
        :columns="columns"
        :data="filteredQueries"
        :loading="loading"
        :pagination="{ pageSize: 20 }"
        :bordered="false"
        size="medium"
      />
      <NEmpty v-if="!loading && filteredQueries.length === 0" description="暂无慢查询数据" />
    </NCard>
  </NSpace>
</template>