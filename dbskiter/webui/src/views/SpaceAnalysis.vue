<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api, formatBytes } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { SpaceInfo } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatCard from '@/components/StatCard.vue'

const dbStore = useDatabaseStore()
const tables = ref<SpaceInfo[]>([])
const loading = ref(false)
const top = ref(20)
const lastUpdated = ref('')

const totalSize = computed(() => tables.value.reduce((s, t) => s + (t.total_size || 0), 0))
const maxTable = computed(() => {
  if (!tables.value.length) return null
  return tables.value.reduce((a, b) => ((a.total_size || 0) > (b.total_size || 0) ? a : b))
})
const totalDataSize = computed(() => tables.value.reduce((s, t) => s + (t.data_size || 0), 0))
const totalIndexSize = computed(() => tables.value.reduce((s, t) => s + (t.index_size || 0), 0))

const criticalTables = computed(() => tables.value.filter(t => (t.free_space ?? 100) < 10))
const warningTables = computed(() => tables.value.filter(t => {
  const f = t.free_space ?? 100
  return f >= 10 && f < 20
}))

function spaceColor(freeSpace: number): string {
  if (freeSpace < 10) return 'var(--color-danger-500)'
  if (freeSpace < 20) return 'var(--color-warning-500)'
  return 'var(--color-success-500)'
}

function rowClass(row: SpaceInfo): string {
  const f = row.free_space ?? 100
  if (f < 10) return 'row-critical'
  if (f < 20) return 'row-warning'
  return ''
}

async function load() {
  loading.value = true
  try {
    const data = await api.space(dbStore.current, top.value)
    const raw = data.data?.raw_metrics || data.raw_data || data
    tables.value = (raw.tables || raw.space_usage || []).slice(0, top.value)
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
    tables.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => { dbStore.loadDatabases(); load() })
</script>

<template>
  <div class="page">
    <el-alert
      v-if="criticalTables.length > 0"
      :title="`发现 ${criticalTables.length} 个表空闲空间不足 10%，建议立即扩容或清理`"
      type="error"
      show-icon
      closable
      class="space-alert"
    />
    <el-alert
      v-else-if="warningTables.length > 0"
      :title="`${warningTables.length} 个表空闲空间不足 20%，建议关注`"
      type="warning"
      show-icon
      closable
      class="space-alert"
    />

    <SectionCard padding>
      <div class="space-controls">
        <div class="space-controls__left">
          <label>数据库</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <label>Top</label>
          <el-select v-model="top" size="small" style="width:100px" @change="load">
            <el-option v-for="n in [10, 20, 50, 100]" :key="n" :label="`Top ${n}`" :value="n" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="space-controls__right">
          <el-tag v-if="totalSize > 0" type="info">总空间: {{ formatBytes(totalSize) }}</el-tag>
        </div>
      </div>
    </SectionCard>

    <div class="stat-grid">
      <StatCard :value="formatBytes(totalSize)" label="总空间占用" size="sm" color="var(--color-brand-500)" />
      <StatCard
        :value="maxTable ? formatBytes(maxTable.total_size) : '-'"
        :subtitle="maxTable?.table_name || ''"
        label="最大表"
        size="sm"
        color="var(--color-warning-500)"
      />
      <StatCard :value="formatBytes(totalDataSize)" label="数据大小" size="sm" color="var(--color-info-500)" />
      <StatCard :value="formatBytes(totalIndexSize)" label="索引大小" size="sm" color="var(--el-color-purple-light-3, #8b5cf6)" />
    </div>

    <SectionCard title="表空间详情">
      <template #actions>
        <el-button size="small" @click="load" :loading="loading">刷新</el-button>
      </template>
      <el-table :data="tables" v-loading="loading" stripe style="width:100%" :row-class-name="rowClass">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="table_schema" label="Schema" width="120" />
        <el-table-column prop="table_name" label="表名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="total_size" label="总大小" width="110" sortable>
          <template #default="{row}">{{ formatBytes(row.total_size || 0) }}</template>
        </el-table-column>
        <el-table-column prop="data_size" label="数据大小" width="110" sortable>
          <template #default="{row}">{{ formatBytes(row.data_size || 0) }}</template>
        </el-table-column>
        <el-table-column prop="index_size" label="索引大小" width="110" sortable>
          <template #default="{row}">{{ formatBytes(row.index_size || 0) }}</template>
        </el-table-column>
        <el-table-column prop="free_space" label="空闲空间" width="110" sortable>
          <template #default="{row}">
            <span class="space-percent" :style="{ color: spaceColor(row.free_space ?? 100) }">
              {{ (row.free_space ?? 0).toFixed(1) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{row}">
            <el-button size="small" type="primary" plain @click="ElMessage.info('分析功能将在后续版本提供')">
              分析
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.space-alert { margin-bottom: var(--space-4); }

.space-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.space-controls__left, .space-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.space-controls label { font-size: var(--text-sm); color: var(--text-secondary); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.space-percent {
  font-weight: var(--font-semibold);
  font-variant-numeric: tabular-nums;
}
</style>

<style>
/* 全局行颜色 */
.row-critical { background-color: var(--color-danger-50) !important; }
.row-warning { background-color: var(--color-warning-50) !important; }
</style>