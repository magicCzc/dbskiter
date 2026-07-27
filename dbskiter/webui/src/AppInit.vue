<script setup lang="ts">
import { onMounted } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { useMessage, useNotification } from 'naive-ui'
import { useI18n } from 'vue-i18n'

const dbStore = useDatabaseStore()
const message = useMessage()
const notification = useNotification()
const { t } = useI18n()

onMounted(() => {
  dbStore.loadDatabases()
})

defineExpose({ message, notification, t })
</script>

<template>
  <div></div>
</template>