import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getString, setString } from '@/utils/storage'

export const useUserStore = defineStore('user', () => {
  const isDark = ref(getString('theme') === 'dark')
  const version = ref('3.0.45')
  const language = ref(getString('lang', 'zh-CN'))

  function toggleTheme() {
    isDark.value = !isDark.value
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
    setString('theme', isDark.value ? 'dark' : 'light')
  }

  function setLanguage(lang: string) {
    language.value = lang
    setString('lang', lang)
  }

  // 初始化主题
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  }

  return { isDark, version, language, toggleTheme, setLanguage }
})