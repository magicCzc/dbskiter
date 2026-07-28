<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import type { ScheduledTaskInfo } from '@/types'

const dbStore = useDatabaseStore()
const tasks = ref<ScheduledTaskInfo[]>([])
const taskTypes = ref<Record<string, { label: string; description: string; default_cron: string }>>({})
const loading = ref(false)
const lastUpdated = ref('')
const dialogVisible = ref(false)
const saving = ref(false)

const form = ref({
  name: '', task_type: 'diagnose', db_alias: '', cron_expr: '0 9 * * *',
})

const taskTypeOptions = [
  { value: 'diagnose', label: '定时诊断', desc: '定期执行数据库诊断' },
  { value: 'inspect', label: '定时巡检', desc: '定期执行综合巡检' },
  { value: 'report', label: '定时报告', desc: '定期生成健康报告' },
  { value: 'collect', label: '指标采集', desc: '定期采集数据库指标' },
]

const enabledTasks = computed(() => tasks.value.filter(t => t.is_enabled))
const disabledTasks = computed(() => tasks.value.filter(t => !t.is_enabled))

async function load() {
  loading.value = true
  try {
    const [td, tt] = await Promise.all([
      api.listTasks(),
      api.listTaskTypes(),
    ])
    tasks.value = (td.tasks || []) as unknown as ScheduledTaskInfo[]
    taskTypes.value = (tt.types || {}) as Record<string, { label: string; description: string; default_cron: string }>
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { name: '', task_type: 'diagnose', db_alias: dbStore.current, cron_expr: '0 9 * * *' }
  dialogVisible.value = true
}

async function save() {
  if (!form.value.name || !form.value.cron_expr) {
    ElMessage.warning('请填写完整信息')
    return
  }
  saving.value = true
  try {
    const data = await api.createTask({ ...form.value, db_alias: form.value.db_alias || dbStore.current })
    if (data.success) {
      ElMessage.success(`任务 '${form.value.name}' 已创建`)
      dialogVisible.value = false
      await load()
    } else {
      ElMessage.error(data.message || '创建失败')
    }
  } catch (e: any) {
    ElMessage.error(`创建失败: ${e.message}`)
  } finally {
    saving.value = false
  }
}

async function toggleTask(task: ScheduledTaskInfo) {
  try {
    const data = await api.toggleTask(task.id)
    if (data.success) {
      ElMessage.success(data.message)
      await load()
    }
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

async function deleteTask(task: ScheduledTaskInfo) {
  try {
    const data = await api.deleteTask(task.id)
    if (data.success) {
      ElMessage.success(data.message)
      await load()
    }
  } catch (e: any) {
    ElMessage.error(`删除失败: ${e.message}`)
  }
}

function cronDescription(expr: string): string {
  const map: Record<string, string> = {
    '0 9 * * *': '每天 09:00',
    '0 2 * * 0': '每周日 02:00',
    '0 10 1 * *': '每月 1 日 10:00',
    '*/5 * * * *': '每 5 分钟',
    '0 * * * *': '每小时',
    '0 0 * * *': '每天午夜',
  }
  return map[expr] || expr
}

onMounted(() => { dbStore.loadDatabases(); load() })
</script>

<template>
  <div class="page">
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
    </div>

    <el-card shadow="never" class="section-card">
      <div class="control-row">
        <div class="control-left">
          <h2 style="margin:0;font-size:16px;display:flex;align-items:center;gap:8px">⏰ 定时任务</h2>
        </div>
        <div class="control-right">
          <el-button type="primary" size="small" @click="openCreate">
            <el-icon><Plus /></el-icon> 新建任务
          </el-button>
          <el-button size="small" :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-value" style="color:#6366f1">{{ tasks.length }}</div><div class="kpi-label">任务总数</div></div>
      <div class="kpi-card"><div class="kpi-value" style="color:#22c55e">{{ enabledTasks.length }}</div><div class="kpi-label">运行中</div></div>
      <div class="kpi-card"><div class="kpi-value" style="color:#94a3b8">{{ disabledTasks.length }}</div><div class="kpi-label">已暂停</div></div>
    </div>

    <!-- 任务列表 -->
    <el-card shadow="never" class="section-card">
      <el-table :data="tasks" v-loading="loading" stripe style="width:100%" :empty-text="'暂无定时任务，点击新建任务开始'"
        :default-sort="{ prop: 'created_at', order: 'descending' }">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="name" label="任务名称" min-width="150">
          <template #default="{row}"><strong>{{ row.name }}</strong></template>
        </el-table-column>
        <el-table-column prop="task_type" label="类型" width="100">
          <template #default="{row}">
            <el-tag size="small">{{ taskTypeOptions.find(t => t.value === row.task_type)?.label || row.task_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="db_alias" label="数据库" width="100" />
        <el-table-column prop="cron_expr" label="调度计划" width="150">
          <template #default="{row}">
            <code style="font-size:12px">{{ row.cron_expr }}</code>
            <span style="font-size:11px;color:var(--el-text-color-placeholder);margin-left:4px">{{ cronDescription(row.cron_expr) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_enabled" label="状态" width="80">
          <template #default="{row}">
            <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">{{ row.is_enabled ? '运行中' : '已暂停' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_run" label="上次执行" width="170">
          <template #default="{row}">{{ row.last_run ? row.last_run.replace('T', ' ').substring(0, 19) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{row}">
            <el-button size="small" :type="row.is_enabled ? 'warning' : 'success'" plain @click="toggleTask(row)">
              {{ row.is_enabled ? '暂停' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" plain @click="deleteTask(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建任务对话框 -->
    <el-dialog v-model="dialogVisible" title="新建定时任务" width="500px">
      <el-form :model="form" label-width="100px" size="small">
        <el-form-item label="任务名称" required>
          <el-input v-model="form.name" placeholder="如: 每日健康诊断" />
        </el-form-item>
        <el-form-item label="任务类型" required>
          <el-select v-model="form.task_type" style="width:100%">
            <el-option v-for="t in taskTypeOptions" :key="t.value" :label="t.label" :value="t.value">
              <span>{{ t.label }}</span>
              <span style="font-size:12px;color:var(--el-text-color-placeholder);margin-left:8px">- {{ t.desc }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="数据库" required>
          <el-select v-model="form.db_alias" style="width:100%">
            <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="Cron 表达式" required>
          <el-input v-model="form.cron_expr" placeholder="0 9 * * *" />
          <div style="font-size:12px;color:var(--el-text-color-placeholder);margin-top:4px">
            常用: 0 9 * * * (每天9点) | 0 2 * * 0 (每周日2点) | */5 * * * * (每5分钟)
          </div>
        </el-form-item>
        <el-form-item>
          <div style="font-size:12px;color:var(--el-text-color-secondary);padding:8px;background:var(--el-fill-color-light);border-radius:4px;width:100%">
            创建后任务将立即开始按计划执行
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }
.section-card { margin-bottom: 16px; }
.control-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.control-left, .control-right { display: flex; align-items: center; gap: 12px; }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 16px; }
.kpi-card { background: var(--el-bg-color); border-radius: 8px; padding: 20px; border: 1px solid var(--el-border-color-light); text-align: center; }
.kpi-value { font-size: 28px; font-weight: 700; }
.kpi-label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }

.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }
</style>