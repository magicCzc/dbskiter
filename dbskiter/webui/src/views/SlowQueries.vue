<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDatabaseStore } from '@/stores/database'
import { api, exportCSV } from '@/api'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import type { SlowQuery } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatCard from '@/components/StatCard.vue'

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
const explainLoading = ref(false)
const lastUpdated = ref('')

const explainedRows = computed<Record<string, unknown>[]>(() => {
  if (!explainResult.value?.rows || !explainResult.value.columns) return []
  const cols = explainResult.value.columns
  return explainResult.value.rows.map((r: unknown[]) => {
    const obj: Record<string, unknown> = {}
    cols.forEach((c: string, j: number) => { obj[c] = r[j] })
    return obj
  })
})

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
    <SectionCard padding>
      <div class="filter-row">
        <label>数据库</label>
        <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
          <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
        </el-select>
        <label>Top</label>
        <el-select v-model="top" size="small" style="width:100px" @change="load">
          <el-option v-for="n in [5,10,20,50]" :key="n" :label="`Top ${n}`" :value="n" />
        </el-select>
        <label>时间</label>
        <el-select v-model="hours" size="small" style="width:110px" @change="load">
          <el-option v-for="[v,l] of [[1,'1小时'],[6,'6小时'],[24,'24小时'],[72,'3天']]" :key="v" :value="v" :label="l" />
        </el-select>
        <el-input v-model="searchText" placeholder="搜索 SQL" size="small" style="width:200px" clearable :prefix-icon="Search" />
        <el-button size="small" @click="exportCSVData" :disabled="!filtered.length">导出 CSV</el-button>
        <el-button type="primary" size="small" :loading="loading" @click="load">查询</el-button>
      </div>
    </SectionCard>

    <div class="stat-grid">
      <StatCard :value="summary.total" label="慢查询总数" size="sm" />
      <StatCard :value="summary.maxTime ? summary.maxTime.toFixed(2) + 's' : '-'" label="最慢耗时" size="sm" />
      <StatCard :value="summary.avgTime ? summary.avgTime.toFixed(2) + 's' : '-'" label="平均耗时" size="sm" />
      <StatCard :value="summary.totalRows.toLocaleString()" label="总扫描行数" size="sm" />
    </div>

    <SectionCard title="慢查询列表">
      <template #actions>
        <el-button size="small" @click="load" :loading="loading">刷新</el-button>
      </template>
      <el-table :data="filtered" v-loading="loading" stripe style="width:100%">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="sql" label="SQL" min-width="250" show-overflow-tooltip>
          <template #default="{row}"><code class="slow-sql">{{ row.sql }}</code></template>
        </el-table-column>
        <el-table-column prop="execution_time" label="总耗时" width="90" sortable>
          <template #default="{row}">
            <span class="slow-time" :class="`slow-time--${row.execution_time > 5 ? 'critical' : row.execution_time > 2 ? 'warning' : 'ok'}`">
              {{ row.execution_time.toFixed(2) }}s
            </span>
          </template>
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
    </SectionCard>

    <el-dialog v-model="explainVisible" title="EXPLAIN 分析" width="800px" :close-on-click-modal="false">
      <div v-if="explainLoading" class="explain-loading">加载中...</div>
      <div v-else-if="explainResult?.error" class="explain-error">{{ explainResult.error }}</div>
      <template v-else>
        <div class="explain-sql-wrap">
          <code class="explain-sql">{{ explainSql.substring(0, 500) }}</code>
        </div>
        <el-table :data="explainedRows" stripe border style="width:100%" max-height="400">
          <el-table-column v-for="col in (explainResult?.columns || [])" :key="col" :prop="col" :label="col" min-width="100" show-overflow-tooltip />
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }

.filter-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.filter-row label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.slow-sql { font-size: var(--text-xs); font-family: var(--font-mono); }
.slow-time { font-weight: var(--font-semibold); }
.slow-time--critical { color: var(--color-danger-500); }
.slow-time--warning { color: var(--color-warning-500); }
.slow-time--ok { color: var(--color-success-500); }

.explain-loading { text-align: center; padding: var(--space-10); color: var(--text-tertiary); }
.explain-error { color: var(--color-danger-700); padding: var(--space-5); }
.explain-sql-wrap { margin-bottom: var(--space-3); }
.explain-sql {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  background: var(--bg-code);
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  display: block;
  word-break: break-all;
}
</style>