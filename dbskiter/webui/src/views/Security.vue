<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api, severityClass } from '@/api'
import { ElMessage } from 'element-plus'
import type { Risk } from '@/types'

const dbStore = useDatabaseStore()
const risks = ref<Risk[]>([])
const loading = ref(false)
const filterLevel = ref('all')

const totalRisks = computed(() => risks.value.length)
const criticalCount = computed(() => risks.value.filter(r => r.severity === 'critical').length)
const highCount = computed(() => risks.value.filter(r => r.severity === 'high').length)
const score = computed(() => Math.max(0, 100 - criticalCount.value * 20 - highCount.value * 10 - risks.value.length * 2))

const filtered = computed(() => {
  if (filterLevel.value === 'all') return risks.value
  return risks.value.filter(r => r.severity === filterLevel.value)
})

const riskSummary = computed(() => ({
  critical: criticalCount.value,
  high: highCount.value,
  medium: risks.value.filter(r => r.severity === 'medium').length,
  low: risks.value.filter(r => r.severity === 'low').length,
}))

async function load() {
  loading.value = true
  try {
    const data = await api.security(dbStore.current)
    risks.value = data.risks
  } catch (e: any) { ElMessage.error(`加载失败: ${e.message}`) }
  finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <el-card shadow="never" class="section-card">
      <div class="section-header">
        <h2 style="margin:0;font-size:16px;display:flex;align-items:center;gap:8px">🔒 安全审计</h2>
        <div class="section-actions">
          <label>数据库：</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">执行审计</el-button>
        </div>
      </div>
    </el-card>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-value" :style="{color:score<60?'#ef4444':score<80?'#f59e0b':'#22c55e'}">{{ score }}</div>
        <div class="kpi-label">安全评分</div>
      </div>
      <div class="kpi-card"><div class="kpi-value" style="color:#6366f1">{{ totalRisks }}</div><div class="kpi-label">风险总数</div></div>
      <div class="kpi-card"><div class="kpi-value" style="color:#ef4444">{{ criticalCount }}</div><div class="kpi-label">严重风险</div></div>
      <div class="kpi-card"><div class="kpi-value" style="color:#f59e0b">{{ highCount }}</div><div class="kpi-label">高风险</div></div>
    </div>

    <el-card shadow="never" class="section-card">
      <template #header><span>📊 风险分布</span></template>
      <div class="dist-bar">
        <div v-if="criticalCount > 0" :style="{background:'#ef4444',flex:criticalCount}" class="dist-seg">{{ criticalCount }} 严重</div>
        <div v-if="highCount > 0" :style="{background:'#f59e0b',flex:highCount}" class="dist-seg">{{ highCount }} 高</div>
        <div v-if="riskSummary.medium > 0" :style="{background:'#3b82f6',flex:riskSummary.medium}" class="dist-seg">{{ riskSummary.medium }} 中</div>
        <div v-if="riskSummary.low > 0" :style="{background:'#22c55e',flex:riskSummary.low}" class="dist-seg">{{ riskSummary.low }} 低</div>
        <div v-if="totalRisks === 0" style="background:#e2e8f0;flex:1" class="dist-seg">✅ 未发现风险</div>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>风险列表</span>
          <el-select v-model="filterLevel" size="small" style="width:120px">
            <el-option label="全部" value="all" />
            <el-option label="严重" value="critical" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </div>
      </template>
      <el-table :data="filtered" v-loading="loading" stripe style="width:100%">
        <el-table-column label="级别" width="90">
          <template #default="{row}"><el-tag :type="(severityClass(row.severity) as any)" size="small">{{ row.severity }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column prop="current_value" label="当前值" width="180">
          <template #default="{row}"><code style="font-size:12px">{{ row.current_value }}</code></template>
        </el-table-column>
        <el-table-column prop="recommended_value" label="建议值" width="180">
          <template #default="{row}"><code style="font-size:12px;color:#22C55E">{{ row.recommended_value }}</code></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.page { max-width:1200px; margin:0 auto; }
.section-card { margin-bottom:16px; }
.section-header { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; }
.section-actions { display:flex; align-items:center; gap:12px; }
.section-actions label { font-size:14px; color:var(--el-text-color-secondary); }
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:16px; }
.kpi-card { background:var(--el-bg-color); border-radius:8px; padding:20px; border:1px solid var(--el-border-color-light); text-align:center; }
.kpi-value { font-size:28px; font-weight:700; }
.kpi-label { font-size:14px; color:var(--el-text-color-secondary); margin-top:4px; }
.dist-bar { display:flex; height:32px; border-radius:8px; overflow:hidden; }
.dist-seg { display:flex; align-items:center; justify-content:center; color:white; font-size:12px; font-weight:600; min-width:60px; }
</style>