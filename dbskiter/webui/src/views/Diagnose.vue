<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  NCard, NButton, NSpace, NSelect, NText, NTag, NSpin, NEmpty,
  NGrid, NGi, NStatistic, useMessage, NIcon, NAlert, NCode,
} from 'naive-ui'
import { SearchOutline, ReloadOutline } from '@vicons/ionicons5'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'

const dbStore = useDatabaseStore()
const message = useMessage()

const loading = ref(false)
const error = ref('')
const result = ref<any>(null)

async function runDiagnose() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const data = await api.diagnose(dbStore.current)
    result.value = data
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  dbStore.loadDatabases()
})
</script>

<template>
  <NSpace vertical :size="16">
    <NCard>
      <NSpace align="center" justify="space-between">
        <NSpace align="center">
          <NIcon size="20" color="#4F46E5"><SearchOutline /></NIcon>
          <NText style="font-weight:600;font-size:16px">实时诊断</NText>
        </NSpace>
        <NSpace align="center">
          <NText>数据库:</NText>
          <NSelect
            :value="dbStore.current"
            :options="dbStore.databases.map((d: string) => ({ label: d, value: d }))"
            style="width:160px" size="small"
            @update:value="(v: string) => dbStore.setCurrent(v)"
          />
          <NButton type="primary" size="small" :loading="loading" @click="runDiagnose">
            <template #icon><NIcon><SearchOutline /></NIcon></template>
            开始诊断
          </NButton>
        </NSpace>
      </NSpace>
    </NCard>

    <NAlert v-if="error" type="error" closable>{{ error }}</NAlert>

    <!-- 诊断结果摘要 -->
    <NGrid v-if="result?.data" :cols="4" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <NGi span="4 m:1">
        <NCard><NStatistic label="健康评分" :value="result.data.score || result.data.health_score || '-'">
          <template #prefix><span style="font-size:24px">🏥</span></template>
        </NStatistic></NCard>
      </NGi>
      <NGi span="4 m:1">
        <NCard><NStatistic label="问题数" :value="result.data.issues?.length || result.data.warnings?.length || 0" /></NCard>
      </NGi>
      <NGi span="4 m:1">
        <NCard><NStatistic label="慢查询" :value="result.data.slow_queries?.length || 0" /></NCard>
      </NGi>
      <NGi span="4 m:1">
        <NCard><NStatistic label="锁等待" :value="result.data.locks?.length || result.data.lock_waits || 0" /></NCard>
      </NGi>
    </NGrid>

    <!-- 诊断原始数据 -->
    <NCard v-if="result" title="诊断数据">
      <pre style="font-size:13px;max-height:500px;overflow:auto;background:var(--table-hover);padding:16px;border-radius:8px;margin:0">{{ JSON.stringify(result, null, 2) }}</pre>
    </NCard>

    <!-- 空状态 -->
    <NCard v-if="!result && !loading && !error" style="text-align:center;padding:60px">
      <div style="font-size:48px;margin-bottom:16px">🔍</div>
      <NText depth="3" style="font-size:16px">选择数据库并点击"开始诊断"</NText>
      <div style="margin-top:8px"><NText depth="3">将显示数据库实时健康状态</NText></div>
    </NCard>

    <!-- 加载中 -->
    <NCard v-if="loading">
      <div style="padding:40px;text-align:center">
        <NSpin size="large" />
        <div style="margin-top:12px;color:var(--text-secondary)">诊断中...</div>
      </div>
    </NCard>
  </NSpace>
</template>