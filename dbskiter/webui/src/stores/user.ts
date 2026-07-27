import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useUserStore = defineStore('user', () => {
  const isDark = ref(localStorage.getItem('dbskiter-theme') === 'dark')
  const version = ref('3.0.43')
  const language = ref(localStorage.getItem('dbskiter-lang') || 'zh-CN')

  function toggleTheme() {
    isDark.value = !isDark.value
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
    localStorage.setItem('dbskiter-theme', isDark.value ? 'dark' : 'light')
  }

  function setLanguage(lang: string) {
    language.value = lang
    localStorage.setItem('dbskiter-lang', lang)
  }

  // 初始化主题
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  }

  return { isDark, version, language, toggleTheme, setLanguage }
})