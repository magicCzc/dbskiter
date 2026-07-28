<script setup lang="ts">
/**
 * DemoBanner — 演示模式小标签
 * 替代当前固定在顶部的横幅,改为侧边栏底部的小标签,不抢眼
 */
import { IS_DEMO } from '@/mock'
</script>

<template>
  <div v-if="IS_DEMO" class="demo-banner">
    <span class="demo-banner__dot"></span>
    <span class="demo-banner__text">演示模式</span>
  </div>
</template>

<style scoped>
.demo-banner {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-xs);
  color: var(--text-on-dark-mute);
  cursor: default;
  border-top: 1px solid rgba(255,255,255,0.08);
}
.demo-banner__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-warning-500);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.demo-banner__text {
  font-weight: var(--font-medium);
}
</style>