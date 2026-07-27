<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  NCard, NDataTable, NButton, NSpace, NTag, NSelect, NGrid, NGi,
  NStatistic, NEmpty, NDivider, NText, useMessage, NIcon,
} from 'naive-ui'
import { ShieldCheckmarkOutline, ReloadOutline } from '@vicons/ionicons5'
import { useDatabaseStore } from '@/stores/database'
import { api, severityClass } from '@/api'
import type { Risk } from '@/types'

const dbStore = useDatabaseStore()
const message = useMessage()

const risks = ref<Risk[]>([])
const loading = ref(false)
const filterLevel = ref<string>('all')

const totalRisks = computed(() => risks.value.length)
const criticalCount = computed(() => risks.value.filter(r => r.severity === 'critical').length)
const highCount = computed(() => risks.value.filter(r => r.severity === 'high').length)
const mediumCount = computed(() => risks.value.filter(r => r.severity === 'medium').length)
const lowCount = computed(() => risks.value.filter(r => r.severity === 'low').length)
const score = computed(() => Math.max(0, 100 - criticalCount.value * 20 - highCount.value * 10 - risks.value.length * 2))

const filteredRisks = computed(() => {
  if (filterLevel.value === 'all') return risks.value
  return risks.value.filter(r => r.severity === filterLevel.value)
})

async function load() {
  loading.value = true
  try {
    const data = await api.security(dbStore.current)
    risks.value = data.risks
  } catch (e: any) {
    message.error(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

const columns = [
  {
    title: '级别',
    key: 'severity',
    width: 100,
    render: (row: Risk) => h(NTag, { type: severityClass(row.severity) as any, size: 'small' }, { default: () => row.severity }),
  },
  {
    title: '描述',
    key: 'description',
    ellipsis: { tooltip: true },
  },
  {
    title: '分类',
    key: 'category',
    width: 150,
  },
  {
    title: '当前值',
    key: 'current_value',
    width: 200,
    render: (row: Risk) => h('code', { style: 'font-size:12px' }, row.current_value || '-'),
  },
  {
    title: '建议值',
    key: 'recommended_value',
    width: 200,
    render: (row: Risk) => h('code', { style: 'font-size:12px;color:#22C55E' }, row.recommended_value || '-'),
  },
]

import { h } from 'vue'
onMounted(load)
</script>

<template>
  <NSpace vertical :size="16">
    <NCard>
      <NSpace align="center" justify="space-between">
        <NSpace align="center">
          <NIcon size="20" color="#4F46E5"><ShieldCheckmarkOutline /></NIcon>
          <NText style="font-weight:600;font-size:16px">安全审计</NText>
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
            <template #icon><NIcon><ReloadOutline /></NIcon></template>
            执行审计
          </NButton>
        </NSpace>
      </NSpace>
    </NCard>

    <NGrid :cols="4" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <NGi span="4 m:1">
        <NCard>
          <NStatistic label="安全评分" :value="score">
            <template #prefix>
              <span :style="{ color: score < 60 ? '#EF4444' : score < 80 ? '#F59E0B' : '#22C55E', fontSize: '32px' }">🛡️</span>
            </template>
          </NStatistic>
        </NCard>
      </NGi>
      <NGi span="4 m:1"><NCard><NStatistic label="风险总数" :value="totalRisks" /></NCard></NGi>
      <NGi span="4 m:1"><NCard><NStatistic label="严重风险" :value="criticalCount" /></NCard></NGi>
      <NGi span="4 m:1"><NCard><NStatistic label="高风险" :value="highCount" /></NCard></NGi>
    </NGrid>

    <NCard title="风险分布">
      <div style="display:flex;height:32px;border-radius:8px;overflow:hidden">
        <div v-if="criticalCount > 0" :style="{ background: '#EF4444', flex: criticalCount, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: '12px', fontWeight: 600, minWidth: '60px' }">
          {{ criticalCount }} 严重
        </div>
        <div v-if="highCount > 0" :style="{ background: '#F59E0B', flex: highCount, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: '12px', fontWeight: 600, minWidth: '60px' }">
          {{ highCount }} 高
        </div>
        <div v-if="mediumCount > 0" :style="{ background: '#3B82F6', flex: mediumCount, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: '12px', fontWeight: 600, minWidth: '60px' }">
          {{ mediumCount }} 中
        </div>
        <div v-if="lowCount > 0" :style="{ background: '#22C55E', flex: lowCount, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: '12px', fontWeight: 600, minWidth: '60px' }">
          {{ lowCount }} 低
        </div>
        <div v-if="totalRisks === 0" style="background:#E2E8F0;flex:1;display:flex;align-items:center;justify-content:center;color:#64748B;font-size:13px">
          ✅ 未发现风险
        </div>
      </div>
    </NCard>

    <NCard title="风险列表">
      <NSpace style="margin-bottom:16px">
        <NText>筛选级别:</NText>
        <NSelect v-model:value="filterLevel" :options="[
          { label: '全部', value: 'all' },
          { label: '严重', value: 'critical' },
          { label: '高', value: 'high' },
          { label: '中', value: 'medium' },
          { label: '低', value: 'low' },
        ]" size="small" style="width:120px" />
      </NSpace>
      <NDataTable
        :columns="columns"
        :data="filteredRisks"
        :loading="loading"
        :bordered="false"
        size="medium"
      />
      <NEmpty v-if="!loading && filteredRisks.length === 0" description="未发现匹配的风险" />
    </NCard>
  </NSpace>
</template>