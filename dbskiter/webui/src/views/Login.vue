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
const isDemo = ref(false)

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
  isDemo.value = true
  loading.value = true
  try {
    await auth.login('demo', 'demo')
    ElMessage.success('🎮 欢迎体验演示模式！所有数据为模拟数据')
    router.push('/')
  } catch {
    ElMessage.info('演示模式已激活，所有数据为模拟数据')
    auth.demoLogin()
    router.push('/')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card" :class="{ 'demo-mode': isDemo }">
      <div class="login-header">
        <div class="login-logo">🗄️</div>
        <h1>DBSKiter</h1>
        <p class="login-subtitle">数据库 AIOps 运维助手</p>
      </div>

      <el-form @submit.prevent="submit" class="login-form">
        <el-input
          v-model="username"
          placeholder="用户名"
          size="large"
          style="margin-bottom:16px"
          autofocus
        />
        <el-input
          v-model="password"
          type="password"
          placeholder="密码"
          size="large"
          style="margin-bottom:16px"
          show-password
        />
        <el-input
          v-if="!isLogin"
          v-model="email"
          placeholder="邮箱（选填）"
          size="large"
          style="margin-bottom:16px"
        />
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          style="width:100%;margin-bottom:12px"
          @click="submit"
        >
          {{ isLogin ? '登 录' : '注 册' }}
        </el-button>
        <div class="login-switch">
          <el-button text @click="isLogin = !isLogin">
            {{ isLogin ? '没有账号？去注册' : '已有账号？去登录' }}
          </el-button>
        </div>
      </el-form>

      <div class="demo-divider">
        <span class="demo-divider-line"></span>
        <span class="demo-divider-text">体验</span>
        <span class="demo-divider-line"></span>
      </div>

      <el-button
        size="large"
        style="width:100%;margin-bottom:12px"
        :loading="loading"
        @click="demoLogin"
      >
        🎮 演示模式（无需账号）
      </el-button>

      <div class="login-footer">
        <span class="login-hint">默认管理员: admin / admin123</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--el-bg-color-page);
}
.login-card {
  width: 400px;
  padding: 40px;
  background: var(--el-bg-color);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.08);
  border: 1px solid var(--el-border-color-light);
}
.login-header {
  text-align: center;
  margin-bottom: 32px;
}
.login-logo {
  font-size: 48px;
  margin-bottom: 12px;
}
.login-header h1 {
  margin: 0;
  font-size: 24px;
  color: var(--el-color-primary);
}
.login-subtitle {
  margin: 4px 0 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
.login-switch {
  text-align: center;
}
.login-footer {
  text-align: center;
  margin-top: 24px;
}
.login-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.demo-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 20px 0 16px;
}
.demo-divider-line {
  flex: 1;
  height: 1px;
  background: var(--el-border-color-light);
}
.demo-divider-text {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.demo-mode {
  border-color: var(--el-color-warning) !important;
}
</style>