<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import {
  NCard, NDataTable, NButton, NSpace, NSelect, NInput, NForm, NFormItem,
  NGrid, NGi, NEmpty, NTag, NText, NIcon, NAlert, NSpin,
} from 'naive-ui'
import { CloudUploadOutline, RefreshOutline } from '@vicons/ionicons5'
import { api, formatBytes, severityClass } from '@/api'
import { useDatabaseStore } from '@/stores/database'
import type { BackupRecord } from '@/types'

const dbStore = useDatabaseStore()

const backupType = ref('full')
const tables = ref('')
const backups = ref<BackupRecord[]>([])
const loading = ref(false)
const backing = ref(false)
const result = ref<{ type: 'success' | 'error' | 'info'; msg: string } | null>(null)

async function createBackup() {
  backing.value = true
  result.value = null
  try {
    const data = await api.createBackup(dbStore.current, backupType.value, tables.value || undefined)
    if (data.success) {
      result.value = { type: 'success', msg: `备份成功！\nID: ${data.backup_id}\n文件: ${data.file_path}\n大小: ${formatBytes(data.file_size)}` }
      console.log("SUCCESS:", '备份创建成功')
    } else {
      result.value = { type: 'error', msg: `备份失败: ${data.error || '未知错误'}` }
      console.error("ERROR:", '备份失败')
    }
    await loadBackups()
  } catch (e: any) {
    result.value = { type: 'error', msg: `错误: ${e.message}` }
  } finally {
    backing.value = false
  }
}

async function loadBackups() {
  loading.value = true
  try {
    const data = await api.listBackups(dbStore.current)
    backups.value = data.backups || []
  } catch (e: any) {
    // 静默
  } finally {
    loading.value = false
  }
}

const columns = [
  {
    title: '备份 ID',
    key: 'backup_id',
    width: 200,
    ellipsis: { tooltip: true },
    render: (row: BackupRecord) => h('code', { style: 'font-size:11px' }, row.backup_id || '-'),
  },
  {
    title: '类型',
    key: 'backup_type',
    width: 100,
    render: (row: BackupRecord) => h(NTag, { type: 'info', size: 'small' }, { default: () => row.backup_type || 'full' }),
  },
  {
    title: '文件路径',
    key: 'file_path',
    ellipsis: { tooltip: true },
  },
  {
    title: '大小',
    key: 'file_size',
    width: 100,
    render: (row: BackupRecord) => formatBytes(row.file_size || 0),
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row: BackupRecord) => h(NTag, {
      type: row.success ? 'success' : 'error', size: 'small',
    }, { default: () => row.success ? '✅ 成功' : '❌ 失败' }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: () => h(NButton, { size: 'tiny', quaternary: true }, { default: () => '验证' }),
  },
]

onMounted(loadBackups)
</script>

<template>
  <NSpace vertical :size="16">
    <NCard>
      <NSpace align="center" wrap>
        <NIcon size="20" color="#4F46E5"><CloudUploadOutline /></NIcon>
        <NText style="font-weight:600;font-size:16px">创建备份</NText>
      </NSpace>
      <NDivider style="margin: 16px 0 12px 0" />
      <NGrid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" item-responsive>
        <NGi span="4 m:1">
          <NFormItem label="数据库">
            <NSelect v-model:value="dbStore.current" :options="dbStore.databases.map((d: string) => ({ label: d, value: d }))" size="small" />
          </NFormItem>
        </NGi>
        <NGi span="4 m:1">
          <NFormItem label="备份类型">
            <NSelect v-model:value="backupType" :options="[
              { label: '全量备份', value: 'full' },
              { label: '增量备份', value: 'incremental' },
              { label: '表级备份', value: 'table' },
            ]" size="small" />
          </NFormItem>
        </NGi>
        <NGi span="4 m:1">
          <NFormItem label="表名（可选）">
            <NInput v-model:value="tables" placeholder="users,orders" size="small" />
          </NFormItem>
        </NGi>
        <NGi span="4 m:1" style="display:flex;align-items:flex-end">
          <NButton type="primary" size="small" :loading="backing" @click="createBackup" block>
            <template #icon><NIcon><CloudUploadOutline /></NIcon></template>
            开始备份
          </NButton>
        </NGi>
      </NGrid>
      <NAlert v-if="result" :type="result.type" :title="result.type === 'success' ? '备份成功' : '备份失败'" style="margin-top:16px;white-space:pre-line">
        {{ result.msg }}
      </NAlert>
    </NCard>

    <NCard>
      <NSpace align="center" justify="space-between" style="margin-bottom:16px">
        <NSpace align="center">
          <NText style="font-weight:600">备份记录</NText>
          <NTag size="small">{{ backups.length }}</NTag>
        </NSpace>
        <NButton size="small" @click="loadBackups" :loading="loading">
          <template #icon><NIcon><RefreshOutline /></NIcon></template>
          刷新
        </NButton>
      </NSpace>
      <NDataTable :columns="columns" :data="backups" :loading="loading" :bordered="false" size="medium" />
      <NEmpty v-if="!loading && backups.length === 0" description="暂无备份记录" />
    </NCard>
  </NSpace>
</template>