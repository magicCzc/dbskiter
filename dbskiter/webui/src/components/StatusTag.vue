<script setup lang="ts">
/**
 * StatusTag — 状态标签
 * 统一 19 个 view 里散落的 <el-tag> 用法
 * 常用: health/ok/warning/critical/danger/info
 */
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  status: string
  label?: string
  dot?: boolean
  size?: 'small' | 'default' | 'large'
}>(), {
  label: '',
  dot: true,
  size: 'small',
})

const colorMap: Record<string, string> = {
  healthy: 'success',
  ok: 'success',
  success: 'success',
  warning: 'warning',
  warn: 'warning',
  critical: 'danger',
  danger: 'danger',
  error: 'danger',
  fatal: 'danger',
  offline: 'info',
  disabled: 'info',
  info: 'info',
  pending: 'info',
  running: 'primary',
  active: 'success',
  inactive: 'info',
  open: 'warning',
  acknowledged: 'warning',
  resolved: 'success',
  true: 'success',
  false: 'info',
  yes: 'success',
  no: 'info',
  enabled: 'success',
  admin: 'danger',
  editor: 'warning',
  viewer: 'info',
}

const normalized = computed(() => {
  const key = props.status?.toLowerCase() || ''
  return {
    type: colorMap[key] as 'success' | 'warning' | 'danger' | 'info' | 'primary' | undefined,
    display: props.label || key,
  }
})
</script>

<template>
  <el-tag
    :type="normalized.type"
    :size="size"
    class="status-tag"
    :class="{ 'status-tag--dot': dot }"
    effect="plain"
  >
    <span v-if="dot" class="status-tag__dot" :style="{ background: `var(--color-${normalized.type || 'info'}-500)` }" />
    {{ normalized.display }}
  </el-tag>
</template>

<style scoped>
.status-tag {
  border-radius: var(--radius-sm);
  font-weight: var(--font-medium);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}
.status-tag--dot .status-tag__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}
</style>