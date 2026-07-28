<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDatabaseStore } from '@/stores/database'
import { api, exportCSV } from '@/api'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import type { SlowQuery } from '@/types'

const router = useRouter()
const dbStore = useDatabaseStore()
const queries = ref<SlowQuery[]>([])
const top = ref(10)
const hours = ref(6)
const loading = ref(false)
const searchText = ref('')
const explainVisible = ref(false)
const explainSql = ref('')
const explainResult = ref<{ success: boolean; columns?: string[]; rows?: unknown[][]; error?: string } | null>(null)

const explainedRows = computed<Record<string, unknown>[]>(() => {
  if (!explainResult.value?.rows || !explainResult.value.columns) return []
  const cols = explainResult.value.columns
  return explainResult.value.rows.map((r: unknown[]) => {
    const obj: Record<string, unknown> = {}
    cols.forEach((c: string, j: number) => { obj[c] = r[j] })
    return obj
  })
})
const explainLoading = ref(false)
const lastUpdated = ref('')

const filtered = computed(() => {
  if (!searchText.value) return queries.value
  return queries.value.filter(q => q.sql?.toLowerCase().includes(searchText.value.toLowerCase()))
})

const summary = computed(() => {
  const total = filtered.value.length
  const maxTime = total ? Math.max(...filtered.value.map(q => q.execution_time || 0)) : 0
  const avgTime = total ? filtered.value.reduce((s, q) => s + (q.execution_time || 0), 0) / total : 0
  const totalRows = filtered.value.reduce((s, q) => s + (q.rows_examined || 0), 0)
  return { total, maxTime, avgTime, totalRows }
})

async function load() {
  loading.value = true
  try {
    const data = await api.slowQueries(dbStore.current, top.value, hours.value)
    queries.value = data.queries
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) { ElMessage.error(`加载失败: ${e.message}`) }
  finally { loading.value = false }
}

function copySql(sql: string) {
  navigator.clipboard.writeText(sql).then(() => {
    ElMessage.success('SQL 已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

function openInEditor(sql: string) {
  localStorage.setItem('sql-editor-pending', sql)
  router.push('/sql-editor')
}

async function showExplain(sql: string) {
  explainSql.value = sql
  explainVisible.value = true
  explainResult.value = null
  explainLoading.value = true
  try {
    const data = await api.executeSQL(dbStore.current, `EXPLAIN ${sql}`, 50, true)
    if (data.success) {
      explainResult.value = {
        success: true,
        columns: data.columns || [],
        rows: (data.rows || []) as unknown[][],
      }
    } else {
      explainResult.value = { success: false, error: data.error || 'EXPLAIN 执行失败' }
    }
  } catch (e: any) {
    explainResult.value = { success: false, error: e.message }
  } finally {
    explainLoading.value = false
  }
}

function exportCSVData() {
  exportCSV(filtered.value.map(q => ({
    SQL: q.sql,
    总耗时_s: q.execution_time?.toFixed(2),
    执行次数: q.execution_count,
    平均耗时_s: q.avg_time?.toFixed(2),
    扫描行数: q.rows_examined,
  })), `slow-queries-${dbStore.current}.csv`)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <!-- 实时反馈 -->
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <label>数据库：</label>
        <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
          <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
        </el-select>
        <label>数量：</label>
        <el-select v-model="top" size="small" style="width:100px" @change="load">
          <el-option v-for="n in [5,10,20,50]" :key="n" :label="'Top '+n" :value="n" />
        </el-select>
        <label>时间：</label>
        <el-select v-model="hours" size="small" style="width:100px" @change="load">
          <el-option v-for="[v,l] of [[1,'1小时'],[6,'6小时'],[24,'24小时'],[72,'3天']]" :key="v" :value="v" :label="l" />
        </el-select>
        <el-button type="primary" size="small" :loading="loading" @click="load">查询</el-button>
        <el-input v-model="searchText" placeholder="搜索 SQL" size="small" style="width:200px" clearable :prefix-icon="Search" />
        <el-button size="small" @click="exportCSVData" :disabled="!filtered.length">导出 CSV</el-button>
      </div>
    </el-card>

    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-value">{{ summary.total }}</div><div class="kpi-label">慢查询总数</div></div>
      <div class="kpi-card"><div class="kpi-value">{{ summary.maxTime ? summary.maxTime.toFixed(2)+'s' : '-' }}</div><div class="kpi-label">最慢耗时</div></div>
      <div class="kpi-card"><div class="kpi-value">{{ summary.avgTime ? summary.avgTime.toFixed(2)+'s' : '-' }}</div><div class="kpi-label">平均耗时</div></div>
      <div class="kpi-card"><div class="kpi-value">{{ summary.totalRows.toLocaleString() }}</div><div class="kpi-label">总扫描行数</div></div>
    </div>

    <el-card shadow="never">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>慢查询列表</span>
          <el-button size="small" @click="load" :loading="loading">刷新</el-button>
        </div>
      </template>
      <el-table :data="filtered" v-loading="loading" stripe style="width:100%">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="sql" label="SQL" min-width="250" show-overflow-tooltip>
          <template #default="{row}"><code style="font-size:12px">{{ row.sql }}</code></template>
        </el-table-column>
        <el-table-column prop="execution_time" label="总耗时" width="90" sortable>
          <template #default="{row}"><span :style="{color:row.execution_time>5?'#ef4444':row.execution_time>2?'#f59e0b':'#22c55e',fontWeight:600}">{{ row.execution_time.toFixed(2) }}s</span></template>
        </el-table-column>
        <el-table-column prop="execution_count" label="次数" width="70" sortable />
        <el-table-column prop="avg_time" label="平均耗时" width="80">
          <template #default="{row}">{{ row.avg_time.toFixed(2) }}s</template>
        </el-table-column>
        <el-table-column prop="rows_examined" label="扫描行数" width="100" sortable>
          <template #default="{row}">{{ row.rows_examined.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{row}">
            <el-button-group>
              <el-button size="small" @click="showExplain(row.sql)">Explain</el-button>
              <el-button size="small" @click="copySql(row.sql)">复制</el-button>
              <el-button size="small" @click="openInEditor(row.sql)">编辑</el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Explain 对话框 -->
    <el-dialog v-model="explainVisible" title="EXPLAIN 分析" width="800px" :close-on-click-modal="false">
      <div v-if="explainLoading" style="text-align:center;padding:40px">加载中...</div>
      <div v-else-if="explainResult?.error" style="color:#ef4444;padding:20px">{{ explainResult.error }}</div>
      <template v-else>
        <div style="margin-bottom:12px">
          <code style="font-size:12px;background:var(--el-fill-color-light);padding:8px;border-radius:4px;display:block;word-break:break-all">{{ explainSql.substring(0, 500) }}</code>
        </div>
        <el-table :data="explainedRows" stripe border style="width:100%" max-height="400">
          <el-table-column v-for="col in (explainResult?.columns || [])" :key="col" :prop="col" :label="col" min-width="100" show-overflow-tooltip />
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page { max-width:1200px; margin:0 auto; }
.filter-card { margin-bottom:16px; }
.filter-row { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
.filter-row label { font-size:14px; color:var(--el-text-color-secondary); }
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:16px; }
.kpi-card { background:var(--el-bg-color); border-radius:8px; padding:20px; border:1px solid var(--el-border-color-light); text-align:center; }
.kpi-value { font-size:28px; font-weight:700; color:var(--el-color-primary); }
.kpi-label { font-size:14px; color:var(--el-text-color-secondary); margin-top:4px; }
.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }
</style>