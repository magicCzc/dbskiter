import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'

export const useDatabaseStore = defineStore('database', () => {
  const databases = ref<string[]>(['default'])
  const current = ref(localStorage.getItem('dbskiter-db') || 'default')
  const connectionStatus = ref<Record<string, 'unknown' | 'online' | 'offline'>>({})
  const loading = ref(false)

  function setCurrent(db: string) {
    current.value = db
    localStorage.setItem('dbskiter-db', db)
  }

  async function loadDatabases() {
    loading.value = true
    try {
      const data = await api.databases()
      if (data.databases?.length) {
        databases.value = data.databases
        if (!databases.value.includes(current.value)) {
          setCurrent(databases.value[0])
        }
      }
    } catch { /* 静默 */ }
    finally { loading.value = false }
  }

  async function testConnection(db: string) {
    connectionStatus.value[db] = 'unknown'
    try {
      const resp = await fetch(`/api/diagnose/connection?database=${encodeURIComponent(db)}`)
      const data = await resp.json()
      connectionStatus.value[db] = data.success ? 'online' : 'offline'
      return data.success
    } catch {
      connectionStatus.value[db] = 'offline'
      return false
    }
  }

  return {
    databases, current, connectionStatus, loading,
    setCurrent, loadDatabases, testConnection,
  }
})