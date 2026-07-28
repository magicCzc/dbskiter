<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { DiagnoseResult, DiagnoseIssue } from '@/types'

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
    { label: '健康评分', value: d.score ?? '-', color: d.score > 80 ? '#22c55e' : d.score > 60 ? '#f59e0b' : '#ef4444', path: '' },
    { label: '问题数', value: d.issues?.length ?? 0, color: '#6366f1', path: '' },
    { label: '慢查询', value: d.raw_data?.slow_queries?.length ?? 0, color: '#f59e0b', path: '/slow-queries' },
    { label: '锁等待', value: d.raw_data?.locks?.length ?? d.raw_data?.lock_waits ?? 0, color: '#ef4444', path: '/locks' },
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
  // "dbskiter --database=chenzc diagnose locks" -> "diagnose locks"
  const parts = cmd.split(' ')
  const dbIdx = parts.findIndex(p => p.startsWith('--database='))
  const cmdStart = dbIdx >= 0 ? dbIdx + 1 : 2 // skip 'dbskiter' and '--database=...'
  return parts.slice(cmdStart).join(' ') || cmd
}

async function executeCommand(cmd: string) {
  cmdLoading.value = cmd
  try {
    // 解析命令: "dbskiter --database=chenzc diagnose locks"
    const parts = cmd.split(' ')
    // 找到第一个不以 -- 开头的参数作为子命令起始
    const cmdParts = parts.filter(p => !p.startsWith('--') && p !== 'dbskiter')
    if (cmdParts.length < 2) {
      ElMessage.warning('无法解析命令')
      return
    }
    const baseCmd = cmdParts[0] // e.g. "diagnose"
    const subCmd = cmdParts.slice(1).join(' ') // e.g. "locks" or "top --limit=10"

    // 通过 API 执行
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
    <!-- 实时反馈 -->
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
    </div>

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

    <!-- 摘要卡片（可点击） -->
    <div v-if="result" class="kpi-grid">
      <div
        v-for="c in summaryCards"
        :key="c.label"
        class="kpi-card"
        :class="{ clickable: c.path }"
        @click="navigateTo(c.path)"
      >
        <div class="kpi-value" :style="{color: c.color}">{{ c.value }}</div>
        <div class="kpi-label">{{ c.label }}</div>
        <div v-if="c.path" class="kpi-sub">查看详情 →</div>
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

      <!-- 问题列表（含下钻） -->
      <div v-if="result.issues?.length" style="margin-top:16px">
        <h4 style="margin-bottom:8px;font-size:14px">⚠️ 发现的问题</h4>
        <el-table :data="result.issues" stripe size="small">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="message" label="描述" min-width="200" />
          <el-table-column prop="severity" label="级别" width="80">
            <template #default="{row}"><el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'" size="small">{{ row.severity }}</el-tag></template>
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

      <!-- AI 提示 -->
      <div v-if="result.ai_hints?.focus_areas?.length" style="margin-top:16px">
        <h4 style="margin-bottom:8px;font-size:14px">💡 AI 建议关注</h4>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <el-tag v-for="area in result.ai_hints.focus_areas" :key="area" type="warning" style="cursor:pointer" @click="navigateTo('/slow-queries')">{{ area }}</el-tag>
        </div>
      </div>

      <!-- 可执行的相关命令 -->
      <div v-if="result.ai_hints?.related_commands?.length" style="margin-top:16px">
        <h4 style="margin-bottom:8px;font-size:14px">▶️ 建议执行</h4>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
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

        <!-- 命令执行结果 -->
        <div v-for="(res, cmd) in cmdResults" :key="cmd" style="margin-top:12px">
          <el-collapse>
            <el-collapse-item :title="commandLabel(cmd) + ' 结果'" name="cmd">
              <pre style="font-size:12px;max-height:300px;overflow:auto;background:var(--el-fill-color-light);padding:12px;border-radius:6px">{{ JSON.stringify(res, null, 2) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <!-- 原始数据 -->
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
.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }
.kpi-card.clickable { cursor: pointer; transition: all 0.2s; }
.kpi-card.clickable:hover { border-color: var(--el-color-primary); transform: translateY(-1px); }
.kpi-sub { font-size: 11px; color: var(--el-color-primary); margin-top: 4px; }
</style>