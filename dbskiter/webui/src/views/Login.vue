<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const auth = useAuthStore()
const isLogin = ref(true)
const username = ref('')
const password = ref('')
const email = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    if (isLogin.value) {
      await auth.login(username.value, password.value)
      ElMessage.success(`欢迎回来，${auth.username}`)
    } else {
      await auth.register(username.value, password.value, email.value)
      ElMessage.success('注册成功')
    }
    router.push('/')
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    loading.value = false
  }
}

async function demoLogin() {
  loading.value = true
  try {
    await auth.login('demo', 'demo')
    ElMessage.success('欢迎体验演示模式')
    router.push('/')
  } catch {
    ElMessage.info('演示模式已激活')
    auth.demoLogin()
    router.push('/')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <svg class="login-logo" viewBox="0 0 24 24" fill="none" width="40" height="40">
          <rect x="3" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.35"/>
          <rect x="14" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55"/>
          <rect x="3" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55"/>
          <rect x="14" y="14" width="7" height="7" rx="1.5" fill="currentColor"/>
        </svg>
        <h1 class="login-title">DBSKiter</h1>
        <p class="login-subtitle">数据库运维管理平台</p>
      </div>

      <el-form @submit.prevent="submit" class="login-form">
        <el-input
          v-model="username"
          placeholder="用户名"
          size="large"
          class="login-input"
          autofocus
        />
        <el-input
          v-model="password"
          type="password"
          placeholder="密码"
          size="large"
          class="login-input"
          show-password
        />
        <el-input
          v-if="!isLogin"
          v-model="email"
          placeholder="邮箱（选填）"
          size="large"
          class="login-input"
        />
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="login-btn"
          @click="submit"
        >
          {{ isLogin ? '登录' : '注册' }}
        </el-button>
        <div class="login-switch">
          <el-button text @click="isLogin = !isLogin">
            {{ isLogin ? '没有账号？去注册' : '已有账号？去登录' }}
          </el-button>
        </div>
      </el-form>

      <div class="login-divider">
        <span class="login-divider-line"></span>
        <span class="login-divider-text">快速体验</span>
        <span class="login-divider-line"></span>
      </div>

      <el-button
        size="large"
        class="login-btn login-btn--demo"
        :loading="loading"
        @click="demoLogin"
      >
        演示模式（无需账号）
      </el-button>

      <p class="login-hint">默认管理员: admin / admin123</p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--bg-page);
}
.login-card {
  width: 400px;
  padding: var(--space-10);
  background: var(--bg-elevated);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-default);
}
.login-header {
  text-align: center;
  margin-bottom: var(--space-8);
}
.login-logo {
  color: var(--color-brand-500);
  margin-bottom: var(--space-4);
}
.login-title {
  margin: 0;
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: -0.3px;
}
.login-subtitle {
  margin: var(--space-1) 0 0;
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}
.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.login-input {
  --el-input-border-radius: var(--radius-md);
}
.login-btn {
  width: 100%;
  margin-top: var(--space-1);
}
.login-btn--demo {
  margin-top: 0;
  --el-button-bg-color: var(--color-gray-50);
  --el-button-border-color: var(--border-default);
  --el-button-text-color: var(--text-secondary);
  --el-button-hover-bg-color: var(--color-gray-100);
  --el-button-hover-border-color: var(--border-strong);
}
.login-switch {
  text-align: center;
  margin-top: var(--space-2);
}
.login-divider {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin: var(--space-6) 0 var(--space-4);
}
.login-divider-line {
  flex: 1;
  height: 1px;
  background: var(--border-default);
}
.login-divider-text {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.login-hint {
  text-align: center;
  margin: var(--space-4) 0 0;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
</style>