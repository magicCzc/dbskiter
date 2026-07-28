import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = '/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('dbskiter-token') || '')
  const username = ref(localStorage.getItem('dbskiter-username') || '')
  const role = ref(localStorage.getItem('dbskiter-role') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')
  const isEditor = computed(() => role.value === 'admin' || role.value === 'editor')

  async function login(user: string, pass: string): Promise<boolean> {
    try {
      const resp = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: user, password: pass }),
      })
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || '登录失败')
      }
      const data = await resp.json()
      token.value = data.access_token
      username.value = data.username
      role.value = data.role
      localStorage.setItem('dbskiter-token', data.access_token)
      localStorage.setItem('dbskiter-username', data.username)
      localStorage.setItem('dbskiter-role', data.role)
      return true
    } catch (e: any) {
      throw e
    }
  }

  async function register(user: string, pass: string, email = ''): Promise<boolean> {
    const resp = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pass, email }),
    })
    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || '注册失败')
    }
    const data = await resp.json()
    token.value = data.access_token
    username.value = data.username
    role.value = data.role
    localStorage.setItem('dbskiter-token', data.access_token)
    localStorage.setItem('dbskiter-username', data.username)
    localStorage.setItem('dbskiter-role', data.role)
    return true
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('dbskiter-token')
    localStorage.removeItem('dbskiter-username')
    localStorage.removeItem('dbskiter-role')
  }

  function demoLogin() {
    token.value = 'demo-token'
    username.value = 'demo'
    role.value = 'admin'
    localStorage.setItem('dbskiter-token', 'demo-token')
    localStorage.setItem('dbskiter-username', 'demo')
    localStorage.setItem('dbskiter-role', 'admin')
  }

  return { token, username, role, isLoggedIn, isAdmin, isEditor, login, register, logout, demoLogin }
})