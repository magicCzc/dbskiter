<script setup lang="ts">
import { ref } from 'vue'
import NavBar from '@/components/NavBar.vue'

const loading = ref(false)
const error = ref('')
</script>

<template>
  <NavBar />
  <div class="container">
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="loading" class="loading">加载中...</div>
    <router-view />
  </div>
  <footer>
    DBSKiter v3.0.43 &middot; 数据库 AIOps 运维助手 &middot;
    <a href="/docs" target="_blank">API 文档</a>
  </footer>
</template>

<style scoped>
footer {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 13px;
  border-top: 1px solid var(--border);
  margin-top: 40px;
}
footer a { color: var(--primary); text-decoration: none; }
</style>