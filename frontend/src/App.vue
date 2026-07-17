<template>
  <el-container class="app-wrapper">
    <el-aside width="260px" class="sidebar">
      <div class="brand">
        <h1>签到管理系统</h1>
        <p>Vue3 + ElementPlus</p>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        class="sidebar-menu"
        background-color="#0f172a"
        text-color="#e5eefc"
        active-text-color="#60a5fa"
      >
        <el-sub-menu index="/checkin">
          <template #title>
            <el-icon><Calendar /></el-icon>
            <span>小小签到</span>
          </template>
          <el-menu-item index="/overview">
            <el-icon><Odometer /></el-icon>
            <span>系统概览</span>
          </el-menu-item>
          <el-menu-item index="/accounts">
            <el-icon><User /></el-icon>
            <span>账号管理</span>
          </el-menu-item>
          <el-menu-item index="/checkin/auto">
            <el-icon><Timer /></el-icon>
            <span>自动签到</span>
          </el-menu-item>
          <el-menu-item index="/logs">
            <el-icon><Document /></el-icon>
            <span>运行日志</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="top-header">
        <h2>{{ $route.meta.title || '签到管理系统' }}</h2>
        <el-space>
          <el-button type="primary" :icon="Refresh" @click="loadAll" :loading="loading">刷新</el-button>
        </el-space>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { Odometer, User, Document, Refresh, Calendar, Timer } from '@element-plus/icons-vue'
import { useAppState } from './composables/useAppState'

const { loading, loadAll } = useAppState()
</script>

<style scoped>
.app-wrapper { min-height: 100vh; }
.sidebar {
  background: linear-gradient(180deg, #0f172a, #111827);
  color: #e5eefc;
  padding: 20px 12px;
}
.brand { margin-bottom: 20px; padding: 0 10px; }
.brand h1 { margin: 0; font-size: 22px; color: #fff; }
.brand p { margin: 8px 0 0; font-size: 12px; color: #9fb0cf; }
.sidebar-menu {
  border-right: none;
  margin-bottom: 20px;
  background: transparent;
}
.sidebar-menu :deep(.el-sub-menu__title),
.sidebar-menu :deep(.el-menu-item) {
  border-radius: 10px;
  margin-bottom: 4px;
  height: 48px;
  line-height: 48px;
  transition: all 0.2s ease;
}
.sidebar-menu :deep(.el-menu-item:hover) {
  background: rgba(96, 165, 250, 0.12) !important;
}
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: rgba(96, 165, 250, 0.15) !important;
  box-shadow: inset 3px 0 0 #60a5fa;
  font-weight: 600;
}
.sidebar-menu :deep(.el-sub-menu .el-menu) {
  background: rgba(255, 255, 255, 0.03) !important;
  border-radius: 10px;
  padding: 4px;
  margin-top: 4px;
}
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(96, 165, 250, 0.1) !important;
}
.top-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(230, 235, 242, 0.8);
  position: sticky;
  top: 0;
  z-index: 10;
}
.top-header h2 { margin: 0; font-size: 20px; color: #1e293b; }
</style>
