<script setup lang="ts">
import NavBar from '@/components/NavBar.vue'
import Toast from '@/components/Toast.vue'
</script>

<template>
  <NavBar />
  <Toast />
  <main class="container">
    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </main>
  <footer>
    <span>DBSKiter v3.0.43</span>
    <span class="sep">·</span>
    <span>数据库 AIOps 运维助手</span>
    <span class="sep">·</span>
    <a href="/docs" target="_blank">API 文档</a>
    <span class="sep">·</span>
    <a href="https://github.com/magicCzc/dbskiter" target="_blank">GitHub</a>
  </footer>
</template>

<style scoped>
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }
footer {
  text-align: center; padding: 24px; color: var(--text-secondary);
  font-size: 13px; border-top: 1px solid var(--border); margin-top: 40px;
}
footer a { color: var(--primary); text-decoration: none; }
.sep { margin: 0 8px; color: var(--border); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>