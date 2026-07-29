<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api, exportCSV } from '@/api'
import { ElMessage } from 'element-plus'
import type { Risk } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const dbStore = useDatabaseStore()
const risks = ref<Risk[]>([])
const loading = ref(false)
const filterLevel = ref('all')
const lastUpdated = ref('')
const fixDialogVisible = ref(false)
const fixSql = ref('')
const fixDescription = ref('')

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
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) { ElMessage.error(`加载失败: ${e.message}`) }
  finally { loading.value = false }
}

function showFix(risk: Risk) {
  fixDescription.value = risk.description || ''
  fixSql.value = risk.recommended_value || risk.current_value || '-- 无自动修复建议'
  fixDialogVisible.value = true
}

async function applyFix() {
  try {
    const data = await api.executeSQL(dbStore.current, fixSql.value, 1, false)
    if (data.success) {
      ElMessage.success('修复执行成功')
      fixDialogVisible.value = false
      await load()
    } else {
      ElMessage.error(`修复失败: ${data.error || '未知错误'}`)
    }
  } catch (e: any) {
    ElMessage.error(`执行错误: ${e.message}`)
  }
}

function exportCSVData() {
  exportCSV(filtered.value.map(r => ({
    级别: r.severity,
    描述: r.description,
    分类: r.category,
    当前值: r.current_value,
    建议值: r.recommended_value,
  })), `security-risks-${dbStore.current}.csv`)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <SectionCard padding>
      <div class="security-controls">
        <h2 class="security-title">安全审计</h2>
        <div class="security-controls__right">
          <label>数据库</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <el-button size="small" @click="exportCSVData" :disabled="!filtered.length">导出 CSV</el-button>
          <el-button type="primary" size="small" :loading="loading" @click="load">执行审计</el-button>
        </div>
      </div>
    </SectionCard>

    <div class="stat-grid">
      <div class="stat-item">
        <div class="stat-item__value" :style="{ color: score < 60 ? 'var(--color-danger-500)' : score < 80 ? 'var(--color-warning-500)' : 'var(--color-success-500)' }">{{ score }}</div>
        <div class="stat-item__label">安全评分</div>
      </div>
      <div class="stat-item">
        <div class="stat-item__value" style="color: var(--color-brand-500)">{{ totalRisks }}</div>
        <div class="stat-item__label">风险总数</div>
      </div>
      <div class="stat-item">
        <div class="stat-item__value" style="color: var(--color-danger-500)">{{ criticalCount }}</div>
        <div class="stat-item__label">严重风险</div>
      </div>
      <div class="stat-item">
        <div class="stat-item__value" style="color: var(--color-warning-500)">{{ highCount }}</div>
        <div class="stat-item__label">高风险</div>
      </div>
    </div>

    <SectionCard title="风险分布">
      <div class="dist-bar">
        <div v-if="criticalCount > 0" :style="{ background: 'var(--color-danger-500)', flex: criticalCount }" class="dist-seg">{{ criticalCount }} 严重</div>
        <div v-if="highCount > 0" :style="{ background: 'var(--color-warning-500)', flex: highCount }" class="dist-seg">{{ highCount }} 高</div>
        <div v-if="riskSummary.medium > 0" :style="{ background: 'var(--color-info-500)', flex: riskSummary.medium }" class="dist-seg">{{ riskSummary.medium }} 中</div>
        <div v-if="riskSummary.low > 0" :style="{ background: 'var(--color-success-500)', flex: riskSummary.low }" class="dist-seg">{{ riskSummary.low }} 低</div>
        <div v-if="totalRisks === 0" class="dist-seg dist-seg--empty">未发现风险</div>
      </div>
    </SectionCard>

    <SectionCard title="风险列表">
      <template #actions>
        <el-select v-model="filterLevel" size="small" style="width:120px">
          <el-option label="全部" value="all" />
          <el-option label="严重" value="critical" />
          <el-option label="高" value="high" />
          <el-option label="中" value="medium" />
          <el-option label="低" value="low" />
        </el-select>
      </template>
      <el-table :data="filtered" v-loading="loading" stripe style="width:100%">
        <el-table-column label="级别" width="80">
          <template #default="{row}"><StatusTag :status="row.severity" /></template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="current_value" label="当前值" width="150" show-overflow-tooltip>
          <template #default="{row}"><code class="security-code">{{ row.current_value }}</code></template>
        </el-table-column>
        <el-table-column prop="recommended_value" label="建议值" width="150" show-overflow-tooltip>
          <template #default="{row}"><code class="security-code security-code--ok">{{ row.recommended_value }}</code></template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{row}">
            <el-button size="small" type="primary" plain @click="showFix(row)" v-if="row.recommended_value">修复</el-button>
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>

    <el-dialog v-model="fixDialogVisible" title="修复建议" width="600px">
      <p class="fix-desc">{{ fixDescription }}</p>
      <div class="fix-code-wrap">
        <code class="fix-code">{{ fixSql }}</code>
      </div>
      <p class="fix-warn">注意：执行修复将修改数据库配置，请确认操作</p>
      <div class="fix-actions">
        <el-button @click="fixDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="applyFix">执行修复</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }

.security-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.security-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.security-controls label { font-size: var(--text-sm); color: var(--text-secondary); }
.security-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.stat-item {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  text-align: center;
}
.stat-item__value {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  margin-bottom: var(--space-1);
}
.stat-item__label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.dist-bar {
  display: flex;
  height: 32px;
  border-radius: var(--radius-md);
  overflow: hidden;
}
.dist-seg {
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  min-width: 60px;
  padding: 0 var(--space-2);
}
.dist-seg--empty {
  background: var(--color-gray-100);
  color: var(--text-tertiary);
  flex: 1;
}

.security-code {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
}
.security-code--ok { color: var(--color-success-700); }

.fix-desc {
  margin: 0 0 var(--space-3);
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.fix-code-wrap {
  background: var(--bg-code);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}
.fix-code {
  font-size: var(--text-sm);
  font-family: var(--font-mono);
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary);
}
.fix-warn {
  font-size: var(--text-xs);
  color: var(--color-danger-700);
  margin-bottom: var(--space-4);
}
.fix-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>