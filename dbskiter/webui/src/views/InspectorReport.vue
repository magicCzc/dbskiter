<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { InspectorResponse } from '@/types'

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

const sections = computed(() => {
  if (!reportData.value) return []
  const raw = reportData.value.data?.raw_metrics || reportData.value.raw_data || reportData.value
  const items = raw.items || []
  const stats = raw.statistics || {}

  // 按 type 分组
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

  interface Section {
    name: string
    score: number
    issues: any[]
  }
  const result: Section[] = []
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
    <!-- 实时反馈 -->
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
    </div>

    <!-- 控制栏 -->
    <el-card shadow="never" class="section-card">
      <div class="control-row">
        <div class="control-left">
          <h2 style="margin:0;font-size:16px;display:flex;align-items:center;gap:8px">📋 巡检报告</h2>
        </div>
        <div class="control-right">
          <label>数据库：</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <label>类型：</label>
          <el-select v-model="reportType" size="small" style="width:120px">
            <el-option v-for="r in reportTypes" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="generate">
            🚀 生成报告
          </el-button>
        </div>
      </div>
    </el-card>

    <el-alert v-if="error" :title="error" type="error" show-icon style="margin-bottom:16px" closable />

    <!-- 空状态 -->
    <el-card v-if="!reportData && !loading" shadow="never" style="text-align:center;padding:60px;margin-bottom:16px">
      <div style="font-size:48px;margin-bottom:16px">📋</div>
      <p style="color:var(--el-text-color-secondary)">选择数据库和报告类型，点击"生成报告"</p>
    </el-card>

    <!-- 报告结果 -->
    <template v-if="reportData">
      <!-- 总分 -->
      <el-card shadow="never" class="section-card">
        <div class="score-banner">
          <div class="score-circle" :style="{
            borderColor: overallScore >= 80 ? '#22c55e' : overallScore >= 60 ? '#f59e0b' : '#ef4444',
            color: overallScore >= 80 ? '#22c55e' : overallScore >= 60 ? '#f59e0b' : '#ef4444',
          }">{{ overallScore.toFixed(0) }}</div>
          <div class="score-info">
            <div class="score-title">巡检总分</div>
            <div class="score-desc">{{ overallScore >= 80 ? '✅ 数据库状态良好' : overallScore >= 60 ? '⚠️ 需要关注部分问题' : '🔴 存在严重问题，建议立即处理' }}</div>
          </div>
        </div>
      </el-card>

      <!-- 分区详情 -->
      <div v-for="section in sections" :key="section.name" class="section-card">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>{{ section.name }}</span>
              <el-tag :type="section.score >= 80 ? 'success' : section.score >= 60 ? 'warning' : 'danger'" size="medium">
                {{ section.score.toFixed(0) }} 分
              </el-tag>
            </div>
          </template>
          <div v-if="section.issues.length > 0">
            <div v-for="(issue, i) in section.issues.slice(0, 10)" :key="i" class="issue-item">
              <span class="issue-icon">{{ issue.severity === 'critical' ? '🔴' : issue.severity === 'high' ? '🟡' : '🟢' }}</span>
              <span class="issue-text">{{ issue.message || issue.description || issue }}</span>
            </div>
          </div>
          <div v-else style="padding: 12px 0; color: var(--el-text-color-secondary);">
            ✅ 未发现问题
          </div>
        </el-card>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }
.section-card { margin-bottom: 16px; }
.control-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.control-left, .control-right { display: flex; align-items: center; gap: 12px; }
.control-row label { font-size: 14px; color: var(--el-text-color-secondary); }
.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }

.score-banner { display: flex; align-items: center; gap: 24px; padding: 8px 0; }
.score-circle { width: 80px; height: 80px; border-radius: 50%; border: 4px solid; display: flex; align-items: center; justify-content: center; font-size: 32px; font-weight: 700; flex-shrink: 0; }
.score-title { font-size: 18px; font-weight: 600; }
.score-desc { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }

.issue-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.issue-item:last-child { border-bottom: none; }
.issue-icon { font-size: 14px; }
.issue-text { font-size: 13px; }
</style>