<script setup lang="ts">
/**
 * EmptyState — 空数据占位
 * 统一 19 个 view 的"暂无数据"样式
 */
withDefaults(defineProps<{
  title?: string
  description?: string
  icon?: string
  size?: 'sm' | 'md' | 'lg'
}>(), {
  title: '暂无数据',
  description: '',
  icon: 'el-icon-document-copy',
  size: 'md',
})
</script>

<template>
  <div class="empty-state" :class="`empty-state--${size}`">
    <el-icon :size="size === 'sm' ? 32 : size === 'lg' ? 64 : 48" class="empty-state__icon" color="var(--text-tertiary)">
      <component :is="icon" />
    </el-icon>
    <h4 class="empty-state__title">{{ title }}</h4>
    <p v-if="description" class="empty-state__desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty-state__actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--space-16) var(--space-4);
}
.empty-state--sm { padding: var(--space-8) var(--space-4); }
.empty-state--lg { padding: var(--space-20) var(--space-4); }
.empty-state__icon { margin-bottom: var(--space-4); }
.empty-state__title {
  font-size: var(--text-lg);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
}
.empty-state__desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin: 0;
  max-width: 360px;
}
.empty-state__actions { margin-top: var(--space-4); }
</style>