<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api, exportCSV } from '@/api'
import { ElMessage } from 'element-plus'
import type { SqlExecuteResponse, SchemaResponse } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { get, set, remove, getString, setString } from '@/utils/storage'

const dbStore = useDatabaseStore()
const sql = ref('SELECT * FROM users LIMIT 10')
const results = ref<SqlExecuteResponse | null>(null)
const schema = ref<SchemaResponse | null>(null)
const history = ref<{ sql: string; timestamp: string; duration: number }[]>(
  get('sql-history', [])!
)
const loading = ref(false)
const loadingSchema = ref(false)
const readOnly = ref(true)
const limit = ref(100)
const activeTab = ref('results')
const error = ref('')
const executionTime = ref(0)
const lastUpdated = ref('')

const SQL_KEYWORDS = [
  'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'IS', 'NULL',
  'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE',
  'ALTER', 'DROP', 'INDEX', 'VIEW', 'TRIGGER', 'PROCEDURE', 'FUNCTION',
  'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS', 'ON',
  'GROUP', 'BY', 'ORDER', 'ASC', 'DESC', 'HAVING', 'LIMIT', 'OFFSET',
  'UNION', 'ALL', 'DISTINCT', 'AS', 'LIKE', 'BETWEEN', 'EXISTS',
  'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'CAST', 'CONVERT',
  'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'NULLIF',
  'WITH', 'RECURSIVE', 'EXPLAIN', 'ANALYZE', 'KILL',
  'SHOW', 'DESCRIBE', 'DESC', 'USE', 'GRANT', 'REVOKE',
  'COMMIT', 'ROLLBACK', 'BEGIN', 'START', 'TRANSACTION',
  'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES', 'CONSTRAINT',
  'UNIQUE', 'CHECK', 'DEFAULT', 'AUTO_INCREMENT', 'SERIAL',
  'INT', 'INTEGER', 'BIGINT', 'SMALLINT', 'TINYINT', 'VARCHAR',
  'CHAR', 'TEXT', 'BOOLEAN', 'FLOAT', 'DOUBLE', 'DECIMAL',
  'DATE', 'DATETIME', 'TIMESTAMP', 'TIME', 'YEAR', 'BLOB',
  'IF', 'THEN', 'ELSE', 'LOOP', 'WHILE', 'REPEAT',
  'TRUE', 'FALSE',
]

function highlightSQL(sqlText: string): string {
  if (!sqlText) return ''
  let escaped = sqlText
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

  escaped = escaped.replace(/(['"`].*?['"`])/g, '<span class="sql-string">$1</span>')
  escaped = escaped.replace(/(--[^\n]*)/g, '<span class="sql-comment">$1</span>')
  escaped = escaped.replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="sql-comment">$1</span>')
  escaped = escaped.replace(/\b(\d+\.?\d*)\b/g, '<span class="sql-number">$1</span>')

  for (const kw of SQL_KEYWORDS) {
    const regex = new RegExp(`\\b(${kw})\\b`, 'gi')
    escaped = escaped.replace(regex, '<span class="sql-keyword">$1</span>')
  }
  return escaped
}

const highlightedSQL = computed(() => highlightSQL(sql.value))

const columns = computed(() => {
  if (!results.value?.columns) return []
  return results.value.columns.map((col: string) => ({
    title: col,
    key: col,
    ellipsis: { tooltip: true },
    minWidth: 120,
  }))
})

const tableData = computed(() => {
  if (!results.value?.rows || !results.value?.columns) return []
  const cols = results.value.columns
  return results.value.rows.map((row: unknown[]) => {
    const obj: Record<string, unknown> = {}
    cols.forEach((col: string, i: number) => { obj[col] = row[i] })
    return obj
  })
})

const schemaTables = computed(() => {
  const raw = schema.value?.data?.raw_metrics || schema.value?.raw_data || schema.value
  if (Array.isArray(raw)) return raw
  if (raw?.tables) return raw.tables
  return []
})

async function execute() {
  if (!sql.value.trim()) {
    ElMessage.warning('请输入 SQL 语句')
    return
  }
  loading.value = true
  error.value = ''
  results.value = null
  const start = performance.now()
  try {
    const data = await api.executeSQL(dbStore.current, sql.value, limit.value, readOnly.value)
    executionTime.value = (performance.now() - start) / 1000
    lastUpdated.value = new Date().toLocaleTimeString()
    if (data.success) {
      results.value = data
      history.value.unshift({
        sql: sql.value,
        timestamp: new Date().toLocaleString(),
        duration: executionTime.value,
      })
      if (history.value.length > 50) history.value.pop()
      set('sql-history', history.value)
      ElMessage.success(`查询完成 (${executionTime.value.toFixed(3)}s)`)
    } else {
      error.value = data.error || '执行失败'
    }
  } catch (e: any) {
    error.value = e.message
    executionTime.value = (performance.now() - start) / 1000
  } finally {
    loading.value = false
  }
}

async function loadSchema() {
  loadingSchema.value = true
  try {
    schema.value = await api.getSchema(dbStore.current)
  } catch (e: any) {
    ElMessage.error(`Schema 加载失败: ${e.message}`)
  } finally {
    loadingSchema.value = false
  }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    execute()
  }
}

function copyAsJSON() {
  if (!tableData.value.length) return
  const json = JSON.stringify(tableData.value, null, 2)
  navigator.clipboard.writeText(json).then(() => {
    ElMessage.success('已复制 JSON 到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

function loadFromHistory(item: { sql: string }) {
  sql.value = item.sql
  activeTab.value = 'results'
  ElMessage.info('已加载历史 SQL')
}

function clearHistory() {
  history.value = []
  remove('sql-history')
  ElMessage.success('历史已清除')
}

onMounted(() => {
  dbStore.loadDatabases()
  const pending = getString('sql-editor-pending')
  if (pending) {
    sql.value = pending
    remove('sql-editor-pending')
  }
})
</script>

<template>
  <div class="page">
    <SectionCard padding>
      <div class="sql-toolbar">
        <div class="sql-toolbar__left">
          <label>数据库</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <el-tag
            :type="readOnly ? 'success' : 'danger'"
            size="small"
            effect="dark"
            class="sql-mode"
            @click="readOnly = !readOnly"
          >
            {{ readOnly ? '只读' : '可写' }}
          </el-tag>
          <label>行数</label>
          <el-input-number v-model="limit" :min="1" :max="10000" size="small" style="width:100px" />
          <el-button size="small" @click="loadSchema">Schema</el-button>
          <el-button type="primary" size="small" :loading="loading" @click="execute">运行 (Ctrl+Enter)</el-button>
        </div>
        <div class="sql-toolbar__right">
          <span v-if="lastUpdated" class="sql-updated">{{ lastUpdated }}</span>
        </div>
      </div>
    </SectionCard>

    <el-alert
      v-if="!readOnly"
      title="写入模式已开启！执行写操作将修改数据库数据，请谨慎操作"
      type="warning"
      show-icon
      closable
      class="sql-alert"
    />

    <SectionCard padding>
      <div class="code-editor">
        <pre class="code-display" aria-hidden="true"><code v-html="highlightedSQL"></code><br /></pre>
        <textarea
          v-model="sql"
          class="code-textarea"
          spellcheck="false"
          placeholder="输入 SQL 语句，Ctrl+Enter 执行..."
          @keydown="handleKeydown"
        ></textarea>
      </div>
    </SectionCard>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      class="sql-alert"
      closable
      @close="error = ''"
    />

    <SectionCard padding>
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="结果" name="results">
          <div v-if="loading" class="panel-loading">执行中...</div>
          <div v-else-if="!results" class="panel-empty">输入 SQL 并点击运行</div>
          <template v-else>
            <div class="result-info">
              <span>执行时间: <strong>{{ executionTime.toFixed(3) }}s</strong></span>
              <span>行数: <strong>{{ results.row_count || tableData.length }}</strong></span>
              <span>列数: <strong>{{ results.columns?.length || 0 }}</strong></span>
              <div class="result-actions">
                <el-button size="small" @click="exportCSV(tableData, 'query-result.csv')" :disabled="!tableData.length">导出 CSV</el-button>
                <el-button size="small" @click="copyAsJSON" :disabled="!tableData.length">复制 JSON</el-button>
              </div>
            </div>
            <el-table :data="tableData" stripe border style="width:100%" max-height="500" empty-text="查询无结果">
              <el-table-column v-for="col in columns" :key="col.key" :prop="col.key" :label="col.title" min-width="120" show-overflow-tooltip />
            </el-table>
          </template>
        </el-tab-pane>

        <el-tab-pane label="Schema" name="schema">
          <div v-if="loadingSchema" class="panel-loading">加载中...</div>
          <div v-else-if="!schema" class="panel-empty">
            <el-button @click="loadSchema" type="primary">加载 Schema</el-button>
          </div>
          <div v-else>
            <div v-for="tbl in schemaTables" :key="tbl.name || tbl.table_name" class="schema-item">
              <div class="schema-table-name">{{ tbl.name || tbl.table_name }}</div>
              <div class="schema-cols" v-if="tbl.columns">
                <div v-for="col in tbl.columns" :key="col.name || col.COLUMN_NAME" class="schema-col">
                  <code class="schema-col-name">{{ col.name || col.COLUMN_NAME }}</code>
                  <el-tag size="small" type="info">{{ col.type || col.DATA_TYPE }}</el-tag>
                  <span v-if="col.nullable === 'NO' || col.is_nullable === 'NO'" class="col-required">NOT NULL</span>
                  <span v-if="col.extra === 'auto_increment'" class="col-auto">AUTO_INC</span>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="最近查询" name="history">
          <div class="history-header">
            <span>{{ history.length }} 条记录</span>
            <el-button size="small" type="danger" plain @click="clearHistory" v-if="history.length > 0">清除历史</el-button>
          </div>
          <div v-if="!history.length" class="panel-empty">暂无查询历史</div>
          <div v-else class="history-list">
            <div v-for="(item, i) in history" :key="i" class="history-item" @click="loadFromHistory(item)">
              <code class="history-sql">{{ item.sql.substring(0, 100) }}{{ item.sql.length > 100 ? '...' : '' }}</code>
              <span class="history-meta">{{ item.timestamp }} · {{ item.duration.toFixed(3) }}s</span>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.sql-alert { margin-bottom: var(--space-3); }

.sql-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sql-toolbar__left, .sql-toolbar__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.sql-toolbar label { font-size: var(--text-sm); color: var(--text-secondary); white-space: nowrap; }
.sql-mode { cursor: pointer; }
.sql-updated { font-size: var(--text-xs); color: var(--text-tertiary); }

.code-editor {
  position: relative;
  min-height: 200px;
  max-height: 400px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.6;
  tab-size: 2;
  background: var(--bg-elevated);
  border-radius: var(--radius-md);
}

.code-display, .code-textarea {
  margin: 0;
  padding: var(--space-4);
  border: 0;
  width: 100%;
  min-height: 200px;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
  font-family: inherit;
  font-size: inherit;
  line-height: inherit;
  tab-size: inherit;
}

.code-display {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  color: var(--text-primary);
  background: transparent;
  overflow: visible;
}

.code-textarea {
  position: relative;
  display: block;
  color: transparent;
  caret-color: var(--text-primary);
  background: transparent;
  border: none;
  outline: none;
  resize: vertical;
  z-index: 1;
}

.code-textarea:focus {
  box-shadow: inset 0 0 0 1px var(--color-brand-500);
  border-radius: var(--radius-sm);
}
.code-textarea::placeholder { color: var(--text-placeholder); }

/* 语法高亮颜色 */
:deep(.sql-keyword) { color: var(--color-info-500); font-weight: var(--font-semibold); }
:deep(.sql-string) { color: var(--color-success-700); }
:deep(.sql-number) { color: var(--color-warning-500); }
:deep(.sql-comment) { color: var(--text-tertiary); font-style: italic; }

:global(.dark) :deep(.sql-keyword) { color: var(--color-brand-300); }
:global(.dark) :deep(.sql-string) { color: var(--color-success-500); }

.result-info {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-2) 0;
  margin-bottom: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  flex-wrap: wrap;
}
.result-info strong { color: var(--text-primary); font-weight: var(--font-semibold); }
.result-actions { margin-left: auto; display: flex; gap: var(--space-2); }

.panel-loading, .panel-empty {
  text-align: center;
  padding: var(--space-10);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}

.schema-item {
  margin-bottom: var(--space-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}
.schema-table-name {
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
  margin-bottom: var(--space-2);
  color: var(--text-primary);
}
.schema-cols { display: flex; flex-direction: column; gap: var(--space-1); }
.schema-col {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) 0;
  font-size: var(--text-sm);
}
.schema-col-name { font-size: var(--text-xs); font-family: var(--font-mono); }
.col-required { font-size: var(--text-xs); color: var(--color-danger-500); }
.col-auto { font-size: var(--text-xs); color: var(--color-info-500); }

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.history-list { display: flex; flex-direction: column; gap: var(--space-1); }
.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}
.history-item:hover {
  border-color: var(--color-brand-300);
  background: var(--color-brand-50);
}
.history-sql {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-meta {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  margin-left: var(--space-3);
  font-variant-numeric: tabular-nums;
}
</style>