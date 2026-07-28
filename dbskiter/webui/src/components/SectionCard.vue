<script setup lang="ts">
/**
 * SectionCard — 带标题的 el-card 封装
 * 替代 17 个 view 中 <el-card class="section-card"> + <template #header> 的重复模式
 */
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  title?: string
  subtitle?: string
  variant?: 'default' | 'compact'
  padding?: boolean
}>(), {
  title: '',
  subtitle: '',
  variant: 'default',
  padding: true,
})
</script>

<template>
  <el-card
    shadow="never"
    class="section-card"
    :body-style="padding ? { padding: variant === 'compact' ? 'var(--space-3) var(--space-4)' : 'var(--space-5)' } : { padding: 0 }"
  >
    <template #header v-if="title || $slots.header">
      <div class="section-card__header">
        <div class="section-card__header-left">
          <span class="section-card__title">{{ title }}</span>
          <span class="section-card__subtitle" v-if="subtitle">{{ subtitle }}</span>
        </div>
        <div class="section-card__header-right" v-if="$slots.actions">
          <slot name="actions" />
        </div>
        <slot name="header" />
      </div>
    </template>
    <slot />
  </el-card>
</template>

<style scoped>
.section-card {
  margin-bottom: var(--space-5);
  border-radius: var(--radius-lg) !important;
  border: 1px solid var(--border-default) !important;
  overflow: hidden;
  transition: box-shadow var(--transition-normal);
}
.section-card:hover { box-shadow: var(--shadow-sm); }
.section-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.section-card__header-left {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}
.section-card__title {
  font-weight: var(--font-semibold);
  font-size: var(--text-md);
  color: var(--text-primary);
}
.section-card__subtitle {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.section-card__header-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}
</style>