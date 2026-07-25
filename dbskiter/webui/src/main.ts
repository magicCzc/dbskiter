import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { routes } from './router'
import './style.css'

const router = createRouter({
  history: createWebHistory('/ui/'),
  routes,
})

createApp(App).use(router).mount('#app')