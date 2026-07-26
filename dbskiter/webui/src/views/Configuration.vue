<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'

const status = ref<any>(null)
const databases = ref<string[]>(['default'])
const selectedDb = ref('default')
const testResult = ref<{ success: boolean; message: string } | null>(null)
const testing = ref(false)
const loading = ref(false)

async function loadStatus() {
  loading.value = true
  try {
    status.value = await api.status()
    const dbs = await api.databases()
    if (dbs.databases?.length) databases.value = dbs.databases
  } catch { /* 静默 */ }
  finally { loading.value = false }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const resp = await fetch(`/api/diagnose/connection?database=${encodeURIComponent(selectedDb.value)}`)
    const data = await resp.json()
    testResult.value = {
      success: data.success,
      message: data.message || (data.success ? '连接成功' : '连接失败：无法连接到数据库'),
    }
  } catch (e: any) {
    testResult.value = { success: false, message: `请求失败: ${e.message}` }
  } finally {
    testing.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="card">
    <h2>⚙️ 系统配置</h2>

    <div class="config-section">
      <h3>API 服务状态</h3>
      <div v-if="status" class="status-grid">
        <div class="status-item">
          <span class="label">服务状态</span>
          <span class="status status-healthy">运行中</span>
        </div>
        <div class="status-item">
          <span class="label">版本</span>
          <span><code>v{{ status.version }}</code></span>
        </div>
        <div class="status-item">
          <span class="label">API 端点</span>
          <span>{{ status.api_endpoints?.length || 0 }} 个</span>
        </div>
      </div>
    </div>

    <div class="config-section">
      <h3>🔌 数据库连接测试</h3>
      <p style="color:var(--text-secondary);font-size:14px;margin-bottom:12px;">
        选择一个数据库别名，测试是否能正常连接。
      </p>
      <div class="test-row">
        <select v-model="selectedDb" style="flex:1;max-width:300px;">
          <option v-for="d in databases" :key="d" :value="d">{{ d }}</option>
        </select>
        <button class="btn-primary" @click="testConnection" :disabled="testing">
          {{ testing ? '测试中...' : '🔄 测试连接' }}
        </button>
      </div>
      <div v-if="testResult" :class="testResult.success ? 'success' : 'error'" style="margin-top:12px;">
        {{ testResult.message }}
      </div>
    </div>

    <div class="config-section">
      <h3>📋 已配置数据库</h3>
      <div v-if="databases.length" class="db-list">
        <div v-for="d in databases" :key="d" class="db-item" @click="selectedDb = d">
          <span class="db-icon">🗄️</span>
          <span class="db-name">{{ d }}</span>
          <span v-if="d === selectedDb" class="db-active">当前</span>
        </div>
      </div>
      <div v-else style="color:var(--text-secondary);font-size:14px;">暂无已配置的数据库</div>
    </div>

    <div class="config-section">
      <h3>快速链接</h3>
      <div class="link-list">
        <a href="/docs" target="_blank" class="link-item">📖 Swagger API 文档</a>
        <a href="/redoc" target="_blank" class="link-item">📕 ReDoc 文档</a>
        <a href="https://github.com/magicCzc/dbskiter" target="_blank" class="link-item">🐙 GitHub 仓库</a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-section { margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid var(--border); }
.config-section:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.config-section h3 { font-size: 14px; color: var(--text-secondary); margin-bottom: 12px; }
.status-grid { display: grid; gap: 12px; }
.status-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; }
.status-item .label { color: var(--text-secondary); }
.test-row { display: flex; gap: 12px; align-items: center; }
.db-list { display: flex; flex-direction: column; gap: 4px; }
.db-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px;
  border: 1px solid var(--border); border-radius: 8px; cursor: pointer;
  transition: all 0.2s;
}
.db-item:hover { border-color: var(--primary); background: var(--table-hover); }
.db-icon { font-size: 18px; }
.db-name { font-weight: 500; flex: 1; }
.db-active { font-size: 12px; background: var(--primary); color: white; padding: 2px 8px; border-radius: 12px; }
.link-list { display: flex; flex-direction: column; gap: 8px; }
.link-item { padding: 10px 16px; border: 1px solid var(--border); border-radius: 8px; text-decoration: none; color: var(--text); transition: all 0.2s; }
.link-item:hover { border-color: var(--primary); background: #f8fafc; }
</style>