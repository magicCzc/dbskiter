<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api, formatBytes } from '@/api'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { SpaceInfo } from '@/types'

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
  if (freeSpace < 10) return '#ef4444'
  if (freeSpace < 20) return '#f59e0b'
  return '#22c55e'
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
    <!-- 实时反馈 -->
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
    </div>

    <!-- 空间告警 -->
    <el-alert
      v-if="criticalTables.length > 0"
      :title="`发现 ${criticalTables.length} 个表空闲空间不足 10%，建议立即扩容或清理`"
      type="error"
      show-icon
      closable
      style="margin-bottom:16px"
    />
    <el-alert
      v-else-if="warningTables.length > 0"
      :title="`${warningTables.length} 个表空闲空间不足 20%，建议关注`"
      type="warning"
      show-icon
      closable
      style="margin-bottom:16px"
    />

    <!-- 控制栏 -->
    <el-card shadow="never" class="section-card">
      <div class="control-row">
        <div class="control-left">
          <label>数据库：</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <label>Top N：</label>
          <el-select v-model="top" size="small" style="width:100px" @change="load">
            <el-option v-for="n in [10, 20, 50, 100]" :key="n" :label="'Top ' + n" :value="n" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="control-right">
          <el-tag v-if="totalSize > 0" type="info" size="medium">总空间: {{ formatBytes(totalSize) }}</el-tag>
        </div>
      </div>
    </el-card>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-value" style="color:#6366f1">{{ formatBytes(totalSize) }}</div>
        <div class="kpi-label">总空间占用</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#f59e0b">{{ maxTable ? formatBytes(maxTable.total_size) : '-' }}</div>
        <div class="kpi-label">最大表</div>
        <div class="kpi-sub">{{ maxTable?.table_name || '' }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#3b82f6">{{ formatBytes(totalDataSize) }}</div>
        <div class="kpi-label">数据大小</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" style="color:#8b5cf6">{{ formatBytes(totalIndexSize) }}</div>
        <div class="kpi-label">索引大小</div>
      </div>
    </div>

    <!-- 空间表格 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>表空间详情</span>
          <el-button size="small" @click="load" :loading="loading">刷新</el-button>
        </div>
      </template>
      <el-table :data="tables" v-loading="loading" stripe style="width:100%" :empty-text="'暂无数据'"
        :row-class-name="rowClass">
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
            <span :style="{ color: spaceColor(row.free_space ?? 100), fontWeight: 600 }">
              {{ (row.free_space ?? 0).toFixed(1) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{row}">
            <el-button size="small" type="primary" plain @click="ElMessage.info('分析功能将在 Phase 3 实现')">
              分析
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.section-card { margin-bottom: 16px; }
.control-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.control-left, .control-right { display: flex; align-items: center; gap: 12px; }
.control-row label { font-size: 14px; color: var(--el-text-color-secondary); }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 16px; }
.kpi-card { background: var(--el-bg-color); border-radius: 8px; padding: 20px; border: 1px solid var(--el-border-color-light); text-align: center; }
.kpi-value { font-size: 28px; font-weight: 700; }
.kpi-label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }
.kpi-sub { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 4px; }

.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }
</style>

<style>
/* 全局行颜色 */
.row-critical { background-color: #fef2f2 !important; }
.row-warning { background-color: #fffbeb !important; }
</style>