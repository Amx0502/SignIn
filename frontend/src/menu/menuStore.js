import { reactive } from 'vue'

import { getMenuCatalogApi } from '../api/index.js'
import { watchMenuVersions } from './menuEvents.js'
import { bootstrapMenuSync } from './menuStartup.js'
import {
  firstVisiblePath,
  menuKeyIsVisible,
  resolveMenuRedirect,
} from './menuPermissions.js'


export const menuState = reactive({
  version: 0,
  menus: [],
  loaded: false,
  loading: false,
  error: '',
})

let loadPromise = null
let streamController = null
let reconnectTimer = null
let activeRouter = null

function currentUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

function cacheKey(user) {
  return user?.id ? `menu_catalog:${user.id}` : ''
}

function persistCatalog(user) {
  const key = cacheKey(user)
  if (!key) return
  localStorage.setItem(key, JSON.stringify({
    version: menuState.version,
    menus: menuState.menus,
  }))
}

export function hydrateMenuCatalog(user = currentUser()) {
  const key = cacheKey(user)
  if (!key || menuState.loaded) return false
  try {
    const cached = JSON.parse(localStorage.getItem(key) || 'null')
    if (!Number.isInteger(cached?.version) || !Array.isArray(cached?.menus)) {
      return false
    }
    menuState.version = cached.version
    menuState.menus = cached.menus
    menuState.loaded = true
    return true
  } catch {
    return false
  }
}

export async function refreshMenuCatalog({ force = false } = {}) {
  if (loadPromise && !force) return loadPromise
  menuState.loading = true
  loadPromise = (async () => {
    try {
      const response = await getMenuCatalogApi()
      const catalog = response?.data || {}
      if (!Number.isInteger(catalog.version) || !Array.isArray(catalog.menus)) {
        throw new Error('菜单配置响应无效')
      }
      menuState.version = catalog.version
      menuState.menus = catalog.menus
      menuState.loaded = true
      menuState.error = ''
      persistCatalog(currentUser())
      return catalog
    } catch (error) {
      menuState.error = error.message || '菜单配置同步失败'
      throw error
    } finally {
      menuState.loading = false
      loadPromise = null
    }
  })()
  return loadPromise
}

export async function ensureMenuCatalog() {
  hydrateMenuCatalog()
  if (!menuState.loaded) await refreshMenuCatalog()
  return menuState
}

export function isCurrentMenuVisible(menuKey, user = currentUser()) {
  return user?.role === 'admin' || menuKeyIsVisible(menuState.menus, menuKey)
}

export function firstAllowedPath(user = currentUser()) {
  return user?.role === 'admin' ? '/overview' : firstVisiblePath(menuState.menus)
}

async function ensureRouteAllowed(router = activeRouter) {
  const user = currentUser()
  if (!router || !user || user.role === 'admin') return
  const route = router.currentRoute.value
  const redirect = resolveMenuRedirect({
    menus: menuState.menus,
    menuKey: route.meta?.menuKey,
    currentPath: route.path,
  })
  if (redirect) await router.replace(redirect)
}

async function delay(ms, signal) {
  await new Promise(resolve => {
    reconnectTimer = window.setTimeout(resolve, ms)
    signal?.addEventListener('abort', resolve, { once: true })
  })
  reconnectTimer = null
}

async function streamLoop(signal) {
  while (!signal.aborted) {
    try {
      await watchMenuVersions({
        lastVersion: menuState.version,
        signal,
        onVersion: async version => {
          if (version <= menuState.version) return
          await refreshMenuCatalog({ force: true })
          await ensureRouteAllowed()
        },
      })
    } catch (error) {
      if (error?.status === 401) return
      if (!signal.aborted) menuState.error = error.message || '菜单实时连接已断开'
    }
    if (!signal.aborted) await delay(1500, signal)
  }
}

async function refreshOnResume() {
  if (document.visibilityState === 'hidden') return
  try {
    await refreshMenuCatalog({ force: true })
    await ensureRouteAllowed()
  } catch {
    // Keep the last successfully loaded menu during a temporary outage.
  }
}

export async function startMenuSync(router) {
  stopMenuSync()
  activeRouter = router
  const controller = new AbortController()
  await bootstrapMenuSync({
    hydrate: hydrateMenuCatalog,
    refresh: () => refreshMenuCatalog({ force: true }),
    ensureAllowed: () => ensureRouteAllowed(router),
    startStream: () => {
      streamController = controller
      void streamLoop(controller.signal)
    },
  })
  window.addEventListener('online', refreshOnResume)
  document.addEventListener('visibilitychange', refreshOnResume)
}

export function stopMenuSync() {
  streamController?.abort()
  streamController = null
  if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
  reconnectTimer = null
  window.removeEventListener('online', refreshOnResume)
  document.removeEventListener('visibilitychange', refreshOnResume)
  activeRouter = null
}

export function resetMenuState() {
  stopMenuSync()
  menuState.version = 0
  menuState.menus = []
  menuState.loaded = false
  menuState.loading = false
  menuState.error = ''
}
