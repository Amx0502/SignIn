<template>
  <router-view v-if="isLoginPage" />
  <el-container v-else class="app-wrapper">
    <el-aside :width="sidebarCollapsed ? '80px' : '280px'" class="sidebar" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
      <div class="brand">
        <img src="./img/logo.png" class="logo-img" alt="签到" />
        <div v-if="!sidebarCollapsed">
          <h1>签到管理系统</h1>
          <p>Professional Admin Console</p>
        </div>
      </div>
      <div v-if="!sidebarCollapsed" class="sidebar-status">
        <span class="pulse-dot"></span>
        <span>{{ loading ? '正在同步数据' : '服务运行中' }}</span>
      </div>
      <el-menu :default-active="$route.path" router class="sidebar-menu" :collapse="sidebarCollapsed" @select="closeSidebar">
        <el-menu-item v-if="currentUser?.role === 'admin'" index="/users">
          <el-icon><User /></el-icon><span>用户管理</span>
        </el-menu-item>
        <el-sub-menu index="/checkin">
          <template #title>
            <el-icon><img src="./img/xxqd.png" class="menu-custom-icon" alt="签到" /></el-icon>
            <span>小小签到</span>
          </template>
          <el-menu-item index="/overview"><el-icon><Odometer /></el-icon><span>系统概览</span></el-menu-item>
          <el-menu-item index="/accounts"><el-icon><User /></el-icon><span>账号管理</span></el-menu-item>
          <el-menu-item index="/checkin/auto"><el-icon><Timer /></el-icon><span>自动签到</span></el-menu-item>
          <el-menu-item index="/tasks"><el-icon><List /></el-icon><span>任务管理</span></el-menu-item>
          <el-menu-item index="/logs"><el-icon><Document /></el-icon><span>运行日志</span></el-menu-item>
        </el-sub-menu>
      </el-menu>
      <div v-if="!sidebarCollapsed" class="sidebar-footer">
        <span>自动化调度</span>
        <strong>安全 · 稳定 · 高效</strong>
      </div>
    </el-aside>

    <el-container class="main-shell">
      <el-header class="top-header">
        <div class="header-left">
          <el-button class="menu-btn" link :icon="Menu" @click="toggleSidebar" style="margin-right: 12px;">菜单</el-button>
          <div>
            <p class="breadcrumb">后台控制台 / {{ $route.meta.title || '签到管理系统' }}</p>
            <h2>{{ $route.meta.title || '签到管理系统' }}</h2>
          </div>
        </div>
        <el-space wrap class="header-right">
          <span class="header-current-time" aria-label="当前时间" role="timer">
            <span class="header-current-time__indicator"></span>
            <el-icon class="header-current-time__icon"><Clock /></el-icon>
            <span class="header-current-time__content">
              <span class="header-current-time__date">{{ currentTime.slice(0, 10) }}</span>
              <span class="header-current-time__clock">{{ currentTime.slice(11) }}</span>
            </span>
          </span>
          <el-button type="primary" :icon="Refresh" @click="loadAll" :loading="loading">刷新数据</el-button>
          <el-dropdown @command="handleUserCommand">
            <span class="user-info">
              <el-icon><User /></el-icon>
              <span>{{ currentUser?.username || '用户' }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-space>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>

    <div v-if="!sidebarCollapsed && isMobile" class="sidebar-mask" @click="closeSidebar"></div>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Odometer, User, Document, Refresh, Timer, List, Menu, Clock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAppState } from './composables/useAppState'
import { formatCurrentTime } from './utils/currentTime'
import { logoutApi } from './api'

const router = useRouter()
const route = useRoute()

const { loading, loadAll } = useAppState()

const sidebarCollapsed = ref(false)
const isMobile = ref(false)
const currentUser = ref(null)
const currentTime = ref(formatCurrentTime())
let currentTimeTimer = null

const isLoginPage = computed(() => route.path === '/login')

function getUserInfo() {
  const userStr = localStorage.getItem('user')
  if (userStr) {
    try {
      currentUser.value = JSON.parse(userStr)
    } catch {
      currentUser.value = null
    }
  }
}

async function handleUserCommand(command) {
  if (command === 'logout') {
    try {
      await logoutApi()
    } catch {
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('expires_at')
      localStorage.removeItem('user')
      currentUser.value = null
      ElMessage.success('已退出登录')
      router.push('/login')
    }
  }
}

function checkMobile() {
  isMobile.value = window.innerWidth <= 768
  if (isMobile.value) {
    sidebarCollapsed.value = true
  } else {
    sidebarCollapsed.value = false
  }
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function closeSidebar() {
  if (isMobile.value) {
    sidebarCollapsed.value = true
  }
}

onMounted(() => {
  checkMobile()
  getUserInfo()
  currentTimeTimer = window.setInterval(() => {
    currentTime.value = formatCurrentTime()
  }, 1000)
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.clearInterval(currentTimeTimer)
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.app-wrapper { min-height: 100vh; }
.sidebar {
  position: sticky; top: 0; height: 100vh; overflow: hidden auto;
  background: linear-gradient(180deg, #07111f 0%, #0f172a 46%, #111827 100%);
  color: #e5eefc; padding: 22px 14px; box-shadow: 18px 0 45px rgba(15, 23, 42, 0.18); z-index: 20;
  transition: width 0.3s ease;
}
.sidebar.sidebar-collapsed {
  padding: 14px 8px;
}
.sidebar::before { content: ""; position: absolute; inset: 0; background: radial-gradient(circle at 20% 0%, rgba(59, 130, 246, 0.28), transparent 34%); pointer-events: none; }
.brand { position: relative; display: flex; gap: 12px; align-items: center; margin-bottom: 18px; padding: 0 8px; }
.brand-mark { width: 48px; height: 48px; display: grid; place-items: center; border-radius: 16px; background: linear-gradient(135deg, #60a5fa, #2563eb); color: #fff; font-weight: 900; box-shadow: 0 16px 30px rgba(37, 99, 235, 0.35); }
.brand h1 { margin: 0; font-size: 21px; color: #fff; letter-spacing: -0.03em; }
.brand p { margin: 6px 0 0; font-size: 11px; color: #9fb0cf; text-transform: uppercase; letter-spacing: 0.08em; }
.sidebar-status, .sidebar-footer { position: relative; margin: 12px 8px 18px; padding: 12px 14px; border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 16px; background: rgba(255, 255, 255, 0.05); color: #cbd5e1; font-size: 13px; }
.pulse-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #22c55e; margin-right: 8px; box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.12); animation: pulse 1.5s infinite; }
.sidebar-menu { position: relative; border-right: none; background: transparent; }
.sidebar-menu :deep(.el-sub-menu__title), .sidebar-menu :deep(.el-menu-item) { border-radius: 14px; margin: 5px 0; height: 48px; line-height: 48px; color: #dbeafe; transition: all 0.22s ease; }
.sidebar-menu :deep(.el-sub-menu__title:hover), .sidebar-menu :deep(.el-menu-item:hover) { background: rgba(96, 165, 250, 0.14); transform: translateX(3px); }
.sidebar-menu :deep(.el-menu-item.is-active) { background: linear-gradient(90deg, rgba(37, 99, 235, 0.28), rgba(14, 165, 233, 0.12)); box-shadow: inset 3px 0 0 #60a5fa; color: #fff; font-weight: 700; }
.sidebar-menu :deep(.el-sub-menu .el-menu) { background: rgba(255, 255, 255, 0.035); border-radius: 14px; padding: 4px; }
.menu-custom-icon { width: 23px; height: 23px; object-fit: contain; display: block; }
.logo-img { width: 48px; height: 48px; object-fit: contain; display: block; }
.sidebar-footer { position: absolute; left: 14px; right: 14px; bottom: 16px; display: grid; gap: 6px; }
.sidebar-footer strong { color: #fff; }
.main-shell { min-width: 0; }
.top-header { min-height: 76px; display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 0 28px; background: rgba(255, 255, 255, 0.72); backdrop-filter: blur(18px); border-bottom: 1px solid rgba(226, 232, 240, 0.8); position: sticky; top: 0; z-index: 10; }
.header-left { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.menu-btn { display: none; }
.breadcrumb { margin: 0 0 4px; color: #64748b; font-size: 12px; }
.top-header h2 { margin: 0; font-size: 22px; color: #0f172a; letter-spacing: -0.03em; }
.header-current-time {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-height: 42px;
  padding: 6px 14px 6px 11px;
  overflow: hidden;
  color: #1e3a8a;
  white-space: nowrap;
  border: 1px solid rgba(96, 165, 250, 0.42);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(239, 246, 255, 0.96), rgba(219, 234, 254, 0.72)),
    radial-gradient(circle at 100% 0%, rgba(14, 165, 233, 0.2), transparent 58%);
  box-shadow: 0 8px 22px rgba(37, 99, 235, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.9);
}
.header-current-time::after {
  content: "";
  position: absolute;
  width: 34px;
  height: 34px;
  right: -15px;
  top: -18px;
  border-radius: 50%;
  background: rgba(56, 189, 248, 0.2);
}
.header-current-time__indicator {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: #38bdf8;
  box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.14);
  animation: headerTimePulse 2s ease-in-out infinite;
}
.header-current-time__icon {
  width: 25px;
  height: 25px;
  flex: none;
  color: #2563eb;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
}
.header-current-time__content {
  display: grid;
  gap: 1px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.header-current-time__date { color: #64748b; font-size: 10px; font-weight: 650; letter-spacing: 0.06em; }
.header-current-time__clock { color: #1e3a8a; font-size: 15px; font-weight: 800; letter-spacing: 0.04em; }
.user-info { display: flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 8px; cursor: pointer; color: #374151; }
.user-info:hover { background: rgba(0, 0, 0, 0.05); }
.sidebar-mask {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); z-index: 15;
  animation: fadeIn 0.2s ease;
}
@keyframes pulse { 50% { box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); } }
@keyframes headerTimePulse { 50% { opacity: 0.58; box-shadow: 0 0 0 7px rgba(56, 189, 248, 0); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

@media (max-width: 900px) {
  .top-header { padding: 12px 16px; height: auto; flex-wrap: wrap; }
  .header-left { flex-wrap: wrap; }
  .menu-btn { display: block; }
}

@media (max-width: 768px) {
  .top-header { min-height: 64px; padding: 10px 12px; }
  .header-left { flex-direction: row; align-items: center; }
  .top-header h2 { font-size: 18px; }
  .breadcrumb { font-size: 11px; }
  .header-right { margin-top: 8px; }
  .header-current-time { min-height: 38px; padding: 5px 10px 5px 8px; gap: 7px; border-radius: 12px; }
  .header-current-time__icon { width: 22px; height: 22px; }
  .header-current-time__date { font-size: 9px; }
  .header-current-time__clock { font-size: 13px; }
  .sidebar { 
    position: fixed; left: 0; top: 0; z-index: 100; height: 100vh; 
    transition: transform 0.3s ease, width 0.3s ease;
  }
  .sidebar.sidebar-collapsed {
    transform: translateX(-100%);
  }
}

@media (max-width: 480px) {
  .top-header { padding: 8px 10px; }
  .top-header h2 { font-size: 16px; }
  .header-current-time__indicator { display: none; }
}
</style>
