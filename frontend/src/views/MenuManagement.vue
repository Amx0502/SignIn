<template>
  <div class="menu-management-page">
    <div class="page-heading">
      <div>
        <h2>菜单管理</h2>
        <p>配置普通用户可见的一级菜单和二级菜单，保存后在线用户立即生效。</p>
      </div>
      <el-tag type="info" effect="plain">配置版本 {{ version || '-' }}</el-tag>
    </div>

    <el-alert
      v-if="conflictVersion"
      type="warning"
      :closable="false"
      show-icon
      class="conflict-alert"
    >
      <template #title>配置已被其他管理员更新（最新版本 {{ conflictVersion }}）</template>
      <el-button size="small" type="warning" plain @click="reloadAfterConflict">刷新并重新编辑</el-button>
    </el-alert>

    <el-card shadow="never" class="config-card" v-loading="loading">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="全局默认配置" name="global">
          <div class="section-copy">
            <strong>全部普通用户的默认菜单</strong>
            <span>一级和二级菜单互不联动；隐藏一级菜单时会暂时隐藏其子菜单，但保留子菜单设置。</span>
          </div>
          <div class="menu-tree-list">
            <div
              v-for="row in rows"
              :key="`global-${row.key}`"
              class="menu-config-row"
              :class="{ 'is-child': row.depth > 0 }"
            >
              <div class="menu-label" :style="{ paddingLeft: `${row.depth * 30}px` }">
                <span class="level-badge">{{ row.depth ? '二级' : '一级' }}</span>
                <div><strong>{{ row.title }}</strong><small>{{ row.path || '菜单分组' }}</small></div>
              </div>
              <el-checkbox v-model="globalVisibility[row.key]">
                {{ globalVisibility[row.key] ? '显示' : '隐藏' }}
              </el-checkbox>
            </div>
          </div>
          <div class="save-bar">
            <span>{{ globalDirty ? '有未保存修改' : '配置已保存' }}</span>
            <el-button type="primary" :loading="saving" :disabled="!globalDirty" @click="saveGlobal">
              保存全局配置
            </el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="用户级覆盖" name="user">
          <div class="user-picker">
            <div><strong>选择普通用户</strong><small>未设置的菜单自动继承全局配置。</small></div>
            <el-select
              v-model="selectedUserId"
              filterable
              placeholder="请选择普通用户"
              @change="loadSelectedUser"
            >
              <el-option
                v-for="user in ordinaryUsers"
                :key="user.id"
                :label="user.username"
                :value="user.id"
              />
            </el-select>
          </div>
          <el-empty v-if="!selectedUserId" description="请选择需要配置的普通用户" />
          <template v-else>
            <div class="menu-tree-list">
              <div
                v-for="row in rows"
                :key="`user-${row.key}`"
                class="menu-config-row override-row"
                :class="{ 'is-child': row.depth > 0 }"
              >
                <div class="menu-label" :style="{ paddingLeft: `${row.depth * 30}px` }">
                  <span class="level-badge">{{ row.depth ? '二级' : '一级' }}</span>
                  <div>
                    <strong>{{ row.title }}</strong>
                    <small>全局当前：{{ globalVisibility[row.key] ? '显示' : '隐藏' }}</small>
                  </div>
                </div>
                <el-radio-group v-model="userOverrides[row.key]" size="small">
                  <el-radio-button value="inherit">继承全局</el-radio-button>
                  <el-radio-button value="visible">显示</el-radio-button>
                  <el-radio-button value="hidden">隐藏</el-radio-button>
                </el-radio-group>
              </div>
            </div>
            <div class="save-bar">
              <span>{{ overrideDirty ? '有未保存修改' : '配置已保存' }}</span>
              <el-button type="primary" :loading="saving" :disabled="!overrideDirty" @click="saveOverrides">
                保存用户配置
              </el-button>
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card shadow="never" class="audit-card">
      <template #header>
        <div class="audit-head"><strong>修改记录</strong><el-button link type="primary" @click="loadLogs">刷新记录</el-button></div>
      </template>
      <el-table :data="logs" v-loading="logsLoading" empty-text="暂无修改记录">
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="管理员" min-width="120">
          <template #default="{ row }">{{ userName(row.actor_user_id, '已删除管理员') }}</template>
        </el-table-column>
        <el-table-column label="作用范围" min-width="150">
          <template #default="{ row }">
            {{ row.target_type === 'global' ? '全局默认' : `用户：${userName(row.target_user_id)}` }}
          </template>
        </el-table-column>
        <el-table-column label="变更内容" min-width="300">
          <template #default="{ row }">{{ changeSummary(row) }}</template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="90" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  getAdminMenuConfigApi,
  getMenuConfigLogsApi,
  getUsersApi,
  updateGlobalMenuConfigApi,
  updateUserMenuOverridesApi,
} from '../api/index.js'
import { flattenMenuCatalog } from '../menu/menuPermissions.js'

const activeTab = ref('global')
const loading = ref(false)
const saving = ref(false)
const logsLoading = ref(false)
const version = ref(0)
const conflictVersion = ref(0)
const catalog = ref([])
const globalVisibility = ref({})
const userOverrides = ref({})
const users = ref([])
const selectedUserId = ref(null)
const loadedUserId = ref(null)
const logs = ref([])
const savedGlobal = ref('{}')
const savedOverrides = ref('{}')

const rows = computed(() => flattenMenuCatalog(catalog.value))
const ordinaryUsers = computed(() => users.value.filter(user => user.role === 'user' && user.is_active))
const globalDirty = computed(() => JSON.stringify(globalVisibility.value) !== savedGlobal.value)
const overrideDirty = computed(() => JSON.stringify(userOverrides.value) !== savedOverrides.value)
const hasUnsavedChanges = computed(() => globalDirty.value || overrideDirty.value)

function captureSavedState() {
  savedGlobal.value = JSON.stringify(globalVisibility.value)
  savedOverrides.value = JSON.stringify(userOverrides.value)
}

async function loadUsers() {
  const response = await getUsersApi()
  users.value = response?.data || []
  if (!selectedUserId.value && ordinaryUsers.value.length) {
    selectedUserId.value = ordinaryUsers.value[0].id
  }
}

async function loadConfig(userId = selectedUserId.value) {
  const response = await getAdminMenuConfigApi(userId)
  const config = response?.data || {}
  version.value = config.version || 0
  catalog.value = config.catalog || []
  globalVisibility.value = { ...(config.global || {}) }
  userOverrides.value = { ...(config.overrides || {}) }
  loadedUserId.value = userId || null
  conflictVersion.value = 0
  captureSavedState()
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const response = await getMenuConfigLogsApi(100)
    logs.value = response?.data || []
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    logsLoading.value = false
  }
}

async function loadInitial() {
  loading.value = true
  try {
    await loadUsers()
    await Promise.all([loadConfig(), loadLogs()])
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

async function loadSelectedUser(userId) {
  if (hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm('切换用户将放弃尚未保存的菜单修改，是否继续？', '未保存修改', { type: 'warning' })
    } catch {
      selectedUserId.value = loadedUserId.value
      return
    }
  }
  loading.value = true
  try { await loadConfig(userId) }
  catch (error) { ElMessage.error(error.message) }
  finally { loading.value = false }
}

function handleSaveError(error) {
  if (error.status === 409) {
    conflictVersion.value = error.data?.current_version || 0
    ElMessage.error('配置已被其他管理员修改，当前编辑内容已保留')
  } else {
    ElMessage.error(error.message || '保存失败，当前编辑内容已保留')
  }
}

async function saveGlobal() {
  saving.value = true
  try {
    const response = await updateGlobalMenuConfigApi({
      version: version.value,
      visibility: globalVisibility.value,
    })
    version.value = response.data.version
    savedGlobal.value = JSON.stringify(globalVisibility.value)
    conflictVersion.value = 0
    ElMessage.success('全局菜单配置已保存并实时生效')
    await loadLogs()
  } catch (error) {
    handleSaveError(error)
  } finally {
    saving.value = false
  }
}

async function saveOverrides() {
  if (!selectedUserId.value) return
  saving.value = true
  try {
    const response = await updateUserMenuOverridesApi(selectedUserId.value, {
      version: version.value,
      overrides: userOverrides.value,
    })
    version.value = response.data.version
    savedOverrides.value = JSON.stringify(userOverrides.value)
    conflictVersion.value = 0
    ElMessage.success('用户菜单配置已保存并实时生效')
    await loadLogs()
  } catch (error) {
    handleSaveError(error)
  } finally {
    saving.value = false
  }
}

async function reloadAfterConflict() {
  if (hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm('刷新将放弃当前未保存的修改，是否继续？', '刷新配置', { type: 'warning' })
    } catch {
      return
    }
  }
  loading.value = true
  try { await loadConfig(selectedUserId.value) }
  catch (error) { ElMessage.error(error.message) }
  finally { loading.value = false }
}

function userName(id, fallback = '') {
  return users.value.find(user => user.id === id)?.username || fallback || `用户 #${id}`
}

function changeSummary(log) {
  const labels = Object.fromEntries(rows.value.map(row => [row.key, row.title]))
  return Object.entries(log.after || {}).map(([key, value]) => {
    const state = value === true || value === 'visible'
      ? '显示'
      : value === false || value === 'hidden' ? '隐藏' : '继承全局'
    return `${labels[key] || key} → ${state}`
  }).join('；') || '无状态变化'
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function beforeUnload(event) {
  if (!hasUnsavedChanges.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(async () => {
  if (!hasUnsavedChanges.value) return true
  try {
    await ElMessageBox.confirm('还有未保存的菜单配置，确定离开吗？', '未保存修改', { type: 'warning' })
    return true
  } catch {
    return false
  }
})

onMounted(() => {
  window.addEventListener('beforeunload', beforeUnload)
  void loadInitial()
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<style scoped>
.menu-management-page { display: grid; gap: 18px; }
.page-heading,.audit-head,.save-bar,.user-picker { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-heading h2 { margin: 0 0 6px; color: #0f172a; }.page-heading p { margin: 0; color: #64748b; }
.config-card,.audit-card { border-radius: 20px; border-color: #dbeafe; }.conflict-alert { border-radius: 14px; }
.section-copy { display: grid; gap: 5px; margin-bottom: 14px; }.section-copy span,.user-picker small { color: #64748b; font-size: 12px; }
.menu-tree-list { display: grid; gap: 8px; }.menu-config-row { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 18px; padding: 13px 16px; border: 1px solid #dbeafe; border-radius: 14px; background: #f8fbff; }.menu-config-row.is-child { background: #fff; }
.menu-label { display: flex; min-width: 0; align-items: center; gap: 10px; }.menu-label div { min-width: 0; }.menu-label strong,.menu-label small { display: block; }.menu-label small { margin-top: 3px; color: #94a3b8; font-size: 11px; overflow-wrap: anywhere; }
.level-badge { flex: none; padding: 3px 7px; color: #2563eb; font-size: 10px; border-radius: 999px; background: #dbeafe; }.is-child .level-badge { color: #0f766e; background: #ccfbf1; }
.save-bar { position: sticky; bottom: 0; margin-top: 16px; padding: 14px 16px; color: #64748b; border: 1px solid #dbeafe; border-radius: 14px; background: rgb(255 255 255 / 94%); box-shadow: 0 -8px 24px rgb(15 23 42 / 5%); }
.user-picker { margin-bottom: 16px; }.user-picker div { display: grid; gap: 4px; }.user-picker .el-select { width: min(360px, 100%); }.override-row .el-radio-group { flex: none; }
@media(max-width:760px){.page-heading,.user-picker,.menu-config-row,.save-bar{align-items:stretch;flex-direction:column}.menu-label{padding-left:0!important}.override-row .el-radio-group{display:grid;grid-template-columns:1fr 1fr 1fr;width:100%}.override-row :deep(.el-radio-button__inner){width:100%;padding-inline:8px}.save-bar .el-button{width:100%}}
</style>
