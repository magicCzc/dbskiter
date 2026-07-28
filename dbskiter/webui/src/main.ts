import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './styles/tokens.css'         // 设计 tokens (CSS 变量)
import './styles/element-theme.css'  // Element Plus 主题映射到 tokens
import './styles/app.css'            // 业务相关全局样式
import App from './App.vue'
import { router } from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')