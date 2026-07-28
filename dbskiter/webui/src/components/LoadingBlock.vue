<script setup lang="ts">
/**
 * LoadingBlock — 加载占位
 * 用于页面/区块正在加载时的骨架屏
 */
withDefaults(defineProps<{
  type?: 'card' | 'table' | 'chart' | 'text'
  rows?: number
}>(), {
  type: 'card',
  rows: 3,
})
</script>

<template>
  <div class="loading-block" :class="`loading-block--${type}`">
    <template v-if="type === 'card'">
      <div class="skeleton skeleton--card" v-for="i in 3" :key="i" />
    </template>
    <template v-else-if="type === 'table'">
      <div class="skeleton skeleton--table-row" v-for="i in rows" :key="i" />
    </template>
    <template v-else-if="type === 'chart'">
      <div class="skeleton skeleton--chart" />
    </template>
    <template v-else>
      <div class="skeleton skeleton--text" v-for="i in rows" :key="i" />
    </template>
  </div>
</template>

<style scoped>
.loading-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4) 0;
}
.skeleton {
  background: linear-gradient(90deg, var(--color-gray-100) 25%, var(--color-gray-200) 50%, var(--color-gray-100) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}
.skeleton--card { height: 100px; }
.skeleton--table-row { height: 40px; }
.skeleton--chart { height: 200px; }
.skeleton--text { height: 14px; width: 60%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>