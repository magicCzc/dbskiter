import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import ElementPlus from 'unplugin-element-plus/vite'

export default defineConfig(({ mode }) => {
  // 显式加载所有 VITE_* 环境变量（包括 process.env 里的）
  const env = loadEnv(mode, process.cwd(), '')
  const isDemo = env.VITE_DEMO_MODE === 'true' || process.env.VITE_DEMO_MODE === 'true'

  return {
    define: {
      // 强制把 import.meta.env.VITE_DEMO_MODE 注入为字符串，
      // 避免被 vite 当成 undefined 而被 tree-shake 掉 mock 代码
      'import.meta.env.VITE_DEMO_MODE': JSON.stringify(isDemo ? 'true' : 'false'),
    },
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
    base: isDemo ? '/dbskiter/ui/' : '/ui/',
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
  }
})