import { createRouter, createWebHistory } from 'vue-router'
import Overview from '../views/Overview.vue'
import Accounts from '../views/Accounts.vue'
import Logs from '../views/Logs.vue'
import AutoCheckIn from '../views/AutoCheckIn.vue'
import TaskManagement from '../views/TaskManagement.vue'
import Login from '../views/Login.vue'

const routes = [
  { path: '/login', name: 'Login', component: Login, meta: { title: '登录' } },
  { path: '/', redirect: '/overview' },
  { path: '/overview', name: 'Overview', component: Overview, meta: { title: '系统概览', requiresAuth: true } },
  { path: '/accounts', name: 'Accounts', component: Accounts, meta: { title: '账号管理', requiresAuth: true } },
  { path: '/checkin/auto', name: 'AutoCheckIn', component: AutoCheckIn, meta: { title: '自动签到', requiresAuth: true } },
  { path: '/tasks', name: 'TaskManagement', component: TaskManagement, meta: { title: '任务管理', requiresAuth: true } },
  { path: '/checkin/normal', redirect: '/checkin/auto' },
  { path: '/checkin/image', redirect: '/checkin/auto' },
  { path: '/logs', name: 'Logs', component: Logs, meta: { title: '运行日志', requiresAuth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  const expiresAt = localStorage.getItem('expires_at')
  
  const isLoggedIn = token && expiresAt && new Date(expiresAt) > new Date()
  
  if (to.meta.requiresAuth && !isLoggedIn) {
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if (to.path === '/login' && isLoggedIn) {
    next({ path: '/' })
  } else {
    next()
  }
})

export default router
