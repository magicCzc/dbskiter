<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { api } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import type { DbConfig as DbConfigType, DbConfigListResponse } from '@/types'

const dbStore = useDatabaseStore()

const dbConfigs = ref<Record<string, DbConfigType>>({})
const loading = ref(false)
const testing = ref<Record<string, boolean>>({})
const lastUpdated = ref('')
const dialogVisible = ref(false)
const dialogMode = ref<'add' | 'edit'>('add')
const editAlias = ref('')
const form = ref<DbConfigType>({
  alias: '', host: '127.0.0.1', port: 3306, user: 'root',
  password: '', database: '', dialect: 'mysql+pymysql', pool_size: 5,
})
const saving = ref(false)
const testingAll = ref(false)

const dbList = ref<(DbConfigType & { alias: string; status: string })[]>([])

const dialects = [
  { value: 'mysql+pymysql', label: 'MySQL / MariaDB' },
  { value: 'postgresql+psycopg2', label: 'PostgreSQL' },
  { value: 'oracle+oracledb', label: 'Oracle' },
  { value: 'mssql+pymssql', label: 'SQL Server' },
  { value: 'clickhouse+clickhouse_driver', label: 'ClickHouse' },
  { value: 'sqlite', label: 'SQLite' },
]

async function load() {
  loading.value = true
  try {
    const data: DbConfigListResponse = await api.listDbConfigs()
    dbConfigs.value = data.databases || {}
    await dbStore.loadDatabases()
    lastUpdated.value = new Date().toLocaleTimeString()
    dbList.value = Object.entries(dbConfigs.value).map(([alias, cfg]) => ({
      ...cfg,
      alias,
      status: dbStore.connectionStatus[alias] || 'unknown',
    }))
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

function openAdd() {
  dialogMode.value = 'add'
  editAlias.value = ''
  form.value = { alias: '', host: '127.0.0.1', port: 3306, user: 'root', password: '', database: '', dialect: 'mysql+pymysql', pool_size: 5 }
  dialogVisible.value = true
}

function openEdit(alias: string) {
  const cfg = dbConfigs.value[alias]
  if (!cfg) return
  dialogMode.value = 'edit'
  editAlias.value = alias
  form.value = { ...cfg, alias }
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (dialogMode.value === 'add') {
      await api.addDbConfig(form.value)
      ElMessage.success(`数据库 '${form.value.alias}' 已添加`)
    } else {
      const { alias, ...cfg } = form.value
      await api.updateDbConfig(editAlias.value, cfg)
      ElMessage.success(`数据库 '${editAlias.value}' 已更新`)
    }
    dialogVisible.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(`保存失败: ${e.message}`)
  } finally {
    saving.value = false
  }
}

async function remove(alias: string) {
  try {
    await ElMessageBox.confirm(
      `确定要删除数据库 '${alias}' 吗？`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.deleteDbConfig(alias)
    ElMessage.success(`数据库 '${alias}' 已删除`)
    await load()
  } catch { /* 用户取消 */ }
}

async function testConnection(alias: string) {
  testing.value = { ...testing.value, [alias]: true }
  try {
    const result = await api.testDbConfig({ alias })
    dbStore.connectionStatus[alias] = result.success ? 'online' : 'offline'
    if (result.success) {
      ElMessage.success(`'${alias}' 连接成功 🎉`)
    } else {
      ElMessage.error(`'${alias}' 连接失败: ${result.message || ''}`)
    }
    await load()
  } catch (e: any) {
    ElMessage.error(`测试失败: ${e.message}`)
  } finally {
    testing.value = { ...testing.value, [alias]: false }
  }
}

async function testAllConnections() {
  for (const alias of dbList.value.map(d => d.alias)) {
    await testConnection(alias)
  }
}

async function testNewConnection() {
  testing.value = { ...testing.value, [form.value.alias] : true }
  try {
    const result = await api.testDbConfig(form.value)
    if (result.success) {
      ElMessage.success(`'${form.value.alias}' 连接成功 🎉`)
    } else {
      ElMessage.warning(`'${form.value.alias}' 连接失败: ${result.message || ''}，仍可保存`)
    }
  } catch (e: any) {
    ElMessage.warning(`测试失败: ${e.message}，仍可保存`)
  } finally {
    testing.value = { ...testing.value, [form.value.alias] : false }
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <!-- 实时反馈 -->
    <div class="live-bar" v-if="lastUpdated">
      <span class="live-dot"></span>
      <span class="live-text">{{ lastUpdated }} 更新</span>
    </div>

    <!-- 控制栏 -->
    <el-card shadow="never" class="section-card">
      <div class="control-row">
        <div class="control-left">
          <h2 style="margin:0;font-size:16px;display:flex;align-items:center;gap:8px">🗄️ 数据库配置</h2>
        </div>
        <div class="control-right">
          <el-button size="small" :loading="testingAll" @click="testAllConnections" v-if="dbList.length > 0">
            🔌 测试全部
          </el-button>
          <el-button type="primary" size="small" @click="openAdd">
            <el-icon><Plus /></el-icon> 新增数据库
          </el-button>
          <el-button size="small" :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>
    </el-card>

    <!-- 空状态 -->
    <el-card v-if="!loading && dbList.length === 0" shadow="never" style="text-align:center;padding:60px">
      <div style="font-size:48px;margin-bottom:16px">🗄️</div>
      <p style="color:var(--el-text-color-secondary);margin-bottom:16px">暂无数据库配置，点击"新增数据库"开始配置</p>
      <el-button type="primary" @click="openAdd"><el-icon><Plus /></el-icon> 新增数据库</el-button>
    </el-card>

    <!-- 数据库列表 -->
    <div v-else class="db-grid">
      <el-card v-for="db in dbList" :key="db.alias" shadow="never" class="db-card"
        :class="'status-' + (db.status || 'unknown')">
        <div class="db-header">
          <div class="db-icon">{{ db.status === 'online' ? '🟢' : db.status === 'offline' ? '🔴' : '⚪' }}</div>
          <div class="db-name">{{ db.alias }}</div>
          <el-tag :type="db.status === 'online' ? 'success' : db.status === 'offline' ? 'danger' : 'info'" size="small" effect="dark">
            {{ db.status === 'online' ? '在线' : db.status === 'offline' ? '离线' : '未检测' }}
          </el-tag>
        </div>
        <div class="db-details">
          <div class="db-detail"><span>类型</span> {{ db.dialect || '-' }}</div>
          <div class="db-detail"><span>主机</span> {{ db.host }}:{{ db.port }}</div>
          <div class="db-detail"><span>用户</span> {{ db.user }}</div>
          <div class="db-detail"><span>库名</span> {{ db.database || '-' }}</div>
        </div>
        <div class="db-actions">
          <el-button size="small" :loading="testing[db.alias]" @click="testConnection(db.alias)">测试</el-button>
          <el-button size="small" @click="openEdit(db.alias)"><el-icon><Edit /></el-icon></el-button>
          <el-button size="small" type="danger" plain @click="remove(db.alias)"><el-icon><Delete /></el-icon></el-button>
        </div>
      </el-card>
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'add' ? '新增数据库' : '编辑数据库'" width="550px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px" size="small">
        <el-form-item label="别名" required>
          <el-input v-model="form.alias" placeholder="如: mydb, prod" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item label="数据库类型" required>
          <el-select v-model="form.dialect" style="width:100%">
            <el-option v-for="d in dialects" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="16">
            <el-form-item label="主机地址" required>
              <el-input v-model="form.host" placeholder="127.0.0.1" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="端口">
              <el-input-number v-model="form.port" :min="1" :max="65535" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="用户名" required>
              <el-input v-model="form.user" placeholder="root" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="密码">
              <el-input v-model="form.password" type="password" show-password />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="数据库名">
          <el-input v-model="form.database" placeholder="mydb" />
        </el-form-item>
        <el-form-item label="连接池大小">
          <el-input-number v-model="form.pool_size" :min="1" :max="100" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button :loading="testing[form.alias]" @click="testNewConnection" :disabled="!form.alias" v-if="dialogMode === 'add'">
          🔌 测试连接
        </el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.section-card { margin-bottom: 16px; }
.control-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.control-left, .control-right { display: flex; align-items: center; gap: 12px; }

.db-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; }
.db-card { border: 1px solid var(--el-border-color-light); }
.db-card.status-online { border-left: 3px solid #22c55e; }
.db-card.status-offline { border-left: 3px solid #ef4444; }

.db-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.db-icon { font-size: 20px; }
.db-name { font-size: 16px; font-weight: 600; flex: 1; }

.db-details { margin-bottom: 12px; }
.db-detail { display: flex; gap: 8px; padding: 4px 0; font-size: 13px; border-bottom: 1px solid var(--el-border-color-lighter); }
.db-detail span { color: var(--el-text-color-secondary); min-width: 50px; }

.db-actions { display: flex; gap: 8px; }

.live-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-text { font-size: 12px; }
</style>