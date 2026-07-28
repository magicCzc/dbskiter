import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import ElementPlus from 'unplugin-element-plus/vite'

export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需加载
    Components({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
    // Element Plus 样式按需加载
    ElementPlus({}),
  ],
  root: '.',
  base: process.env.VITE_DEMO_MODE ? '/dbskiter/ui/' : '/ui/',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: resolve(__dirname, '..', 'web', 'static'),
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          echarts: ['echarts', 'vue-echarts', 'zrender'],
        },
      },
    },
  },
})