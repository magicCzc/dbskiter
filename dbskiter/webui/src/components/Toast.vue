<script setup lang="ts">
import { ref, provide } from 'vue'

export type ToastType = 'info' | 'success' | 'error'

export interface Toast {
  id: number
  message: string
  type: ToastType
}

const toasts = ref<Toast[]>([])
let nextId = 0

function addToast(message: string, type: ToastType = 'info', duration = 4000) {
  const id = nextId++
  toasts.value.push({ id, message, type })
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, duration)
}

function removeToast(id: number) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

provide('toast', addToast)
</script>

<template>
  <div class="toast-container">
    <div v-for="t in toasts" :key="t.id" :class="'toast toast-' + t.type" @click="removeToast(t.id)">
      <span>{{ t.type === 'success' ? '✓' : t.type === 'error' ? '✕' : 'ℹ' }}</span>
      <span>{{ t.message }}</span>
    </div>
  </div>
</template>