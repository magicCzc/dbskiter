import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getString, setString, remove } from '@/utils/storage'

const API_BASE = '/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getString('token'))
  const username = ref(getString('username'))
  const role = ref(getString('role'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')
  const isEditor = computed(() => role.value === 'admin' || role.value === 'editor')

  function _saveAuth(data: { access_token: string; username: string; role: string }) {
    token.value = data.access_token
    username.value = data.username
    role.value = data.role
    setString('token', data.access_token)
    setString('username', data.username)
    setString('role', data.role)
  }

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
      _saveAuth(await resp.json())
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
    _saveAuth(await resp.json())
    return true
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    remove('token')
    remove('username')
    remove('role')
  }

  function demoLogin() {
    _saveAuth({ access_token: 'demo-token', username: 'demo', role: 'admin' })
  }

  return { token, username, role, isLoggedIn, isAdmin, isEditor, login, register, logout, demoLogin }
})