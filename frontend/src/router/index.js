import { createRouter, createWebHistory } from 'vue-router'
import Overview from '../views/Overview.vue'
import Accounts from '../views/Accounts.vue'
import Logs from '../views/Logs.vue'
import AutoCheckIn from '../views/AutoCheckIn.vue'
import TaskManagement from '../views/TaskManagement.vue'

const routes = [
  { path: '/', redirect: '/overview' },
  { path: '/overview', name: 'Overview', component: Overview, meta: { title: '系统概览' } },
  { path: '/accounts', name: 'Accounts', component: Accounts, meta: { title: '账号管理' } },
  { path: '/checkin/auto', name: 'AutoCheckIn', component: AutoCheckIn, meta: { title: '自动签到' } },
  { path: '/tasks', name: 'TaskManagement', component: TaskManagement, meta: { title: '任务管理' } },
  { path: '/checkin/normal', redirect: '/checkin/auto' },
  { path: '/checkin/image', redirect: '/checkin/auto' },
  { path: '/logs', name: 'Logs', component: Logs, meta: { title: '运行日志' } }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
