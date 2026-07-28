<script setup lang="ts">
/**
 * PageHeader — 页面标题区
 * 替代 19 个 view 里各自实现的 <div class="page"> 标题逻辑
 * 左侧:标题 + 面包屑 + 副标题; 右侧:插槽用于刷新/操作按钮
 */
withDefaults(defineProps<{
  title: string
  subtitle?: string
  breadcrumb?: { label: string; to?: string }[]
  loading?: boolean
}>(), {
  subtitle: '',
  breadcrumb: () => [],
  loading: false,
})
</script>

<template>
  <div class="page-header">
    <div class="page-header__left">
      <div class="page-header__breadcrumb" v-if="breadcrumb.length > 0">
        <template v-for="(cr, i) in breadcrumb" :key="i">
          <span v-if="i > 0" class="page-header__sep">/</span>
          <router-link v-if="cr.to" :to="cr.to" class="page-header__crumb">
            {{ cr.label }}
          </router-link>
          <span v-else class="page-header__crumb page-header__crumb--current">
            {{ cr.label }}
          </span>
        </template>
      </div>
      <h1 class="page-header__title">{{ title }}</h1>
      <p v-if="subtitle" class="page-header__subtitle">{{ subtitle }}</p>
    </div>
    <div class="page-header__right" v-if="$slots.default">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-6);
  gap: var(--space-4);
}
.page-header__left { flex: 1; min-width: 0; }
.page-header__right { flex-shrink: 0; display: flex; align-items: center; gap: var(--space-2); }

.page-header__breadcrumb {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-bottom: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.page-header__sep { color: var(--border-strong); }
.page-header__crumb { color: var(--text-tertiary); text-decoration: none; }
.page-header__crumb--current { color: var(--text-secondary); font-weight: var(--font-medium); }
.page-header__crumb:hover { color: var(--text-link); }

.page-header__title {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
  line-height: 1.3;
}
.page-header__subtitle {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin: var(--space-1) 0 0;
}
</style>