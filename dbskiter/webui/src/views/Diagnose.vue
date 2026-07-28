<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { DiagnoseResult, DiagnoseIssue } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const router = useRouter()
const dbStore = useDatabaseStore()
const loading = ref(false)
const error = ref('')
const result = ref<DiagnoseResult | null>(null)
const lastUpdated = ref('')
const cmdLoading = ref<string>('')
const cmdResults = ref<Record<string, any>>({})

const summaryCards = computed(() => {
  if (!result.value) return []
  const d = result.value
  return [
    { label: '健康评分', value: d.score ?? '-', color: d.score > 80 ? 'var(--color-success-500)' : d.score > 60 ? 'var(--color-warning-500)' : 'var(--color-danger-500)', path: '' },
    { label: '问题数', value: d.issues?.length ?? 0, color: 'var(--color-brand-500)', path: '' },
    { label: '慢查询', value: d.raw_data?.slow_queries?.length ?? 0, color: 'var(--color-warning-500)', path: '/slow-queries' },
    { label: '锁等待', value: d.raw_data?.locks?.length ?? d.raw_data?.lock_waits ?? 0, color: 'var(--color-danger-500)', path: '/locks' },
  ]
})

async function run() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const data = await api.diagnose(dbStore.current)
    result.value = data
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    error.value = e.message
    ElMessage.error(`诊断失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

function navigateTo(path: string) {
  if (path) router.push(path)
}

function detailPath(issue: DiagnoseIssue): string {
  const msg = (issue.message || issue.description || '').toLowerCase()
  if (msg.includes('慢查询') || msg.includes('slow')) return '/slow-queries'
  if (msg.includes('锁') || msg.includes('lock') || msg.includes('deadlock')) return '/locks'
  if (msg.includes('空间') || msg.includes('space') || msg.includes('磁盘') || msg.includes('disk')) return '/space'
  if (msg.includes('连接') || msg.includes('connection')) return '/connections'
  if (msg.includes('安全') || msg.includes('security') || msg.includes('风险')) return '/security'
  return ''
}

function commandLabel(cmd: string): string {
  const parts = cmd.split(' ')
  const dbIdx = parts.findIndex(p => p.startsWith('--database='))
  const cmdStart = dbIdx >= 0 ? dbIdx + 1 : 2
  return parts.slice(cmdStart).join(' ') || cmd
}

async function executeCommand(cmd: string) {
  cmdLoading.value = cmd
  try {
    const parts = cmd.split(' ')
    const cmdParts = parts.filter(p => !p.startsWith('--') && p !== 'dbskiter')
    if (cmdParts.length < 2) {
      ElMessage.warning('无法解析命令')
      return
    }
    const subCmd = cmdParts.slice(1).join(' ')
    const url = `/api/diagnose/${subCmd.split(' ')[0]}?database=${encodeURIComponent(dbStore.current)}`
    const resp = await fetch(url)
    const data = await resp.json()
    cmdResults.value = { ...cmdResults.value, [cmd]: data }
  } catch (e: any) {
    cmdResults.value = { ...cmdResults.value, [cmd]: { error: e.message } }
  } finally {
    cmdLoading.value = ''
  }
}

onMounted(() => { dbStore.loadDatabases() })
</script>

<template>
  <div class="page">
    <SectionCard padding>
      <div class="diagnose-controls">
        <div class="diagnose-controls__left">
          <h2 class="diagnose-title">实时诊断</h2>
        </div>
        <div class="diagnose-controls__right">
          <label>数据库</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="run">
            开始诊断
          </el-button>
        </div>
      </div>
    </SectionCard>

    <el-alert v-if="error" :title="error" type="error" show-icon class="diagnose-error" closable />

    <!-- KPI 卡片 -->
    <div v-if="result" class="stat-grid">
      <div
        v-for="c in summaryCards"
        :key="c.label"
        class="summary-card"
        :class="{ 'summary-card--clickable': c.path }"
        @click="navigateTo(c.path)"
      >
        <div class="summary-value" :style="{ color: c.color }">{{ c.value }}</div>
        <div class="summary-label">{{ c.label }}</div>
        <div v-if="c.path" class="summary-link">查看详情</div>
      </div>
    </div>

    <!-- 诊断结果 -->
    <SectionCard v-if="result" title="诊断结果">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="数据库">{{ result.database }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag :status="result.status" />
        </el-descriptions-item>
      </el-descriptions>

      <!-- 问题列表 -->
      <div v-if="result.issues?.length" class="diagnose-section">
        <h4 class="diagnose-section-title">发现的问题</h4>
        <el-table :data="result.issues" stripe size="small">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="message" label="描述" min-width="200" />
          <el-table-column prop="severity" label="级别" width="80">
            <template #default="{row}">
              <StatusTag :status="row.severity" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{row}">
              <el-button
                v-if="detailPath(row)"
                size="small"
                type="primary"
                plain
                @click="navigateTo(detailPath(row))"
              >查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- AI 建议 -->
      <div v-if="result.ai_hints?.focus_areas?.length" class="diagnose-section">
        <h4 class="diagnose-section-title">AI 建议关注</h4>
        <div class="diagnose-tags">
          <el-tag v-for="area in result.ai_hints.focus_areas" :key="area" type="warning" style="cursor:pointer" @click="navigateTo('/slow-queries')">{{ area }}</el-tag>
        </div>
      </div>

      <!-- 建议命令 -->
      <div v-if="result.ai_hints?.related_commands?.length" class="diagnose-section">
        <h4 class="diagnose-section-title">建议执行</h4>
        <div class="diagnose-tags">
          <el-button
            v-for="cmd in result.ai_hints.related_commands"
            :key="cmd"
            size="small"
            :type="cmdLoading === cmd ? 'warning' : 'primary'"
            :loading="cmdLoading === cmd"
            @click="executeCommand(cmd)"
          >
            {{ commandLabel(cmd) }}
          </el-button>
        </div>
        <div v-for="(res, cmd) in cmdResults" :key="cmd" style="margin-top:12px">
          <el-collapse>
            <el-collapse-item :title="commandLabel(cmd) + ' 结果'" name="cmd">
              <pre class="diagnose-code">{{ JSON.stringify(res, null, 2) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <!-- 原始数据 -->
      <details style="margin-top:16px">
        <summary class="diagnose-raw-toggle">查看原始数据</summary>
        <pre class="diagnose-code">{{ JSON.stringify(result.raw_data, null, 2) }}</pre>
      </details>
    </SectionCard>

    <!-- 空状态 -->
    <SectionCard v-if="!result && !loading" padding>
      <div class="diagnose-empty">
        <p>选择数据库并点击"开始诊断"</p>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }

.diagnose-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.diagnose-controls__left, .diagnose-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.diagnose-controls label { font-size: var(--text-sm); color: var(--text-secondary); }
.diagnose-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}
.diagnose-error { margin-bottom: var(--space-4); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.summary-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  text-align: center;
}
.summary-card--clickable {
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.summary-card--clickable:hover {
  border-color: var(--color-brand-200);
  box-shadow: var(--shadow-sm);
}
.summary-value {
  font-size: var(--text-3xl);
  font-weight: var(--font-semibold);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  margin-bottom: var(--space-1);
}
.summary-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}
.summary-link {
  font-size: var(--text-xs);
  color: var(--text-link);
  margin-top: var(--space-1);
}

.diagnose-section {
  margin-top: var(--space-4);
}
.diagnose-section-title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}
.diagnose-tags {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.diagnose-code {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  max-height: 300px;
  overflow: auto;
  background: var(--bg-code);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  margin-top: var(--space-2);
}
.diagnose-raw-toggle {
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}
.diagnose-empty {
  text-align: center;
  padding: var(--space-10);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}
</style>