<script setup lang="ts">
/**
 * StatCard — 统计卡片
 * 替代 Dashboard 里 4 个 div.stat-card + div.stat-value + div.stat-label 重复
 * 适配 Bytebase 风格:简约、留白、数值左对齐
 */
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  value: string | number
  label: string
  subtitle?: string
  color?: string              // 数值颜色,默认取语义色
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  icon?: string               // Element Plus icon 组件名,如 'Monitor'
  to?: string                 // 点击跳转路径
  loading?: boolean
  size?: 'sm' | 'md' | 'lg'
}>(), {
  subtitle: '',
  color: '',
  trend: 'neutral',
  trendValue: '',
  icon: '',
  to: '',
  loading: false,
  size: 'md',
})

const emit = defineEmits<{
  click: []
}>()

const sizeClass = computed(() => `stat-card--${props.size}`)

const trendIcon = computed(() => {
  if (props.trend === 'up') return 'el-icon-top-right'
  if (props.trend === 'down') return 'el-icon-bottom-right'
  return ''
})
</script>

<template>
  <div
    class="stat-card"
    :class="[sizeClass, { 'stat-card--clickable': !!to }]"
    @click="emit('click')"
    role="button"
    :tabindex="to ? 0 : -1"
  >
    <div v-if="loading" class="stat-card__loading">
      <div class="skeleton skeleton--value"></div>
      <div class="skeleton skeleton--label"></div>
    </div>
    <template v-else>
      <div class="stat-card__header">
        <span class="stat-card__value" :style="color ? { color } : {}">
          {{ value }}
          <span v-if="trend !== 'neutral'" class="stat-card__trend" :class="`stat-card__trend--${trend}`">
            {{ trendValue }}
          </span>
        </span>
      </div>
      <div class="stat-card__label">{{ label }}</div>
      <div v-if="subtitle" class="stat-card__subtitle">{{ subtitle }}</div>
    </template>
  </div>
</template>

<style scoped>
.stat-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  padding: var(--space-6) var(--space-5);
  cursor: default;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.stat-card--clickable {
  cursor: pointer;
}
.stat-card--clickable:hover {
  border-color: var(--color-brand-200);
  box-shadow: var(--shadow-sm);
}
.stat-card--sm { padding: var(--space-4) var(--space-3); }
.stat-card--lg { padding: var(--space-8) var(--space-6); }

.stat-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}
.stat-card__value {
  font-size: var(--text-3xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.stat-card--sm .stat-card__value { font-size: var(--text-2xl); }
.stat-card--lg .stat-card__value { font-size: var(--text-4xl); }

.stat-card__trend { font-size: var(--text-sm); font-weight: var(--font-normal); margin-left: var(--space-2); }
.stat-card__trend--up { color: var(--color-success-500); }
.stat-card__trend--down { color: var(--color-danger-500); }

.stat-card__label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}
.stat-card__subtitle {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}

/* Skeleton loading */
.stat-card__loading { padding: var(--space-1) 0; }
.skeleton {
  background: var(--color-gray-100);
  border-radius: var(--radius-sm);
  animation: shimmer 1.5s infinite;
}
.skeleton--value { width: 60%; height: 28px; margin-bottom: var(--space-2); }
.skeleton--label { width: 40%; height: 14px; }
@keyframes shimmer {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}
</style>