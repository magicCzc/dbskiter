<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'

const dbStore = useDatabaseStore()
const loading = ref(false)
const error = ref('')
const result = ref<any>(null)

const summaryCards = computed(() => {
  if (!result.value) return []
  const d = result.value
  return [
    { label: '健康评分', value: d.score ?? '-', color: d.score > 80 ? '#22c55e' : d.score > 60 ? '#f59e0b' : '#ef4444' },
    { label: '问题数', value: d.issues?.length ?? 0, color: '#6366f1' },
    { label: '慢查询', value: d.raw_data?.slow_queries?.length ?? 0, color: '#f59e0b' },
    { label: '锁等待', value: d.raw_data?.locks?.length ?? d.raw_data?.lock_waits ?? 0, color: '#ef4444' },
  ]
})

async function run() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const data = await api.diagnose(dbStore.current)
    result.value = data
  } catch (e: any) {
    error.value = e.message
    ElMessage.error(`诊断失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => { dbStore.loadDatabases() })
</script>

<template>
  <div class="page">
    <el-card shadow="never" class="section-card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
        <h2 style="margin:0;font-size:16px">🔍 实时诊断</h2>
        <div style="display:flex;align-items:center;gap:12px">
          <label>数据库：</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="run">
            🔍 开始诊断
          </el-button>
        </div>
      </div>
    </el-card>

    <el-alert v-if="error" :title="error" type="error" show-icon style="margin-bottom:16px" closable />

    <!-- 摘要卡片 -->
    <div v-if="result" class="kpi-grid">
      <div v-for="c in summaryCards" :key="c.label" class="kpi-card">
        <div class="kpi-value" :style="{color: c.color}">{{ c.value }}</div>
        <div class="kpi-label">{{ c.label }}</div>
      </div>
    </div>

    <!-- 诊断结果 -->
    <el-card v-if="result" shadow="never" class="section-card">
      <template #header><span>📋 诊断结果</span></template>

      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="数据库">{{ result.database }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="result.status === 'HEALTHY' ? 'success' : 'warning'" size="small">{{ result.status }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 问题列表 -->
      <div v-if="result.issues?.length" style="margin-top:16px">
        <h4 style="margin-bottom:8px;font-size:14px">⚠️ 发现的问题</h4>
        <el-table :data="result.issues" stripe size="small">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="message" label="描述" />
          <el-table-column prop="severity" label="级别" width="100">
            <template #default="{row}"><el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'" size="small">{{ row.severity }}</el-tag></template>
          </el-table-column>
        </el-table>
      </div>

      <!-- AI 提示 -->
      <div v-if="result.ai_hints?.focus_areas?.length" style="margin-top:16px">
        <h4 style="margin-bottom:8px;font-size:14px">💡 AI 建议关注</h4>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <el-tag v-for="area in result.ai_hints.focus_areas" :key="area" type="warning">{{ area }}</el-tag>
        </div>
      </div>

      <!-- 原始数据（可折叠） -->
      <details style="margin-top:16px">
        <summary style="cursor:pointer;font-size:13px;color:var(--el-text-color-secondary)">📄 查看原始数据</summary>
        <pre style="font-size:12px;max-height:400px;overflow:auto;background:var(--el-fill-color-light);padding:12px;border-radius:6px;margin-top:8px">{{ JSON.stringify(result.raw_data, null, 2) }}</pre>
      </details>
    </el-card>

    <!-- 空状态 -->
    <el-card v-if="!result && !loading" shadow="never" style="text-align:center;padding:60px">
      <div style="font-size:48px;margin-bottom:16px">🔍</div>
      <p style="color:var(--el-text-color-secondary)">选择数据库并点击"开始诊断"</p>
    </el-card>
  </div>
</template>

<style scoped>
.page { max-width:1200px; margin:0 auto; }
.section-card { margin-bottom:16px; }
.section-card label { font-size:14px; color:var(--el-text-color-secondary); }
</style>