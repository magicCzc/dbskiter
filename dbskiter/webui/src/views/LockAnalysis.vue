<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { LockInfo } from '@/types'

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
  } catch {
    // 用户取消
  }
}

onMounted(() => { dbStore.loadDatabases(); load() })
</script>

<template>
  <div class="page">
    <!-- 实时反馈指示器 -->
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
    </div>

    <!-- 严重告警横幅 -->
    <el-alert
      v-if="criticalLocks > 0"
      :title="`发现 ${criticalLocks} 个长时间锁等待（超过 30s），建议立即处理`"
      type="error"
      show-icon
      closable
      style="margin-bottom:16px"
    />
    <el-alert
      v-else-if="totalLocks > 0 && totalLocks <= 3"
      title="存在少量锁等待，建议关注"
      type="warning"
      show-icon
      closable
      style="margin-bottom:16px"
    />

    <!-- 控制栏 -->
    <el-card shadow="never" class="section-card">
      <div class="control-row">
        <div class="control-left">
          <label>数据库：</label>
          <el-select v-model="dbStore.current" size="small" style="width:160px" @change="load">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <el-button type="primary" size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div class="control-right">
          <el-tag v-if="totalLocks > 0" :type="criticalLocks > 0 ? 'danger' : 'warning'" size="medium" effect="dark">
            {{ totalLocks }} 个锁等待
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: totalLocks > 5 ? '#ef4444' : '#6366f1' }">{{ totalLocks }}</div>
        <div class="kpi-label">当前锁等待</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: maxWait > 30 ? '#ef4444' : maxWait > 10 ? '#f59e0b' : '#6366f1' }">
          {{ maxWait ? maxWait.toFixed(1) + 's' : '-' }}
        </div>
        <div class="kpi-label">最长等待</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: blockedQueries > 0 ? '#ef4444' : '#6366f1' }">{{ blockedQueries }}</div>
        <div class="kpi-label">阻塞查询数</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" :style="{ color: deadlockCount > 0 ? '#ef4444' : '#6366f1' }">{{ deadlockCount }}</div>
        <div class="kpi-label">死锁记录</div>
      </div>
    </div>

    <!-- 锁详情 -->
    <el-card shadow="never" class="section-card">
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="当前锁等待" name="current">
          <el-table :data="locks" v-loading="loading" stripe style="width:100%" :empty-text="loading ? '加载中...' : '当前无锁等待 ✅'">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="blocking_pid" label="阻塞进程" width="100" />
            <el-table-column prop="blocked_pid" label="被阻塞进程" width="100" />
            <el-table-column prop="blocking_query" label="阻塞 SQL" min-width="250" show-overflow-tooltip>
              <template #default="{row}"><code style="font-size:12px">{{ row.blocking_query || '-' }}</code></template>
            </el-table-column>
            <el-table-column prop="blocked_query" label="被阻塞 SQL" min-width="250" show-overflow-tooltip>
              <template #default="{row}"><code style="font-size:12px">{{ row.blocked_query || '-' }}</code></template>
            </el-table-column>
            <el-table-column prop="blocking_duration" label="等待时间" width="100" sortable>
              <template #default="{row}">
                <span :style="{ color: row.blocking_duration > 30 ? '#ef4444' : row.blocking_duration > 10 ? '#f59e0b' : '#22c55e', fontWeight: 600 }">
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
          <el-table :data="deadlocks" v-loading="loading" stripe style="width:100%" :empty-text="'暂无死锁记录 ✅'">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="blocking_pid" label="阻塞进程" width="100" />
            <el-table-column prop="blocked_pid" label="被阻塞进程" width="100" />
            <el-table-column prop="blocking_query" label="SQL" min-width="300" show-overflow-tooltip>
              <template #default="{row}"><code style="font-size:12px">{{ row.blocking_query || '-' }}</code></template>
            </el-table-column>
            <el-table-column prop="timestamp" label="发生时间" width="180" />
            <el-table-column prop="severity" label="级别" width="90">
              <template #default="{row}">
                <el-tag :type="row.severity === 'deadlock' ? 'danger' : 'warning'" size="small">{{ row.severity || 'deadlock' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.section-card { margin-bottom: 16px; }
.control-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.control-left, .control-right { display: flex; align-items: center; gap: 12px; }
.control-row label { font-size: 14px; color: var(--el-text-color-secondary); }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 16px; }
.kpi-card { background: var(--el-bg-color); border-radius: 8px; padding: 20px; border: 1px solid var(--el-border-color-light); text-align: center; }
.kpi-value { font-size: 28px; font-weight: 700; }
.kpi-label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }

.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }
</style>