<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api'
import { ElMessage } from 'element-plus'
import type { UserInfo } from '@/types'
import SectionCard from '@/components/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const auth = useAuthStore()
const users = ref<UserInfo[]>([])
const loading = ref(false)
const lastUpdated = ref('')

async function load() {
  loading.value = true
  try {
    const data = await api.listUsers()
    if (data.success) {
      users.value = data.users || []
      lastUpdated.value = new Date().toLocaleTimeString()
    }
  } catch (e: any) {
    ElMessage.error(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

async function changeRole(user: UserInfo, role: string) {
  try {
    const data = await api.updateUserRole(user.id, role)
    if (data.success) {
      ElMessage.success(data.message)
      await load()
    } else {
      ElMessage.error('操作失败')
    }
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

async function toggleUser(user: UserInfo) {
  try {
    const data = await api.toggleUser(user.id)
    if (data.success) {
      ElMessage.success(data.message)
      await load()
    }
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e.message}`)
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <SectionCard padding>
      <div class="users-controls">
        <div class="users-controls__left">
          <h2 class="users-title">用户管理</h2>
        </div>
        <div class="users-controls__right">
          <span v-if="lastUpdated" class="users-updated">{{ lastUpdated }} 更新</span>
          <el-button size="small" :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>
    </SectionCard>

    <SectionCard padding>
      <el-table :data="users" v-loading="loading" stripe style="width:100%">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="username" label="用户名" width="150">
          <template #default="{row}">
            <span class="user-name">{{ row.username }}</span>
            <StatusTag v-if="row.username === 'admin'" status="admin" label="管理员" />
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" width="200" />
        <el-table-column prop="role" label="角色" width="150">
          <template #default="{row}">
            <el-select :model-value="row.role" size="small" style="width:100px" @change="(v: string) => changeRole(row, v)" :disabled="row.username === 'admin'">
              <el-option label="管理员" value="admin" />
              <el-option label="编辑者" value="editor" />
              <el-option label="查看者" value="viewer" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{row}">
            <StatusTag :status="row.is_active ? 'active' : 'inactive'" :label="row.is_active ? '正常' : '已禁用'" />
          </template>
        </el-table-column>
        <el-table-column prop="last_login" label="最后登录" width="180">
          <template #default="{row}">{{ row.last_login ? row.last_login.replace('T', ' ').substring(0, 19) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{row}">{{ row.created_at ? row.created_at.replace('T', ' ').substring(0, 19) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{row}">
            <el-button v-if="row.username !== 'admin'" size="small" :type="row.is_active ? 'warning' : 'success'" plain @click="toggleUser(row)">
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }
.users-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.users-controls__left, .users-controls__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.users-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}
.users-updated {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.user-name {
  font-weight: var(--font-semibold);
  margin-right: var(--space-1);
}
</style>