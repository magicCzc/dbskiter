<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api, exportCSV } from '@/api'
import { ElMessage } from 'element-plus'
import type { SqlExecuteResponse, SchemaResponse } from '@/types'

const dbStore = useDatabaseStore()
const sql = ref('SELECT * FROM users LIMIT 10')
const results = ref<SqlExecuteResponse | null>(null)
const schema = ref<SchemaResponse | null>(null)
const history = ref<{ sql: string; timestamp: string; duration: number }[]>(
  JSON.parse(localStorage.getItem('sql-history') || '[]')
)
const loading = ref(false)
const loadingSchema = ref(false)
const readOnly = ref(true)
const limit = ref(100)
const activeTab = ref('results')
const error = ref('')
const executionTime = ref(0)
const lastUpdated = ref('')

// SQL 语法高亮
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
  // 转义 HTML 特殊字符
  let escaped = sqlText
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

  // 高亮字符串 ('...' 和 "...")
  escaped = escaped.replace(/(['"`].*?['"`])/g, '<span class="sql-string">$1</span>')

  // 高亮注释 (-- 和 /* */)
  escaped = escaped.replace(/(--[^\n]*)/g, '<span class="sql-comment">$1</span>')
  escaped = escaped.replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="sql-comment">$1</span>')

  // 高亮数字
  escaped = escaped.replace(/\b(\d+\.?\d*)\b/g, '<span class="sql-number">$1</span>')

  // 高亮关键字（不区分大小写）
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
    cols.forEach((col: string, i: number) => {
      obj[col] = row[i]
    })
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
      // 保存到历史
      history.value.unshift({
        sql: sql.value,
        timestamp: new Date().toLocaleString(),
        duration: executionTime.value,
      })
      if (history.value.length > 50) history.value.pop()
      localStorage.setItem('sql-history', JSON.stringify(history.value))
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
    const data = await api.getSchema(dbStore.current)
    schema.value = data
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
  localStorage.removeItem('sql-history')
  ElMessage.success('历史已清除')
}

onMounted(() => {
  dbStore.loadDatabases()
  // 检查是否有从其他页面传来的 SQL
  const pending = localStorage.getItem('sql-editor-pending')
  if (pending) {
    sql.value = pending
    localStorage.removeItem('sql-editor-pending')
  }
})
</script>

<template>
  <div class="page">
    <!-- 工具栏 -->
    <el-card shadow="never" class="section-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <label>数据库：</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <div class="readonly-toggle">
            <el-tag :type="readOnly ? 'success' : 'danger'" size="small" effect="dark" style="cursor:pointer" @click="readOnly = !readOnly">
              {{ readOnly ? '🔒 只读' : '🔓 可写' }}
            </el-tag>
          </div>
          <label>行数：</label>
          <el-input-number v-model="limit" :min="1" :max="10000" size="small" style="width:100px" />
          <el-button type="primary" size="small" :loading="loading" @click="execute">
            ▶ 运行 (Ctrl+Enter)
          </el-button>
          <el-button size="small" @click="loadSchema">
            Schema
          </el-button>
        </div>
        <div class="toolbar-right">
          <span class="live-text" v-if="lastUpdated">{{ lastUpdated }}</span>
        </div>
      </div>
    </el-card>

    <!-- 写入模式警告 -->
    <el-alert
      v-if="!readOnly"
      title="写入模式已开启！执行写操作将修改数据库数据，请谨慎操作"
      type="warning"
      show-icon
      closable
      style="margin-bottom:8px"
    />

    <!-- SQL 编辑器（语法高亮） -->
    <el-card shadow="never" class="section-card editor-card">
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
    </el-card>

    <!-- 错误提示 -->
    <el-alert v-if="error" :title="error" type="error" show-icon style="margin-bottom:8px" closable @close="error = ''" />

    <!-- 结果面板 -->
    <el-card shadow="never" class="section-card">
      <el-tabs v-model="activeTab" type="border-card">
        <!-- 结果 Tab -->
        <el-tab-pane label="📊 结果" name="results">
          <div v-if="loading" class="panel-loading">执行中...</div>
          <div v-else-if="!results" class="panel-empty">
            <div style="font-size:40px;margin-bottom:12px">⌨️</div>
            <div>输入 SQL 并点击运行</div>
          </div>
          <template v-else>
            <div class="result-info">
              <span>执行时间: <strong>{{ executionTime.toFixed(3) }}s</strong></span>
              <span>行数: <strong>{{ results.row_count || tableData.length }}</strong></span>
              <span>列数: <strong>{{ results.columns?.length || 0 }}</strong></span>
              <div class="result-actions">
                <el-button size="small" @click="exportCSV(tableData, 'query-result.csv')" :disabled="!tableData.length">
                  导出 CSV
                </el-button>
                <el-button size="small" @click="copyAsJSON" :disabled="!tableData.length">
                  复制 JSON
                </el-button>
              </div>
            </div>
            <el-table :data="tableData" stripe border style="width:100%" max-height="500" :empty-text="'查询无结果'">
              <el-table-column v-for="col in columns" :key="col.key" :prop="col.key" :label="col.title" min-width="120" show-overflow-tooltip />
            </el-table>
          </template>
        </el-tab-pane>

        <!-- Schema Tab -->
        <el-tab-pane label="📋 Schema" name="schema">
          <div v-if="loadingSchema" class="panel-loading">加载中...</div>
          <div v-else-if="!schema" class="panel-empty">
            <el-button @click="loadSchema" type="primary">加载 Schema</el-button>
          </div>
          <div v-else>
            <div v-for="tbl in schemaTables" :key="tbl.name || tbl.table_name" class="schema-item">
              <div class="schema-table-name">📄 {{ tbl.name || tbl.table_name }}</div>
              <div class="schema-cols" v-if="tbl.columns">
                <div v-for="col in tbl.columns" :key="col.name || col.COLUMN_NAME" class="schema-col">
                  <code>{{ col.name || col.COLUMN_NAME }}</code>
                  <el-tag size="small" type="info">{{ col.type || col.DATA_TYPE }}</el-tag>
                  <span v-if="col.nullable === 'NO' || col.is_nullable === 'NO'" class="col-required">NOT NULL</span>
                  <span v-if="col.extra === 'auto_increment'" class="col-auto">AUTO_INC</span>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 历史 Tab -->
        <el-tab-pane label="🕐 最近查询" name="history">
          <div class="history-header">
            <span>{{ history.length }} 条记录</span>
            <el-button size="small" type="danger" plain @click="clearHistory" v-if="history.length > 0">清除历史</el-button>
          </div>
          <div v-if="!history.length" class="panel-empty">
            <div style="font-size:40px;margin-bottom:12px">🕐</div>
            <div>暂无查询历史</div>
          </div>
          <div v-else>
            <div v-for="(item, i) in history" :key="i" class="history-item" @click="loadFromHistory(item)">
              <code class="history-sql">{{ item.sql.substring(0, 100) }}{{ item.sql.length > 100 ? '...' : '' }}</code>
              <span class="history-meta">{{ item.timestamp }} · {{ item.duration.toFixed(3) }}s</span>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.section-card { margin-bottom: 12px; }

.toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.toolbar label { font-size: 14px; color: var(--el-text-color-secondary); white-space: nowrap; }
.live-text { font-size: 12px; color: var(--el-text-color-placeholder); }

.editor-card { padding: 0; }

.code-editor {
  position: relative;
  min-height: 200px;
  max-height: 400px;
  overflow: auto;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 14px;
  line-height: 1.6;
  tab-size: 2;
  background: var(--el-bg-color);
}

.code-display, .code-textarea {
  margin: 0;
  padding: 16px;
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
  color: var(--el-text-color-primary);
  background: transparent;
  overflow: visible;
}

.code-textarea {
  position: relative;
  display: block;
  color: transparent;
  caret-color: var(--el-text-color-primary);
  background: transparent;
  border: none;
  outline: none;
  resize: vertical;
  z-index: 1;
}

.code-textarea:focus { box-shadow: inset 0 0 0 1px var(--el-color-primary); border-radius: 4px; }
.code-textarea::placeholder { color: var(--el-text-color-placeholder); }

/* 语法高亮颜色 */
:deep(.sql-keyword) { color: #3b82f6; font-weight: 600; }
:deep(.sql-string) { color: #22c55e; }
:deep(.sql-number) { color: #f59e0b; }
:deep(.sql-comment) { color: #94a3b8; font-style: italic; }

/* 暗色模式 */
:global(.dark) :deep(.sql-keyword) { color: #60a5fa; }
:global(.dark) :deep(.sql-string) { color: #4ade80; }
:global(.dark) :deep(.sql-number) { color: #fbbf24; }
:global(.dark) :deep(.sql-comment) { color: #64748b; }

.result-info {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  flex-wrap: wrap;
}
.result-actions { margin-left: auto; display: flex; gap: 8px; }

.panel-loading { text-align: center; padding: 40px; color: var(--el-text-color-placeholder); }
.panel-empty { text-align: center; padding: 40px; color: var(--el-text-color-placeholder); }

.schema-item { margin-bottom: 16px; border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 12px; }
.schema-table-name { font-weight: 600; font-size: 14px; margin-bottom: 8px; }
.schema-cols { display: flex; flex-direction: column; gap: 4px; }
.schema-col { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.schema-col code { font-size: 12px; }
.col-required { font-size: 11px; color: #ef4444; }
.col-auto { font-size: 11px; color: #3b82f6; }

.history-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 13px; color: var(--el-text-color-secondary); }
.history-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--el-border-color-light); border-radius: 6px; margin-bottom: 6px; cursor: pointer; transition: all 0.15s; }
.history-item:hover { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.history-sql { font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-meta { font-size: 11px; color: var(--el-text-color-placeholder); white-space: nowrap; margin-left: 12px; }
</style>