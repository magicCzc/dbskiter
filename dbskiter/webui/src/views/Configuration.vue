<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api'

const status = ref<any>(null)
const loading = ref(false)
const dbConfig = ref({
  host: 'localhost',
  port: 3306,
  user: 'root',
  database: 'default',
})

async function loadStatus() {
  loading.value = true
  try {
    status.value = await api.status()
  } catch { /* 静默 */ }
  finally { loading.value = false }
}

function testConnection() {
  alert('连接测试功能需要后端支持，请先配置数据库连接。')
}

// 加载状态
loadStatus()
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
      <h3>数据库连接</h3>
      <div class="form-grid">
        <div class="form-group">
          <label>主机</label>
          <input v-model="dbConfig.host" />
        </div>
        <div class="form-group">
          <label>端口</label>
          <input v-model.number="dbConfig.port" type="number" />
        </div>
        <div class="form-group">
          <label>用户名</label>
          <input v-model="dbConfig.user" />
        </div>
        <div class="form-group">
          <label>数据库</label>
          <input v-model="dbConfig.database" />
        </div>
      </div>
      <button class="btn-primary" @click="testConnection" style="margin-top:12px;">测试连接</button>
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
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group input { width: 100%; }
.link-list { display: flex; flex-direction: column; gap: 8px; }
.link-item { padding: 10px 16px; border: 1px solid var(--border); border-radius: 8px; text-decoration: none; color: var(--text); transition: all 0.2s; }
.link-item:hover { border-color: var(--primary); background: #f8fafc; }
</style>