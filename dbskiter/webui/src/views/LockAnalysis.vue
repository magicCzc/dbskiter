<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { LockInfo } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const dbStore = useDatabaseStore()
const locks = ref<LockInfo[]>([])
const deadlocks = ref<LockInfo[]>([])
const loading = ref(false)
const activeTab = ref('current')
const lastUpdated = ref('')

const totalLocks = computed(() => locks.value.length)
const deadlockCount = computed(() => deadlocks.value.length)
const maxWait = computed(() => {
  if (!locks.value.length) return 0
  return Math.max(...locks.value.map(l => l.blocking_duration || 0))
})
const blockedQueries = computed(() => locks.value.filter(l => l.blocked_query).length)
const criticalLocks = computed(() => {
  const threshold = 30
  return locks.value.filter(l => (l.blocking_duration || 0) > threshold).length
})

async function load() {
  loading.value = true
  try {
    const data = await api.locks(dbStore.current)
    if (!data.success && data.error) {
      ElMessage.warning(data.error)
      if (data.solution) ElMessage.info(`解决: ${data.solution}`)
      locks.value = []
      deadlocks.value = []
      lastUpdated.value = new Date().toLocaleTimeString()
      return
    }
    const raw = data.data?.raw_metrics || data.raw_data || data
    locks.value = (raw.locks || raw.lock_waits || []).slice(0, 50)
    deadlocks.value = (raw.deadlocks || raw.deadlock_history || []).slice(0, 20)
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
    locks.value = []
    deadlocks.value = []
  } finally {
    loading.value = false
  }
}

async function killQuery(pid: number, query: string) {
  try {
    await ElMessageBox.confirm(
      `确定要 KILL 进程 ${pid} 吗？\nSQL: ${(query || '').substring(0, 100)}`,
      '终止查询',
      { confirmButtonText: '确认终止', cancelButtonText: '取消', type: 'warning' }
    )
    const resp = await fetch(`/api/sql/execute?database=${encodeURIComponent(dbStore.current)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql: `KILL ${pid}`, limit: 1, read_only: false }),
    })
    const result = await resp.json()
    if (result.success || result.data?.success) {
      ElMessage.success(`已终止进程 ${pid}`)
      await load()
    } else {
      ElMessage.error(`终止失败: ${result.error || '未知错误'}`)
    }
  } catch { /* 用户取消 */ }
}

onMounted(() => { dbStore.loadDatabases(); load() })
</script>

<template>
  <div class="page">
    <el-alert
      v-if="criticalLocks > 0"
      :title="`发现 ${criticalLocks} 个长时间锁等待（超过 30s），建议立即处理`"
      type="error"
      show-icon
      closable
      class="lock-alert"
    />
    <el-alert
      v-else-if="totalLocks > 0 && totalLocks <= 3"
      title="存在少量锁等待，建议关注"
      type="warning"
      show-icon
      closable
      class="lock-alert"
    />

    <SectionCard padding>
      <div class="lock-controls">
        <div class="lock-controls__left">
          <label>数据库</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="lock-controls__right">
          <el-tag v-if="totalLocks > 0" :type="criticalLocks > 0 ? 'danger' : 'warning'" effect="dark">
            {{ totalLocks }} 个锁等待
          </el-tag>
        </div>
      </div>
    </SectionCard>

    <div class="stat-grid">
      <StatCard
        :value="totalLocks"
        label="当前锁等待"
        size="sm"
        :color="totalLocks > 5 ? 'var(--color-danger-500)' : 'var(--color-brand-500)'"
      />
      <StatCard
        :value="maxWait ? maxWait.toFixed(1) + 's' : '-'"
        label="最长等待"
        size="sm"
        :color="maxWait > 30 ? 'var(--color-danger-500)' : maxWait > 10 ? 'var(--color-warning-500)' : 'var(--color-brand-500)'"
      />
      <StatCard
        :value="blockedQueries"
        label="阻塞查询数"
        size="sm"
        :color="blockedQueries > 0 ? 'var(--color-danger-500)' : 'var(--color-brand-500)'"
      />
      <StatCard
        :value="deadlockCount"
        label="死锁记录"
        size="sm"
        :color="deadlockCount > 0 ? 'var(--color-danger-500)' : 'var(--color-brand-500)'"
      />
    </div>

    <SectionCard padding>
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="当前锁等待" name="current">
          <el-table :data="locks" v-loading="loading" stripe style="width:100%">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="blocking_pid" label="阻塞进程" width="100" />
            <el-table-column prop="blocked_pid" label="被阻塞进程" width="100" />
            <el-table-column prop="blocking_query" label="阻塞 SQL" min-width="250" show-overflow-tooltip>
              <template #default="{row}"><code class="lock-sql">{{ row.blocking_query || '-' }}</code></template>
            </el-table-column>
            <el-table-column prop="blocked_query" label="被阻塞 SQL" min-width="250" show-overflow-tooltip>
              <template #default="{row}"><code class="lock-sql">{{ row.blocked_query || '-' }}</code></template>
            </el-table-column>
            <el-table-column prop="blocking_duration" label="等待时间" width="100" sortable>
              <template #default="{row}">
                <span class="lock-time" :class="`lock-time--${row.blocking_duration > 30 ? 'critical' : row.blocking_duration > 10 ? 'warning' : 'ok'}`">
                  {{ row.blocking_duration ? row.blocking_duration.toFixed(1) + 's' : '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{row}">
                <el-button size="small" type="danger" plain @click="killQuery(row.blocking_pid, row.blocking_query)">
                  KILL {{ row.blocking_pid }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`死锁历史 (${deadlockCount})`" name="history">
          <el-table :data="deadlocks" v-loading="loading" stripe style="width:100%">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="blocking_pid" label="阻塞进程" width="100" />
            <el-table-column prop="blocked_pid" label="被阻塞进程" width="100" />
            <el-table-column prop="blocking_query" label="SQL" min-width="300" show-overflow-tooltip>
              <template #default="{row}"><code class="lock-sql">{{ row.blocking_query || '-' }}</code></template>
            </el-table-column>
            <el-table-column prop="timestamp" label="发生时间" width="180" />
            <el-table-column prop="severity" label="级别" width="90">
              <template #default="{row}">
                <StatusTag :status="row.severity || 'critical'" />
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.lock-alert { margin-bottom: var(--space-4); }

.lock-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.lock-controls__left, .lock-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.lock-controls label { font-size: var(--text-sm); color: var(--text-secondary); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.lock-sql { font-size: var(--text-xs); font-family: var(--font-mono); }
.lock-time { font-weight: var(--font-semibold); font-variant-numeric: tabular-nums; }
.lock-time--critical { color: var(--color-danger-500); }
.lock-time--warning { color: var(--color-warning-500); }
.lock-time--ok { color: var(--color-success-500); }
</style>