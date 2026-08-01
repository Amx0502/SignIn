import { createRouter, createWebHistory } from 'vue-router'
import Overview from '../views/Overview.vue'
import Accounts from '../views/Accounts.vue'
import Logs from '../views/Logs.vue'
import AutoCheckIn from '../views/AutoCheckIn.vue'
import TaskManagement from '../views/TaskManagement.vue'
import Login from '../views/Login.vue'
import ClassCubeOverview from '../views/ClassCubeOverview.vue'
import ClassCubeAccounts from '../views/ClassCubeAccounts.vue'
import ClassCubeTasks from '../views/ClassCubeTasks.vue'
import ClassCubeRuns from '../views/ClassCubeRuns.vue'
import ClassCubeLogs from '../views/ClassCubeLogs.vue'
import UserManagement from '../views/UserManagement.vue'
import ChangePassword from '../views/ChangePassword.vue'
import MenuManagement from '../views/MenuManagement.vue'
import NoAvailableMenus from '../views/NoAvailableMenus.vue'
import {
  ensureMenuCatalog,
  firstAllowedPath,
  isCurrentMenuVisible,
} from '../menu/menuStore.js'

const routes = [
  { path: '/login', name: 'Login', component: Login, meta: { title: '登录' } },
  { path: '/change-password', name: 'ChangePassword', component: ChangePassword, meta: { title: '修改密码', requiresAuth: true } },
  { path: '/users', name: 'UserManagement', component: UserManagement, meta: { title: '用户管理', requiresAuth: true, requiresAdmin: true } },
  { path: '/menu-management', name: 'MenuManagement', component: MenuManagement, meta: { title: '菜单管理', parentTitle: '系统设置', requiresAuth: true, requiresAdmin: true } },
  { path: '/no-access', name: 'NoAvailableMenus', component: NoAvailableMenus, meta: { title: '暂无可用功能', requiresAuth: true } },
  { path: '/', redirect: '/overview' },
  { path: '/overview', name: 'Overview', component: Overview, meta: { title: '系统概览', parentTitle: '小小签到', requiresAuth: true, menuKey: 'xxqd.overview' } },
  { path: '/accounts', name: 'Accounts', component: Accounts, meta: { title: '账号管理', parentTitle: '小小签到', requiresAuth: true, menuKey: 'xxqd.accounts' } },
  { path: '/checkin/auto', name: 'AutoCheckIn', component: AutoCheckIn, meta: { title: '自动签到', parentTitle: '小小签到', requiresAuth: true, menuKey: 'xxqd.auto' } },
  { path: '/tasks', name: 'TaskManagement', component: TaskManagement, meta: { title: '任务管理', parentTitle: '小小签到', requiresAuth: true, menuKey: 'xxqd.tasks' } },
  { path: '/checkin/normal', redirect: '/checkin/auto' },
  { path: '/checkin/image', redirect: '/checkin/auto' },
  { path: '/logs', name: 'Logs', component: Logs, meta: { title: '运行日志', parentTitle: '小小签到', requiresAuth: true, menuKey: 'xxqd.logs' } },
  { path: '/class-cube', redirect: '/class-cube/overview' },
  { path: '/class-cube/overview', name: 'ClassCubeOverview', component: ClassCubeOverview, meta: { title: '系统概览', parentTitle: '班级魔方', requiresAuth: true, menuKey: 'class_cube.overview' } },
  { path: '/class-cube/accounts', name: 'ClassCubeAccounts', component: ClassCubeAccounts, meta: { title: '账号管理', parentTitle: '班级魔方', requiresAuth: true, menuKey: 'class_cube.accounts' } },
  { path: '/class-cube/tasks', name: 'ClassCubeTasks', component: ClassCubeTasks, meta: { title: '自动任务', parentTitle: '班级魔方', requiresAuth: true, menuKey: 'class_cube.tasks' } },
  { path: '/class-cube/runs', name: 'ClassCubeRuns', component: ClassCubeRuns, meta: { title: '运行记录', parentTitle: '班级魔方', requiresAuth: true, menuKey: 'class_cube.runs' } },
  { path: '/class-cube/logs', name: 'ClassCubeLogs', component: ClassCubeLogs, meta: { title: '魔方日志', parentTitle: '班级魔方', requiresAuth: true, menuKey: 'class_cube.logs' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('access_token')
  const expiresAt = localStorage.getItem('expires_at')
  let user = null
  try {
    user = JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    user = null
  }
  
  const isLoggedIn = token && expiresAt && new Date(expiresAt) > new Date()
  
  if (to.meta.requiresAuth && !isLoggedIn) {
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if (to.meta.requiresAdmin && user?.role !== 'admin') {
    try { await ensureMenuCatalog() } catch {}
    next(firstAllowedPath(user))
  } else if (to.path === '/login' && isLoggedIn) {
    if (user?.role === 'admin') return next('/overview')
    try { await ensureMenuCatalog() } catch {}
    next(firstAllowedPath(user))
  } else if (to.meta.menuKey && user?.role !== 'admin') {
    try {
      await ensureMenuCatalog()
    } catch {
      if (!isCurrentMenuVisible(to.meta.menuKey, user)) {
        return next('/no-access')
      }
    }
    if (!isCurrentMenuVisible(to.meta.menuKey, user)) {
      return next(firstAllowedPath(user))
    }
    next()
  } else {
    next()
  }
})

export default router
