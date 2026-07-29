<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { InspectorResponse } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const dbStore = useDatabaseStore()
const loading = ref(false)
const reportType = ref('full')
const reportData = ref<InspectorResponse | null>(null)
const error = ref('')
const lastUpdated = ref('')

const reportTypes = [
  { value: 'configuration', label: '配置检查' },
  { value: 'performance', label: '性能分析' },
  { value: 'storage', label: '存储分析' },
  { value: 'security', label: '安全检查' },
  { value: 'capacity', label: '容量分析' },
  { value: 'replication', label: '复制检查' },
]

const overallScore = computed(() => {
  if (!reportData.value) return 0
  return reportData.value.data?.raw_metrics?.health_score ?? reportData.value.data?.score ?? reportData.value.score ?? 0
})

const scoreColor = computed(() => {
  if (overallScore.value >= 80) return 'var(--color-success-500)'
  if (overallScore.value >= 60) return 'var(--color-warning-500)'
  return 'var(--color-danger-500)'
})

const scoreText = computed(() => {
  if (overallScore.value >= 80) return '数据库状态良好'
  if (overallScore.value >= 60) return '需要关注部分问题'
  return '存在严重问题，建议立即处理'
})

const sections = computed(() => {
  if (!reportData.value) return []
  const raw = reportData.value.data?.raw_metrics || reportData.value.raw_data || reportData.value
  const items = raw.items || []

  const groups: Record<string, any[]> = {}
  for (const item of items) {
    const t = (item as any).type || '综合'
    if (!groups[t]) groups[t] = []
    groups[t].push(item)
  }

  const typeLabels: Record<string, string> = {
    configuration: '配置检查', performance: '性能分析',
    storage: '存储分析', security: '安全检查',
    capacity: '容量分析', replication: '复制检查',
  }

  const result: { name: string; score: number; issues: any[] }[] = []
  for (const [type, typeItems] of Object.entries(groups)) {
    const issues = typeItems.filter((i) => {
      const item = i as { status?: string; risk_level?: string }
      return item.status === 'warning' || item.status === 'fail' || (item.risk_level && item.risk_level !== 'info')
    })
    const passCount = typeItems.filter((i) => (i as { status?: string }).status === 'pass').length
    const score = typeItems.length > 0 ? Math.round((passCount / typeItems.length) * 100) : 0
    result.push({
      name: typeLabels[type] || type,
      score,
      issues: issues.slice(0, 10),
    })
  }

  if (!result.length) {
    result.push({ name: '综合', score: overallScore.value, issues: raw.issues || [] })
  }
  return result
})

async function generate() {
  loading.value = true
  error.value = ''
  reportData.value = null
  try {
    const data = await api.inspectorReport(dbStore.current, reportType.value)
    reportData.value = data
    lastUpdated.value = new Date().toLocaleTimeString()
    ElMessage.success('巡检报告生成完成')
  } catch (e: any) {
    error.value = e.message
    ElMessage.error(`生成失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => { dbStore.loadDatabases() })
</script>

<template>
  <div class="page">
    <SectionCard padding>
      <div class="inspector-controls">
        <h2 class="inspector-title">巡检报告</h2>
        <div class="inspector-controls__right">
          <label>数据库</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <label>类型</label>
          <el-select v-model="reportType" size="small" style="width:120px">
            <el-option v-for="r in reportTypes" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="generate">生成报告</el-button>
        </div>
      </div>
    </SectionCard>

    <el-alert v-if="error" :title="error" type="error" show-icon class="inspector-alert" closable />

    <SectionCard v-if="!reportData && !loading" padding>
      <div class="inspector-empty">选择数据库和报告类型，点击"生成报告"</div>
    </SectionCard>

    <template v-if="reportData">
      <SectionCard title="巡检总分">
        <div class="score-banner">
          <div class="score-circle" :style="{ borderColor: scoreColor, color: scoreColor }">{{ overallScore.toFixed(0) }}</div>
          <div class="score-info">
            <div class="score-title">总分</div>
            <div class="score-desc">{{ scoreText }}</div>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        v-for="section in sections"
        :key="section.name"
        :title="section.name"
      >
        <template #actions>
          <el-tag :type="section.score >= 80 ? 'success' : section.score >= 60 ? 'warning' : 'danger'">
            {{ section.score.toFixed(0) }} 分
          </el-tag>
        </template>
        <div v-if="section.issues.length > 0" class="issue-list">
          <div v-for="(issue, i) in section.issues.slice(0, 10)" :key="i" class="issue-item">
            <span class="issue-dot" :class="`issue-dot--${issue.severity || 'info'}`"></span>
            <span class="issue-text">{{ issue.message || issue.description || issue }}</span>
          </div>
        </div>
        <div v-else class="issue-empty">未发现问题</div>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }
.inspector-alert { margin-bottom: var(--space-4); }

.inspector-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.inspector-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.inspector-controls label { font-size: var(--text-sm); color: var(--text-secondary); }
.inspector-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.inspector-empty {
  text-align: center;
  padding: var(--space-12);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}

.score-banner {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-2) 0;
}
.score-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 4px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.score-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}
.score-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}

.issue-list {
  display: flex;
  flex-direction: column;
}
.issue-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-muted);
  font-size: var(--text-sm);
}
.issue-item:last-child { border-bottom: none; }
.issue-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.issue-dot--critical, .issue-dot--high { background: var(--color-danger-500); }
.issue-dot--warning, .issue-dot--medium { background: var(--color-warning-500); }
.issue-dot--info, .issue-dot--low, .issue-dot--success { background: var(--color-success-500); }
.issue-text { color: var(--text-primary); }

.issue-empty {
  padding: var(--space-3) 0;
  color: var(--text-tertiary);
  font-size: var(--text-sm);
  text-align: center;
}
</style>