<template>
  <router-view v-if="isLoginPage" />
  <el-container v-else class="app-wrapper">
    <el-aside :width="sidebarCollapsed ? '80px' : '280px'" class="sidebar" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
      <div class="brand" role="button" tabindex="0" aria-label="打开综合总览" @click="router.push('/dashboard')" @keydown.enter="router.push('/dashboard')">
        <img src="./img/logo.png" class="logo-img" alt="签到" />
        <div v-if="!sidebarCollapsed">
          <h1>签到管理系统</h1>
          <p>Professional Admin Console</p>
        </div>
      </div>
      <el-menu
        :key="sidebarMenuRenderKey"
        ref="sidebarMenuRef"
        :default-active="$route.path"
        router
        class="sidebar-menu"
        :collapse="sidebarCollapsed"
        :persistent="false"
        @select="closeSidebar"
      >
        <template v-for="parent in sidebarSections" :key="parent.key">
          <el-sub-menu v-if="!parent.path" :index="`menu:${parent.key}`">
            <template #title>
              <el-icon>
                <img
                  v-if="isImageMenuIcon(parent.icon)"
                  :src="menuImage(parent.icon)"
                  class="menu-custom-icon"
                  :alt="parent.title"
                />
                <component :is="menuIcon(parent.icon)" v-else />
              </el-icon>
              <span>{{ parent.title }}</span>
            </template>
            <el-menu-item
              v-for="child in parent.children || []"
              :key="child.key"
              :index="child.path"
            >
              <el-icon><component :is="menuIcon(child.icon)" /></el-icon>
              <span>{{ child.title }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="parent.path">
            <el-icon><component :is="menuIcon(parent.icon)" /></el-icon>
            <span>{{ parent.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container class="main-shell">
      <el-header class="top-header">
        <div class="header-left">
          <el-button
            class="menu-btn"
            :icon="Menu"
            :aria-label="sidebarCollapsed ? '展开菜单' : '收起菜单'"
            @click="toggleSidebar"
          >
            {{ sidebarCollapsed ? '展开菜单' : '收起菜单' }}
          </el-button>
          <div>
            <p class="breadcrumb">{{ breadcrumb.parentTitle }} / {{ breadcrumb.title }}</p>
            <h2>{{ breadcrumb.title }}</h2>
          </div>
        </div>
        <el-space wrap class="header-right">
          <span class="header-current-time" aria-label="当前时间" role="timer">
            <span class="header-current-time__indicator"></span>
            <span class="header-current-time__content">
              <span class="header-current-time__date">{{ currentTime.slice(0, 10) }}</span>
              <span class="header-current-time__clock">{{ currentTime.slice(11) }}</span>
            </span>
          </span>
          <el-popover
            v-model:visible="notifyVisible"
            placement="bottom-end"
            :width="400"
            trigger="click"
            popper-class="notify-popper"
          >
            <template #reference>
              <el-badge
                :value="unreadCount"
                :hidden="unreadCount === 0"
                :max="99"
                class="notify-badge"
                :class="{ pulse: unreadCount > 0 }"
              >
                <el-button class="notify-btn" :icon="Bell" circle aria-label="通知" />
              </el-badge>
            </template>
            <div class="notify-panel">
              <div class="notify-header">
                <span>通知</span>
                <span v-if="unreadCount" class="notify-unread">（{{ unreadCount }} 条未读）</span>
                <div class="notify-header-actions">
                  <el-select v-model="notifyLevelFilter" size="small" style="width: 108px">
                    <el-option label="全部级别" value="ALL" />
                    <el-option label="INFO" value="INFO" />
                    <el-option label="WARNING" value="WARNING" />
                    <el-option label="ERROR" value="ERROR" />
                  </el-select>
                  <el-switch v-model="dndEnabled" size="small" active-text="免打扰" @change="toggleDnd" />
                </div>
              </div>
              <div v-if="notifyGroups.length" class="notify-list">
                <div v-for="group in notifyGroups" :key="group.key" class="notify-group">
                  <div class="notify-group-title">
                    {{ group.label }}
                    <span class="notify-group-count">{{ group.items.length }}</span>
                  </div>
                  <div
                    v-for="item in group.items"
                    :key="item.id"
                    class="notify-item"
                    :class="[`notify-level-${item.level.toLowerCase()}`, { unread: !item.read }]"
                    @click="openNotification(item)"
                  >
                    <span class="notify-dot" :class="`notify-dot-${item.level.toLowerCase()}`"></span>
                    <div class="notify-body">
                      <div class="notify-title">
                        {{ item.title }}
                        <span class="notify-time">{{ item.time }}</span>
                      </div>
                      <div class="notify-message">{{ item.message }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <el-empty v-else description="暂无通知" :image-size="60" />
              <div class="notify-footer">
                <el-button link type="primary" size="small" :disabled="!notifications.length" @click="markAllRead">全部已读</el-button>
                <el-button link size="small" :disabled="!notifications.length" @click="clearNotifications">清空通知</el-button>
              </div>
            </div>
          </el-popover>
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
            <div class="tabs-bar" @wheel.prevent="onTabsWheel">
        <button
          v-show="tabsOverflow"
          class="tabs-nav-btn"
          :aria-label="'向左滚动'"
          @click="scrollTabs(-1)"
        >
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <div class="tabs-scroll" ref="tabsScrollRef">
          <div class="tabs-track">
            <draggable
              v-model="tabs"
              item-key="path"
              :animation="180"
              ghost-class="tab-ghost"
              drag-class="tab-drag"
              chosen-class="tab-chosen"
              @end="onDragEnd"
            >
              <template #item="{ element }">
                <div
                  class="tab-item"
                  :class="{ active: element.path === route.path }"
                  :title="element.parentTitle ? element.parentTitle + ' / ' + element.title : element.title"
                  @click="activateTab(element.path)"
                  @click.middle.prevent="closeTab(element.path)"
                >
                  <el-icon class="tab-icon"><component :is="tabIcon(element)" /></el-icon>
                  <span class="tab-title">{{ element.title }}</span>
                  <span
                    v-if="element.pinned"
                    class="tab-pin"
                    :title="'取消固定'"
                    @click.stop="togglePin(element.path)"
                  >
                    <el-icon><Lock /></el-icon>
                  </span>
                  <template v-else>
                    <span
                      class="tab-pin-action"
                      :title="'固定标签'"
                      @click.stop="togglePin(element.path)"
                    >
                      <el-icon><Lock /></el-icon>
                    </span>
                    <span
                      v-if="tabs.length > 1"
                      class="tab-close"
                      :aria-label="'关闭标签'"
                      @click.stop="closeTab(element.path)"
                    >
                      <el-icon><Close /></el-icon>
                    </span>
                  </template>
                </div>
              </template>
            </draggable>
          </div>
        </div>
        <button
          v-show="tabsOverflow"
          class="tabs-nav-btn"
          :aria-label="'向右滚动'"
          @click="scrollTabs(1)"
        >
          <el-icon><ArrowRight /></el-icon>
        </button>
        <el-dropdown trigger="click" @command="handleTabMenuCommand">
          <button class="tabs-nav-btn" :aria-label="'标签操作菜单'">
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="close-left" :disabled="!canCloseLeft">关闭左侧</el-dropdown-item>
              <el-dropdown-item command="close-right" :disabled="!canCloseRight">关闭右侧</el-dropdown-item>
              <el-dropdown-item command="close-others" :disabled="!canCloseOthers">关闭其他</el-dropdown-item>
              <el-dropdown-item divided command="close-all" :disabled="!canCloseAll">关闭全部</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <el-main>
        <router-view />
      </el-main>
    </el-container>

    <div v-if="!sidebarCollapsed && isMobile" class="sidebar-mask" @click="closeSidebar"></div>
  </el-container>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Odometer, User, Document, Timer, List, Menu, UserFilled, Grid, Setting, Close, Lock, Bell, ArrowLeft, ArrowRight, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAppState } from './composables/useAppState'
import { formatCurrentTime } from './utils/currentTime'
import { getBreadcrumb } from './utils/breadcrumb'
import { logoutApi } from './api'
import { parseLogLine } from './utils/logConsole.js'
import classCubeApi from './api/classCube.js'
import draggable from 'vuedraggable'
import xxqdImage from './img/xxqd.png'
import classCubeImage from './img/bjmf.png'
import {
  menuState,
  resetMenuState,
  startMenuSync,
  stopMenuSync,
  isCurrentMenuVisible,
} from './menu/menuStore.js'
import { buildSidebarSections } from './menu/sidebarSections.js'

const router = useRouter()
const route = useRoute()

const { logs } = useAppState()

const sidebarCollapsed = ref(false)
const sidebarMenuRef = ref(null)
const sidebarMenuRenderKey = ref(0)
const isMobile = ref(false)
const currentUser = ref(null)
const currentTime = ref(formatCurrentTime())
const breadcrumb = computed(() => getBreadcrumb(route.meta))
const sidebarSections = computed(() => buildSidebarSections(
  menuState.menus,
  currentUser.value?.role === 'admin',
))
let currentTimeTimer = null
const iconMap = {
  Odometer,
  User,
  Document,
  Timer,
  List,
  Grid,
  Setting,
  UserFilled,
  Menu,
}
const imageMap = { xxqd: xxqdImage, class_cube: classCubeImage }

const isLoginPage = computed(() => route.path === '/login')

const TABS_STORAGE_PREFIX = 'signin_visited_tabs'
const MAX_TABS = 15

const tabs = ref([])
const tabsScrollRef = ref(null)
const tabsOverflow = ref(false)

function tabsStorageKey() {
  let userId = ''
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    if (user && user.id != null) userId = String(user.id)
  } catch {
    userId = ''
  }
  return userId ? `${TABS_STORAGE_PREFIX}:${userId}` : TABS_STORAGE_PREFIX
}

loadTabs()

function loadTabs() {
  try {
    const parsed = JSON.parse(localStorage.getItem(tabsStorageKey()) || '[]')
    tabs.value = Array.isArray(parsed)
      ? parsed
          .filter(item => item && typeof item.path === 'string' && typeof item.title === 'string')
          .map((item, index) => ({
            path: item.path,
            title: item.title,
            parentTitle: typeof item.parentTitle === 'string' ? item.parentTitle : '',
            pinned: item.pinned === true,
            lastUsedAt: typeof item.lastUsedAt === 'number' ? item.lastUsedAt : Date.now() - index * 1000,
          }))
      : []
  } catch {
    tabs.value = []
  }
}

function persistTabs() {
  try {
    localStorage.setItem(tabsStorageKey(), JSON.stringify(tabs.value))
  } catch {
    // ignore storage errors
  }
}

function clearTabs() {
  tabs.value = []
  try {
    localStorage.removeItem(tabsStorageKey())
  } catch {
    // ignore storage errors
  }
}

function addTab(target) {
  if (!target?.meta?.title) return
  if (tabs.value.some(item => item.path === target.path)) return
  tabs.value.push({
    path: target.path,
    title: target.meta.title,
    parentTitle: target.meta.parentTitle || '',
    pinned: false,
    lastUsedAt: Date.now(),
  })
  if (tabs.value.length > MAX_TABS) evictLeastUsed()
  persistTabs()
  nextTick(updateTabsOverflow)
}

function evictLeastUsed() {
  const candidates = tabs.value.filter(item => !item.pinned)
  if (!candidates.length) return
  candidates.sort((a, b) => (a.lastUsedAt || 0) - (b.lastUsedAt || 0))
  const victim = candidates[0]
  const index = tabs.value.findIndex(item => item.path === victim.path)
  if (index === -1) return
  tabs.value.splice(index, 1)
  const now = Date.now()
  if (now - lastEvictNoticeAt > 5000) {
    lastEvictNoticeAt = now
    ElMessage.warning('标签已达上限（' + MAX_TABS + '），已自动关闭最久未使用的标签')
  }
}

function touchTab(path) {
  const item = tabs.value.find(t => t.path === path)
  if (item) item.lastUsedAt = Date.now()
}

function activateTab(path) {
  touchTab(path)
  if (path !== route.path) router.push(path)
}

function togglePin(path) {
  const item = tabs.value.find(t => t.path === path)
  if (!item) return
  item.pinned = !item.pinned
  persistTabs()
}

function closeTab(path) {
  const index = tabs.value.findIndex(item => item.path === path)
  if (index === -1) return
  if (tabs.value[index].pinned) return
  const wasActive = path === route.path
  tabs.value.splice(index, 1)
  persistTabs()
  if (wasActive) {
    const next = tabs.value[index] || tabs.value[index - 1]
    if (next) router.push(next.path)
    else router.push('/dashboard')
  }
  nextTick(updateTabsOverflow)
}

function removeTabs(paths) {
  const removed = new Set(paths)
  if (!removed.size) return
  const activeRemoved = removed.has(route.path)
  tabs.value = tabs.value.filter(item => !removed.has(item.path))
  persistTabs()
  if (activeRemoved) {
    const next = tabs.value[0]
    if (next) router.push(next.path)
    else router.push('/dashboard')
  }
  nextTick(updateTabsOverflow)
}

function handleTabMenuCommand(command) {
  const currentIndex = tabs.value.findIndex(item => item.path === route.path)
  if (command === 'close-left') {
    if (currentIndex <= 0) return
    removeTabs(tabs.value.slice(0, currentIndex).filter(t => !t.pinned).map(t => t.path))
  } else if (command === 'close-right') {
    if (currentIndex === -1 || currentIndex === tabs.value.length - 1) return
    removeTabs(tabs.value.slice(currentIndex + 1).filter(t => !t.pinned).map(t => t.path))
  } else if (command === 'close-others') {
    removeTabs(tabs.value.filter(t => t.path !== route.path && !t.pinned).map(t => t.path))
  } else if (command === 'close-all') {
    removeTabs(tabs.value.filter(t => !t.pinned).map(t => t.path))
  }
}

function pruneHiddenTabs() {
  if (!currentUser.value || currentUser.value.role === 'admin') return
  if (!menuState.loaded) return
  const visible = tabs.value.filter(item => {
    const meta = router.resolve(item.path)?.meta || {}
    if (!meta.menuKey) return true
    return isCurrentMenuVisible(meta.menuKey, currentUser.value)
  })
  if (visible.length !== tabs.value.length) {
    tabs.value = visible
    persistTabs()
  }
}

function syncCurrentTab() {
  if (route.path === '/login' || !route.meta?.title) return
  addTab(route)
  touchTab(route.path)
  pruneHiddenTabs()
  if (!tabs.value.some(item => item.path === route.path)) addTab(route)
}

function onTabsWheel(event) {
  const el = tabsScrollRef.value
  if (!el) return
  el.scrollLeft += (event.deltaY || event.deltaX) > 0 ? 48 : -48
}

function scrollTabs(direction) {
  const el = tabsScrollRef.value
  if (!el) return
  const distance = Math.max(160, Math.round(el.clientWidth * 0.6))
  el.scrollBy({ left: direction * distance, behavior: 'smooth' })
}

function updateTabsOverflow() {
  const el = tabsScrollRef.value
  tabsOverflow.value = el ? el.scrollWidth > el.clientWidth + 2 : false
}

function scrollActiveTabIntoView() {
  requestAnimationFrame(() => {
    const el = tabsScrollRef.value
    if (!el) return
    const active = el.querySelector('.tab-item.active')
    if (!active) return
    const left = active.offsetLeft - 12
    const right = active.offsetLeft + active.offsetWidth + 12
    if (left < el.scrollLeft) {
      el.scrollTo({ left, behavior: 'smooth' })
    } else if (right > el.scrollLeft + el.clientWidth) {
      el.scrollTo({ left: right - el.clientWidth, behavior: 'smooth' })
    }
  })
}

function tabIcon(tab) {
  return menuIcon(iconNameForTab(tab) || 'Grid')
}

function iconNameForTab(tab) {
  for (const section of sidebarSections.value) {
    if (section.path === tab.path) return section.icon
    for (const child of section.children || []) {
      if (child.path === tab.path) return child.icon
    }
  }
  return ''
}

function onDragEnd() {
  persistTabs()
  nextTick(updateTabsOverflow)
}

// notification helpers
const notifyVisible = ref(false)
const notifications = ref([])
const notifyLevelFilter = ref('ALL')
const dndEnabled = ref(false)
let notifySequence = 0
const NOTIFY_STORAGE_PREFIX = 'signin_notifications'
const NOTIFY_TTL_MS = 7 * 24 * 60 * 60 * 1000
const NOTIFY_LEVELS = ['INFO', 'WARNING', 'ERROR']

function notifyStorageKey() {
  let userId = ''
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    if (user && user.id != null) userId = String(user.id)
  } catch {
    userId = ''
  }
  return userId ? `${NOTIFY_STORAGE_PREFIX}:${userId}` : NOTIFY_STORAGE_PREFIX
}

function pruneOldNotifications() {
  const cutoff = Date.now() - NOTIFY_TTL_MS
  notifications.value = notifications.value.filter(item => (item.ts || 0) >= cutoff)
}

function persistNotifications() {
  pruneOldNotifications()
  try {
    localStorage.setItem(notifyStorageKey(), JSON.stringify({
      dnd: dndEnabled.value,
      notifications: notifications.value,
    }))
  } catch {
    // ignore storage errors
  }
}

function loadNotifications() {
  try {
    const parsed = JSON.parse(localStorage.getItem(notifyStorageKey()) || 'null')
    if (parsed && typeof parsed === 'object') {
      dndEnabled.value = parsed.dnd === true
      if (Array.isArray(parsed.notifications)) {
        notifications.value = parsed.notifications
          .filter(item => item && typeof item.path === 'string' && typeof item.message === 'string')
          .map(item => ({
            id: item.id,
            path: item.path,
            source: item.source === 'class_cube' ? 'class_cube' : 'xxqd',
            title: typeof item.title === 'string' ? item.title : '',
            level: NOTIFY_LEVELS.includes(item.level) ? item.level : 'INFO',
            message: String(item.message || '').slice(0, 120),
            time: typeof item.time === 'string' ? item.time : '',
            ts: typeof item.ts === 'number' ? item.ts : Date.now(),
            read: item.read === true,
          }))
      }
    }
  } catch {
    // ignore storage errors
  }
  pruneOldNotifications()
  notifySequence = notifications.value.reduce((max, item) => Math.max(max, item.id || 0), 0)
}

function menuKeyForNotifyPath(path) {
  return path === '/class-cube/logs' ? 'class_cube.logs' : 'xxqd.logs'
}

function notificationVisible(item) {
  if (currentUser.value?.role === 'admin') return true
  if (!menuState.loaded) return true
  return isCurrentMenuVisible(menuKeyForNotifyPath(item.path), currentUser.value)
}

const visibleNotifications = computed(() => notifications.value.filter(item => {
  if (notifyLevelFilter.value !== 'ALL' && item.level !== notifyLevelFilter.value) return false
  return notificationVisible(item)
}))

const unreadCount = computed(() => notifications.value.filter(item => !item.read && notificationVisible(item)).length)

const notifyGroups = computed(() => {
  const groups = [
    { key: 'xxqd', label: '小小签到', items: [] },
    { key: 'class_cube', label: '班级魔方', items: [] },
  ]
  const index = { xxqd: groups[0], class_cube: groups[1] }
  for (const item of visibleNotifications.value) {
    index[item.source].items.push(item)
  }
  return groups.filter(group => group.items.length)
})

function pushNotification(path, rawLine) {
  if (!notificationVisible({ path })) return
  const parsed = parseLogLine(rawLine)
  const isCc = path === '/class-cube/logs'
  notifySequence += 1
  const now = Date.now()
  notifications.value.unshift({
    id: notifySequence,
    path,
    source: isCc ? 'class_cube' : 'xxqd',
    title: isCc ? '魔方日志' : '运行日志',
    level: NOTIFY_LEVELS.includes(parsed.level) ? parsed.level : 'INFO',
    message: (parsed.message || String(rawLine || '')).slice(0, 120),
    time: new Date(now).toLocaleTimeString('zh-CN', { hour12: false }),
    ts: now,
    read: dndEnabled.value,
  })
  if (notifications.value.length > 200) notifications.value.pop()
  persistNotifications()
}

function markPathRead(path) {
  let changed = false
  notifications.value.forEach(item => {
    if (item.path === path && !item.read) {
      item.read = true
      changed = true
    }
  })
  if (changed) persistNotifications()
}

function markAllRead() {
  let changed = false
  notifications.value.forEach(item => {
    if (!item.read) {
      item.read = true
      changed = true
    }
  })
  if (changed) persistNotifications()
}

function clearNotifications() {
  notifications.value = []
  persistNotifications()
}

function openNotification(item) {
  if (!item.read) {
    item.read = true
    persistNotifications()
  }
  notifyVisible.value = false
  if (item.path !== route.path) router.push(item.path)
}

function toggleDnd(value) {
  dndEnabled.value = value
  persistNotifications()
}

function resetNotifications() {
  notifications.value = []
  notifyVisible.value = false
  notifyLevelFilter.value = 'ALL'
  dndEnabled.value = false
  xxqdLogBaselineSet = false
  lastXxqdLogKey = ''
  ccLogBaselineSet = false
  lastCcLogKey = ''
}

loadNotifications()

watch(() => route.path, path => {
  if (path === '/logs' || path === '/class-cube/logs') markPathRead(path)
}, { immediate: true })

// xxqd log badge
let xxqdLogBaselineSet = false
let lastXxqdLogKey = ''
watch(logs, list => {
  const last = list && list[list.length - 1]
  const lastKey = last ? String(last) : ''
  if (!xxqdLogBaselineSet) {
    xxqdLogBaselineSet = true
    lastXxqdLogKey = lastKey
    return
  }
  if (lastKey && lastKey !== lastXxqdLogKey) {
    lastXxqdLogKey = lastKey
    pushNotification('/logs', last)
  }
})

// class cube log badge
const ccLogs = ref([])
let ccLogBaselineSet = false
let lastCcLogKey = ''
let ccLogTimer = null
let tabsResizeObserver = null

async function refreshCcLogs() {
  try {
    const res = await classCubeApi.listLogs(50)
    if (res.ok) ccLogs.value = res.data || []
  } catch {
    // ignore errors
  }
}

watch(ccLogs, list => {
  const last = list && list[list.length - 1]
  const lastKey = last ? String(last) : ''
  if (!ccLogBaselineSet) {
    ccLogBaselineSet = true
    lastCcLogKey = lastKey
    return
  }
  if (lastKey && lastKey !== lastCcLogKey) {
    lastCcLogKey = lastKey
    pushNotification('/class-cube/logs', last)
  }
})

function startCcLogPolling() {
  stopCcLogPolling()
  refreshCcLogs()
  ccLogTimer = window.setInterval(refreshCcLogs, 3000)
}

function stopCcLogPolling() {
  if (ccLogTimer) {
    window.clearInterval(ccLogTimer)
    ccLogTimer = null
  }
}

// menu command availability
const currentTabIndex = computed(() => tabs.value.findIndex(item => item.path === route.path))
const canCloseLeft = computed(() => {
  if (currentTabIndex.value <= 0) return false
  return tabs.value.slice(0, currentTabIndex.value).some(item => !item.pinned)
})
const canCloseRight = computed(() => {
  if (currentTabIndex.value === -1 || currentTabIndex.value === tabs.value.length - 1) return false
  return tabs.value.slice(currentTabIndex.value + 1).some(item => !item.pinned)
})
const canCloseOthers = computed(() => tabs.value.some(item => item.path !== route.path && !item.pinned))
const canCloseAll = computed(() => tabs.value.some(item => !item.pinned))

let lastEvictNoticeAt = 0

watch(() => route.path, () => {
  syncCurrentTab()
  nextTick(() => {
    scrollActiveTabIntoView()
    updateTabsOverflow()
  })
}, { immediate: true })

watch(() => menuState.version, () => {
  pruneHiddenTabs()
})

watch(currentUser, () => {
  if (currentUser.value) syncCurrentTab()
})

function menuIcon(name) { return iconMap[name] || Grid }
function isImageMenuIcon(name) { return Boolean(imageMap[name]) }
function menuImage(name) { return imageMap[name] || '' }

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
      resetMenuState()
      clearTabs()
      stopCcLogPolling()
      resetNotifications()
      currentUser.value = null
      ElMessage.success('已退出登录')
      router.push('/login')
    }
  }
}

function checkMobile() {
  isMobile.value = window.innerWidth <= 768
  sidebarCollapsed.value = window.innerWidth <= 1024
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function closeSidebar() {
  if (isMobile.value || sidebarCollapsed.value) {
    sidebarMenuRef.value?.close('menu:xxqd')
    sidebarMenuRef.value?.close('menu:class_cube')
    sidebarMenuRef.value?.close('menu:system')
    sidebarMenuRenderKey.value += 1
    sidebarCollapsed.value = true
  }
}

onMounted(async () => {
  checkMobile()
  getUserInfo()
  syncCurrentTab()
  currentTimeTimer = window.setInterval(() => {
    currentTime.value = formatCurrentTime()
  }, 1000)
  window.addEventListener('resize', checkMobile)
  window.addEventListener('resize', updateTabsOverflow)
  if (!isLoginPage.value) {
    startCcLogPolling()
    tabsResizeObserver = new ResizeObserver(() => updateTabsOverflow())
    if (tabsScrollRef.value) tabsResizeObserver.observe(tabsScrollRef.value)
    nextTick(updateTabsOverflow)
    try {
      await startMenuSync(router)
    } catch (error) {
      ElMessage.warning(error.message || '菜单配置暂时无法同步')
    }
  }
})

onUnmounted(() => {
  window.clearInterval(currentTimeTimer)
  window.removeEventListener('resize', checkMobile)
  window.removeEventListener('resize', updateTabsOverflow)
  tabsResizeObserver?.disconnect()
  stopCcLogPolling()
  stopMenuSync()
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
.sidebar-menu { position: relative; border-right: none; background: transparent; }
.sidebar-menu :deep(.el-sub-menu__title), .sidebar-menu :deep(.el-menu-item) { border-radius: 14px; margin: 5px 0; height: 48px; line-height: 48px; color: #dbeafe; transition: all 0.22s ease; }
.sidebar-menu :deep(.el-sub-menu__title:hover), .sidebar-menu :deep(.el-menu-item:hover) { background: rgba(96, 165, 250, 0.14); transform: translateX(3px); }
.sidebar-menu :deep(.el-menu-item.is-active) { background: linear-gradient(90deg, rgba(37, 99, 235, 0.28), rgba(14, 165, 233, 0.12)); box-shadow: inset 3px 0 0 #60a5fa; color: #fff; font-weight: 700; }
.sidebar-menu :deep(.el-sub-menu .el-menu) { background: rgba(255, 255, 255, 0.035); border-radius: 14px; padding: 4px; }
.menu-custom-icon { width: 22px; height: 22px; object-fit: contain; display: block; }
.logo-img { width: 48px; height: 48px; object-fit: contain; display: block; }
.main-shell { min-width: 0; }
.top-header { min-height: 76px; display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 0 28px; background: rgba(255, 255, 255, 0.72); backdrop-filter: blur(18px); border-bottom: 1px solid rgba(226, 232, 240, 0.8); position: sticky; top: 0; z-index: 10; }
.header-left { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.menu-btn { flex: none; margin-right: 4px; color: #2563eb; border-color: #bfdbfe; background: #eff6ff; }
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

.tabs-bar {
  position: sticky;
  top: 76px;
  z-index: 9;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 6px 12px 0;
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.92), rgba(255, 255, 255, 0.66));
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(191, 219, 254, 0.9);
  box-shadow: 0 4px 18px rgba(37, 99, 235, 0.06);
  overflow: hidden;
}
.tabs-scroll {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding: 0 2px 6px;
}
.tabs-scroll::-webkit-scrollbar { display: none; }
.tabs-track { display: flex; align-items: center; gap: 8px; flex: none; }
.tab-item {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex: none;
  height: 34px;
  padding: 0 10px 0 12px;
  border: 1px solid transparent;
  border-radius: 12px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition: all 0.22s ease;
  animation: tabIn 0.25s cubic-bezier(0.34, 1.3, 0.64, 1);
}
.tab-item .tab-icon { color: #60a5fa; font-size: 15px; transition: color 0.22s ease; }
.tab-item:hover {
  color: #1d4ed8;
  background: rgba(219, 234, 254, 0.65);
  border-color: rgba(147, 197, 253, 0.55);
}
.tab-item.active {
  color: #fff;
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 55%, #38bdf8 130%);
  border-color: rgba(255, 255, 255, 0.18);
  box-shadow:
    0 6px 16px rgba(37, 99, 235, 0.32),
    inset 0 1px 0 rgba(255, 255, 255, 0.35);
}
.tab-item.active .tab-icon { color: #e0f2fe; }
.tab-item.active::after {
  content: "";
  position: absolute;
  left: 18%;
  right: 18%;
  bottom: -8px;
  height: 3px;
  border-radius: 3px;
  background: linear-gradient(90deg, #2563eb, #38bdf8);
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.8);
  animation: tabActivePulse 2.4s ease-in-out infinite;
}
.tab-close,
.tab-pin,
.tab-pin-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  font-size: 11px;
  transition: all 0.18s ease;
}
.tab-pin { color: #f59e0b; }
.tab-item.active .tab-pin { color: #fde68a; }
.tab-pin-action { opacity: 0.85; color: #94a3b8; }
.tab-pin-action:hover { opacity: 1; color: #2563eb; background: rgba(37, 99, 235, 0.12); }
.tab-close { opacity: 0.85; margin-left: 1px; }
.tab-item.active .tab-close,
.tab-item.active .tab-pin-action { color: #e0f2fe; }
.tab-close:hover {
  opacity: 1 !important;
  color: #fff;
  background: #ef4444;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.5);
}
.tabs-nav-btn {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid rgba(147, 197, 253, 0.7);
  border-radius: 9px;
  background: linear-gradient(135deg, #eff6ff, #ffffff);
  color: #2563eb;
  cursor: pointer;
  transition: all 0.2s ease;
}
.tabs-nav-btn:hover {
  background: linear-gradient(135deg, #dbeafe, #eff6ff);
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.18);
}
.tabs-nav-btn:active { transform: scale(0.95); }
.tab-ghost { opacity: 0.45; background: #dbeafe; border: 1px dashed #3b82f6; }
.tab-drag { opacity: 0.9; box-shadow: 0 10px 24px rgba(37, 99, 235, 0.35); }
.tab-chosen { border-color: #60a5fa; }

.notify-badge { display: inline-flex; align-items: center; }
.notify-badge.pulse .notify-btn { animation: notifyPulse 1.6s ease-in-out infinite; }
.notify-btn {
  border: 1px solid rgba(96, 165, 250, 0.45);
  background: linear-gradient(135deg, #eff6ff, #ffffff);
  color: #2563eb;
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.1);
  transition: all 0.2s ease;
}
.notify-btn:hover { color: #1d4ed8; border-color: #60a5fa; }
.notify-popper { border-radius: 14px; }
.notify-panel { display: grid; gap: 10px; }
.notify-header { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; font-weight: 700; color: #0f172a; }
.notify-header-actions { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.notify-unread { color: #ef4444; font-size: 12px; font-weight: 600; }
.notify-list { display: grid; gap: 8px; max-height: 340px; overflow-y: auto; }
.notify-group { display: grid; gap: 4px; }
.notify-group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  padding: 2px 6px;
}
.notify-group-count {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: rgba(148, 163, 184, 0.18);
  color: #475569;
  font-size: 11px;
}
.notify-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.18s ease;
}
.notify-item:hover { background: #eff6ff; }
.notify-item.unread { background: rgba(219, 234, 254, 0.5); }
.notify-dot { flex: none; width: 8px; height: 8px; margin-top: 6px; border-radius: 50%; }
.notify-dot-info { background: #94a3b8; }
.notify-dot-warning { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15); }
.notify-dot-error { background: #ef4444; box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15); }
.notify-body { min-width: 0; flex: 1; display: grid; gap: 2px; }
.notify-title { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: #1e293b; }
.notify-item.unread .notify-title { color: #1d4ed8; }
.notify-message {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
}
.notify-item.notify-level-warning .notify-message { color: #b45309; }
.notify-item.notify-level-error .notify-message { color: #b91c1c; }
.notify-time { font-size: 11px; color: #94a3b8; margin-left: auto; flex: none; }
.notify-footer { display: flex; justify-content: flex-end; gap: 4px; border-top: 1px solid #eef2f7; padding-top: 8px; }

@keyframes notifyPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.35); }
  50% { box-shadow: 0 0 0 6px rgba(37, 99, 235, 0); }
}

@keyframes tabIn {
  from { opacity: 0; transform: translateY(8px) scale(0.9); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes tabActivePulse {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 1; }
}
@media (max-width: 768px) {
  .tabs-bar { top: 64px; padding: 5px 8px 0; gap: 6px; }
  .tab-item { height: 32px; padding: 0 8px 0 10px; font-size: 12px; }
  .tab-icon { display: none; }
  .tabs-nav-btn { width: 26px; height: 26px; }
}

@media (max-width: 900px) {
  .top-header { padding: 12px 16px; height: auto; flex-wrap: wrap; }
  .header-left { flex-wrap: wrap; }
}

@media (max-width: 768px) {
  .top-header { min-height: 64px; padding: 10px 12px; }
  .header-left { flex-direction: row; align-items: center; }
  .top-header h2 { font-size: 18px; }
  .breadcrumb { font-size: 11px; }
  .header-right { margin-top: 8px; }
  .header-current-time { min-height: 38px; padding: 5px 10px 5px 8px; gap: 7px; border-radius: 12px; }
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
