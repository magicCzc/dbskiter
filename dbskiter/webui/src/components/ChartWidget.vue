<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

const props = defineProps<{
  type: 'doughnut' | 'line'
  data: any
  options?: any
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
let chartInstance: Chart | null = null

function renderChart() {
  if (!canvasRef.value) return
  if (chartInstance) chartInstance.destroy()
  chartInstance = new Chart(canvasRef.value, {
    type: props.type,
    data: props.data,
    options: props.options || { responsive: true, maintainAspectRatio: false },
  })
}

watch(() => props.data, renderChart, { deep: true })

function initChart() {
  if (canvasRef.value) renderChart()
}

defineExpose({ initChart })
</script>

<template>
  <div class="chart-wrapper">
    <canvas ref="canvasRef" @vue:mounted="initChart"></canvas>
  </div>
</template>

<style scoped>
.chart-wrapper { position: relative; width: 100%; height: 100%; min-height: 200px; }
</style>