<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { ApiStatus, DbConfigTestResponse } from '@/types'
import SectionCard from '@/components/SectionCard.vue'

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
      message: data.message || (data.success ? '连接成功' : '连接失败'),
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
    <SectionCard padding>
      <h2 class="config-title">系统配置</h2>
    </SectionCard>

    <SectionCard title="API 服务状态">
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
      <div v-else class="config-loading">加载中...</div>
    </SectionCard>

    <SectionCard title="数据库连接测试">
      <p class="config-desc">选择一个数据库别名，测试是否能正常连接。</p>
      <div class="test-row">
        <el-select v-model="dbStore.current" size="small" style="width:300px">
          <el-option v-for="d in dbStore.databases" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button type="primary" size="small" :loading="testing" @click="testConnection">测试连接</el-button>
      </div>
      <el-alert
        v-if="testResult"
        :title="testResult.message"
        :type="testResult.success ? 'success' : 'error'"
        show-icon
        closable
        class="test-alert"
        @close="testResult = null"
      />
    </SectionCard>

    <SectionCard title="已配置数据库">
      <div v-if="dbStore.databases.length" class="db-list">
        <div
          v-for="d in dbStore.databases"
          :key="d"
          class="db-item"
          :class="{ 'db-item--active': d === dbStore.current }"
          @click="dbStore.setCurrent(d)"
        >
          <svg class="db-item__icon" viewBox="0 0 24 24" fill="none" width="20" height="20">
            <rect x="3" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.35"/>
            <rect x="14" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55"/>
            <rect x="3" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55"/>
            <rect x="14" y="14" width="7" height="7" rx="1.5" fill="currentColor"/>
          </svg>
          <div class="db-item__info">
            <div class="db-item__name">{{ d }}</div>
            <div class="db-item__desc">{{ d === dbStore.current ? '当前选中' : '点击切换' }}</div>
          </div>
          <el-tag v-if="d === dbStore.current" type="primary" size="small">当前</el-tag>
        </div>
      </div>
      <div v-else class="config-empty">暂无已配置的数据库</div>
    </SectionCard>

    <SectionCard title="快速链接">
      <div class="link-row">
        <el-button tag="a" href="/docs" target="_blank" plain>Swagger API 文档</el-button>
        <el-button tag="a" href="/redoc" target="_blank" plain>ReDoc 文档</el-button>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }

.config-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}
.config-desc {
  margin: 0 0 var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.config-loading, .config-empty {
  text-align: center;
  padding: var(--space-5);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}

.status-list { display: flex; flex-direction: column; }
.status-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-muted);
  font-size: var(--text-sm);
}
.status-item:last-child { border-bottom: none; }
.status-label {
  color: var(--text-tertiary);
  min-width: 80px;
}

.test-row { display: flex; align-items: center; gap: var(--space-3); }
.test-alert { margin-top: var(--space-3); }

.db-list { display: flex; flex-direction: column; gap: var(--space-2); }
.db-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}
.db-item:hover {
  border-color: var(--color-brand-300);
  background: var(--color-brand-50);
}
.db-item--active {
  border-color: var(--color-brand-500);
  background: var(--color-brand-50);
}
.db-item__icon {
  color: var(--color-brand-500);
  flex-shrink: 0;
}
.db-item__info { flex: 1; }
.db-item__name {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}
.db-item__desc {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.link-row { display: flex; gap: var(--space-2); }
</style>