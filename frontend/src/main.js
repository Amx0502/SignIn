import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import './style.css'
import { mountAppWhenRouterReady } from './appBootstrap.js'

const app = createApp(App)
app.use(router)
void mountAppWhenRouterReady({ app, router, root: '#app' })
