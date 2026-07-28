<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { AlertItem, AlertStatsResponse } from '@/types'
import StatCard from '@/components/StatCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const dbStore = useDatabaseStore()
const alerts = ref<AlertItem[]>([])
const loading = ref(false)
const filterLevel = ref('all')
const filterStatus = ref('open')
const lastUpdated = ref('')
const stats = ref<AlertStatsResponse['stats']>({ total: 0, open: 0, critical: 0, warning: 0 })

const filtered = computed(() => {
  let list = alerts.value
  if (filterLevel.value !== 'all') {
    list = list.filter(a => a.level === filterLevel.value)
  }
  return list
})

async function load() {
  loading.value = true
  try {
    const [data, statsData] = await Promise.all([
      api.listAlerts({ status: filterStatus.value === 'all' ? 'all' : filterStatus.value, limit: 100 }),
      api.getAlertStats(),
    ])
    alerts.value = data.alerts || []
    stats.value = statsData.stats || { total: 0, open: 0, critical: 0, warning: 0 }
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

async function acknowledge(id: number) {
  try {
    await api.acknowledgeAlert(id)
    ElMessage.success('告警已确认')
    await load()
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

async function resolve(id: number) {
  try {
    await api.resolveAlert(id)
    ElMessage.success('告警已解决')
    await load()
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

async function resolveAll() {
  try {
    const data = await api.resolveAllAlerts()
    ElMessage.success(`已解决 ${data.resolved_count} 个告警`)
    await load()
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

onMounted(() => { dbStore.loadDatabases(); load() })
</script>

<template>
  <div class="page">
    <!-- 控制栏 -->
    <SectionCard padding>
      <div class="alert-controls">
        <div class="alert-controls__left">
          <label>级别</label>
          <el-select v-model="filterLevel" size="small" style="width:100px" @change="load">
            <el-option label="全部" value="all" />
            <el-option label="严重" value="critical" />
            <el-option label="警告" value="warning" />
            <el-option label="提示" value="info" />
          </el-select>
          <label>状态</label>
          <el-select v-model="filterStatus" size="small" style="width:110px" @change="load">
            <el-option label="未处理" value="open" />
            <el-option label="已确认" value="acknowledged" />
            <el-option label="已解决" value="resolved" />
            <el-option label="全部" value="all" />
          </el-select>
        </div>
        <div class="alert-controls__right">
          <span v-if="lastUpdated" class="alert-updated">{{ lastUpdated }} 更新</span>
          <el-button size="small" @click="resolveAll" v-if="stats.open > 0">全部解决</el-button>
          <el-button type="primary" size="small" :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>
    </SectionCard>

    <!-- KPI 统计卡片 -->
    <div class="stat-grid">
      <StatCard :value="stats.total" label="告警总数" size="sm" />
      <StatCard
        :value="stats.open"
        label="未处理"
        :color="stats.open > 0 ? 'var(--color-danger-500)' : 'var(--color-success-500)'"
        size="sm"
      />
      <StatCard :value="stats.critical" label="严重" color="var(--color-danger-500)" size="sm" />
      <StatCard :value="stats.warning" label="警告" color="var(--color-warning-500)" size="sm" />
    </div>

    <!-- 告警列表 -->
    <SectionCard padding>
      <el-table
        :data="filtered"
        v-loading="loading"
        stripe
        style="width:100%"
        :default-sort="{ prop: 'created_at', order: 'descending' }"
        empty-text="暂无告警数据"
      >
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="created_at" label="时间" width="170" sortable>
          <template #default="{row}">
            <span class="alert-time">{{ row.created_at ? row.created_at.replace('T', ' ').substring(0, 19) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="db_alias" label="数据库" width="100" />
        <el-table-column prop="metric" label="指标" width="100" />
        <el-table-column prop="level" label="级别" width="80">
          <template #default="{row}">
            <StatusTag :status="row.level" />
          </template>
        </el-table-column>
        <el-table-column prop="current_value" label="当前值" width="100" sortable>
          <template #default="{row}">
            <span class="alert-value" :class="`alert-value--${row.level}`">
              {{ typeof row.current_value === 'number' ? row.current_value.toFixed(1) : row.current_value }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="threshold" label="阈值" width="80" />
        <el-table-column prop="message" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{row}">
            <StatusTag :status="row.status" :label="row.status === 'open' ? '未处理' : row.status === 'acknowledged' ? '已确认' : '已解决'" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{row}">
            <el-button v-if="row.status === 'open'" size="small" @click="acknowledge(row.id)">确认</el-button>
            <el-button v-if="row.status !== 'resolved'" size="small" type="success" plain @click="resolve(row.id)">解决</el-button>
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }

.alert-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.alert-controls__left, .alert-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.alert-controls label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.alert-updated {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.alert-time {
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
}
.alert-value {
  font-weight: var(--font-semibold);
}
.alert-value--critical { color: var(--color-danger-500); }
.alert-value--warning { color: var(--color-warning-500); }
</style>