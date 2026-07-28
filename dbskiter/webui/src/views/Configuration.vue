<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { ApiStatus, DbConfigTestResponse } from '@/types'

const dbStore = useDatabaseStore()

const status = ref<ApiStatus | null>(null)
const testResult = ref<DbConfigTestResponse | null>(null)
const testing = ref(false)
const loading = ref(false)
const lastUpdated = ref('')

async function loadStatus() {
  loading.value = true
  try {
    status.value = await api.status()
    await dbStore.loadDatabases()
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch { /* 静默 */ }
  finally { loading.value = false }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const data = await api.testDbConfig({ alias: dbStore.current })
    testResult.value = {
      success: data.success,
      message: data.message || (data.success ? '连接成功 🎉' : '连接失败'),
    }
    dbStore.connectionStatus[dbStore.current] = data.success ? 'online' : 'offline'
  } catch (e: any) {
    testResult.value = { success: false, message: `请求失败: ${e.message}` }
  } finally {
    testing.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="page">
    <!-- 实时反馈 -->
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
    </div>

    <!-- 标题 -->
    <el-card shadow="never" class="section-card">
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:20px">⚙️</span>
        <h2 style="margin:0;font-size:16px">系统配置</h2>
      </div>
    </el-card>

    <!-- API 服务状态 -->
    <el-card shadow="never" class="section-card">
      <template #header><span>🟢 API 服务状态</span></template>
      <div v-if="status" class="status-list">
        <div class="status-item">
          <span class="status-label">服务状态</span>
          <el-tag type="success" size="small">运行中</el-tag>
        </div>
        <div class="status-item">
          <span class="status-label">版本</span>
          <el-tag type="info" size="small">v{{ status.version }}</el-tag>
        </div>
        <div class="status-item">
          <span class="status-label">API 端点</span>
          <span>{{ status.api_endpoints?.length || 0 }} 个</span>
        </div>
      </div>
      <div v-else style="padding:20px;text-align:center;color:var(--el-text-color-placeholder)">加载中...</div>
    </el-card>

    <!-- 连接测试 -->
    <el-card shadow="never" class="section-card">
      <template #header><span>🔌 数据库连接测试</span></template>
      <div style="margin-bottom:12px;font-size:13px;color:var(--el-text-color-secondary)">
        选择一个数据库别名，测试是否能正常连接。
      </div>
      <div class="test-row">
        <el-select v-model="dbStore.current" size="small" style="width:300px">
          <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button type="primary" size="small" :loading="testing" @click="testConnection">
          测试连接
        </el-button>
      </div>
      <el-alert
        v-if="testResult"
        :title="testResult.message"
        :type="testResult.success ? 'success' : 'error'"
        show-icon
        closable
        style="margin-top:12px"
        @close="testResult = null"
      />
    </el-card>

    <!-- 已配置数据库 -->
    <el-card shadow="never" class="section-card">
      <template #header><span>📋 已配置数据库</span></template>
      <div v-if="dbStore.databases.length" class="db-list">
        <div
          v-for="d in dbStore.databases"
          :key="d"
          class="db-item"
          :class="{ active: d === dbStore.current }"
          @click="dbStore.setCurrent(d)"
        >
          <span style="font-size:18px">🗄️</span>
          <div class="db-info">
            <div class="db-name">{{ d }}</div>
            <div class="db-desc">{{ d === dbStore.current ? '当前选中' : '点击切换' }}</div>
          </div>
          <el-tag v-if="d === dbStore.current" type="primary" size="small">当前</el-tag>
        </div>
      </div>
      <div v-else style="padding:20px;text-align:center;color:var(--el-text-color-placeholder)">暂无已配置的数据库</div>
    </el-card>

    <!-- 快速链接 -->
    <el-card shadow="never" class="section-card">
      <template #header><span>🔗 快速链接</span></template>
      <div style="display:flex;gap:12px">
        <el-button tag="a" href="/docs" target="_blank" plain>Swagger API 文档</el-button>
        <el-button tag="a" href="/redoc" target="_blank" plain>ReDoc 文档</el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }
.section-card { margin-bottom: 16px; }

.status-list { display: flex; flex-direction: column; gap: 8px; }
.status-item { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.status-item:last-child { border-bottom: none; }
.status-label { font-size: 14px; color: var(--el-text-color-secondary); min-width: 80px; }

.test-row { display: flex; align-items: center; gap: 12px; }

.db-list { display: flex; flex-direction: column; gap: 4px; }
.db-item { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid var(--el-border-color-light); border-radius: 8px; cursor: pointer; transition: all 0.15s; }
.db-item:hover { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.db-item.active { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.db-info { flex: 1; }
.db-name { font-size: 14px; font-weight: 500; }
.db-desc { font-size: 12px; color: var(--el-text-color-placeholder); }

.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }
</style>