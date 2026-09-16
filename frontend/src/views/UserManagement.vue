<template>
  <div class="users-page">
    <div class="page-heading">
      <div><h2>用户管理</h2><p>管理当前用户、会员卡和永久保留的过期归档</p></div>
      <div class="page-heading__actions">
        <template v-if="activeTab === 'current'">
          <el-button plain @click="openMemberCreate">一键创建用户</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
        </template>
        <el-button
          v-else
          type="primary"
          :icon="Download"
          :loading="exporting"
          @click="exportArchivedUsers"
        >
          导出归档清单
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-tabs v-model="activeTab" class="user-view-tabs">
        <el-tab-pane :label="`当前用户 (${currentPageData.current_total})`" name="current">
          <UserFilterBar
            v-model:keyword="currentFilters.keyword"
            v-model:role="currentFilters.role"
            v-model:card="currentFilters.card"
            v-model:status="currentFilters.status"
            v-model:scope="currentFilters.scope"
            :visible-count="currentUsers.length"
            :total-count="currentPageData.total"
            @reset="resetCurrentFilters"
          />
          <UserTable
            :users="currentUsers"
            :loading="currentLoading"
            @edit="openEdit"
            @reset="openReset"
            @remove="removeUser"
          />
          <el-pagination
            v-if="currentPageData.total > currentPageData.page_size"
            class="user-pagination"
            background
            layout="total, prev, pager, next"
            :current-page="currentPageData.page"
            :page-size="currentPageData.page_size"
            :total="currentPageData.total"
            @current-change="changeCurrentPage"
          />
        </el-tab-pane>

        <el-tab-pane :label="`已过期归档 (${currentPageData.archived_total})`" name="archived">
          <ArchiveFilterBar
            v-model:keyword="archiveFilters.keyword"
            v-model:card="archiveFilters.card"
            v-model:scope="archiveFilters.scope"
            v-model:date-range="archiveFilters.dateRange"
            :total-count="archivePageData.archived_total"
            @reset="resetArchiveFilters"
          />
          <ArchivedUserTable
            :users="archiveUsers"
            :loading="archiveLoading"
            @detail="openArchiveDetail"
          />
          <el-pagination
            v-if="archivePageData.total > archivePageData.page_size"
            class="user-pagination"
            background
            layout="total, prev, pager, next"
            :current-page="archivePageData.page"
            :page-size="archivePageData.page_size"
            :total="archivePageData.total"
            @current-change="changeArchivePage"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <UserEditorDialog
      v-model="userDialog"
      :user-id="editingUser?.id || null"
      :initial-user="editingUser"
      :account-pool="accountPool"
      @saved="handleSaved"
    />
    <MemberCardDialog
      v-model="memberDialog"
      :default-platform="memberPlatform"
      @saved="handleSaved"
    />
    <PasswordResetDialog
      v-model="resetDialog"
      :user="resetUser"
      @saved="handleSaved"
    />
    <ArchivedUserDetailDrawer
      v-model="archiveDetailDialog"
      :user="archiveDetailUser"
      @view-runs="viewArchiveRuns"
    />
  </div>
</template>

<script setup>
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteUserApi, exportArchivedUsersApi, getUsersApi } from '../api'
import classCubeApi from '../api/classCube.js'
import ArchiveFilterBar from '../components/user-management/ArchiveFilterBar.vue'
import ArchivedUserDetailDrawer from '../components/user-management/ArchivedUserDetailDrawer.vue'
import ArchivedUserTable from '../components/user-management/ArchivedUserTable.vue'
import MemberCardDialog from '../components/user-management/MemberCardDialog.vue'
import PasswordResetDialog from '../components/user-management/PasswordResetDialog.vue'
import UserEditorDialog from '../components/user-management/UserEditorDialog.vue'
import UserFilterBar from '../components/user-management/UserFilterBar.vue'
import UserTable from '../components/user-management/UserTable.vue'
import { accountStatus } from '../utils/userMembership'

const route = useRoute()
const router = useRouter()
const activeTab = ref(route.query.tab === 'archived' ? 'archived' : 'current')
const currentUsers = ref([])
const archiveUsers = ref([])
const accountPool = ref([])
const currentLoading = ref(false)
const archiveLoading = ref(false)
const exporting = ref(false)
const userDialog = ref(false)
const editingUser = ref(null)
const memberDialog = ref(false)
const memberPlatform = ref('class_cube')
const resetDialog = ref(false)
const resetUser = ref(null)
const archiveDetailDialog = ref(false)
const archiveDetailUser = ref(null)
const currentPage = ref(1)
const archivePage = ref(1)
const pageSize = 20
const currentFilters = reactive({ keyword: '', role: '', card: '', status: '', scope: '' })
const archiveFilters = reactive({ keyword: '', card: '', scope: '', dateRange: [] })
const currentPageData = reactive(emptyPageData())
const archivePageData = reactive(emptyPageData())
const currentFilterSignature = computed(() => JSON.stringify(currentFilters))
const archiveFilterSignature = computed(() => JSON.stringify(archiveFilters))
let filterTimer = null
let userRefreshTimer = null

function emptyPageData() {
  return { items: [], total: 0, page: 1, page_size: pageSize, current_total: 0, archived_total: 0 }
}

function resetCurrentFilters() {
  Object.assign(currentFilters, { keyword: '', role: '', card: '', status: '', scope: '' })
}

function resetArchiveFilters() {
  Object.assign(archiveFilters, { keyword: '', card: '', scope: '', dateRange: [] })
}

function openCreate() { editingUser.value = null; userDialog.value = true }
function openEdit(row) { if (accountStatus(row) === 'expired') return; editingUser.value = row; userDialog.value = true }
function openReset(row) { if (accountStatus(row) === 'expired') return; resetUser.value = row; resetDialog.value = true }
function openMemberCreate() { memberPlatform.value = 'class_cube'; memberDialog.value = true }
function openArchiveDetail(row) { archiveDetailUser.value = row; archiveDetailDialog.value = true }
function changeCurrentPage(page) { currentPage.value = page; loadCurrentUsers() }
function changeArchivePage(page) { archivePage.value = page; loadArchivedUsers() }

function viewArchiveRuns(platformScope) {
  if (!archiveDetailUser.value) return
  const path = platformScope === 'xxqd' ? '/runs' : '/class-cube/runs'
  router.push({
    path,
    query: {
      owner_user_id: archiveDetailUser.value.id,
      username: archiveDetailUser.value.username,
    },
  })
}

function scheduleFilterReload(loader, resetPage) {
  if (filterTimer) window.clearTimeout(filterTimer)
  filterTimer = window.setTimeout(() => { resetPage(); loader() }, 250)
}

async function loadCurrentUsers() {
  currentLoading.value = true
  try {
    const response = await getUsersApi({
      view: 'current', keyword: currentFilters.keyword || undefined,
      role: currentFilters.role || undefined, card_type: currentFilters.card || undefined,
      status: currentFilters.status || undefined, platform_scope: currentFilters.scope || undefined,
      page: currentPage.value, page_size: pageSize,
    })
    Object.assign(currentPageData, response.data)
    currentUsers.value = response.data.items || []
  } catch (error) { ElMessage.error(error.message) }
  finally { currentLoading.value = false }
}

async function loadArchivedUsers() {
  archiveLoading.value = true
  try {
    const response = await getUsersApi({
      view: 'archived', keyword: archiveFilters.keyword || undefined,
      ...archiveQueryParams(),
      page: archivePage.value, page_size: pageSize,
    })
    Object.assign(archivePageData, response.data)
    archiveUsers.value = response.data.items || []
  } catch (error) { ElMessage.error(error.message) }
  finally { archiveLoading.value = false }
}

function archiveQueryParams() {
  const [startDate, endDate] = archiveFilters.dateRange || []
  return {
    keyword: archiveFilters.keyword || undefined,
    card_type: archiveFilters.card || undefined,
    platform_scope: archiveFilters.scope || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
  }
}

async function exportArchivedUsers() {
  exporting.value = true
  try {
    const blob = await exportArchivedUsersApi(archiveQueryParams())
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `过期用户归档-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('归档清单已导出')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    exporting.value = false
  }
}

async function loadAccountPool() {
  try { accountPool.value = (await classCubeApi.listAccounts()).data || [] }
  catch { accountPool.value = [] }
}

async function handleSaved() {
  if (activeTab.value === 'archived') await loadArchivedUsers()
  else await loadCurrentUsers()
}

async function removeUser(row) {
  if (accountStatus(row) === 'expired') return
  try {
    await ElMessageBox.confirm(`确认删除用户“${row.username}”？`, '删除用户', { type: 'warning' })
    await deleteUserApi(row.id)
    if (currentUsers.value.length === 1 && currentPage.value > 1) currentPage.value -= 1
    ElMessage.success('用户已删除')
    await loadCurrentUsers()
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error.message) }
}

watch(activeTab, async (tab) => {
  router.replace({ query: { ...route.query, tab } })
  if (tab === 'archived') await loadArchivedUsers()
  else await loadCurrentUsers()
})
watch(currentFilterSignature, () => scheduleFilterReload(loadCurrentUsers, () => { currentPage.value = 1 }))
watch(archiveFilterSignature, () => scheduleFilterReload(loadArchivedUsers, () => { archivePage.value = 1 }))

onMounted(async () => {
  await Promise.all([loadAccountPool(), loadCurrentUsers()])
  if (activeTab.value === 'archived') await loadArchivedUsers()
  userRefreshTimer = window.setInterval(() => {
    if (activeTab.value === 'current' && !currentLoading.value) loadCurrentUsers()
  }, 30_000)
})
onBeforeUnmount(() => {
  if (filterTimer) window.clearTimeout(filterTimer)
  if (userRefreshTimer) window.clearInterval(userRefreshTimer)
})
</script>

<style scoped>
.users-page { display: grid; gap: 20px; }
.page-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.page-heading__actions { display: flex; align-items: center; gap: 10px; }
.page-heading h2 { margin: 0 0 6px; color: #0f172a; }
.page-heading p { margin: 0; color: #64748b; }
.table-card { border-radius: 18px; }
.user-view-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }
.user-pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 640px) {
  .page-heading { display: grid; grid-template-columns: minmax(0, 1fr); align-items: start; gap: 10px; }
  .page-heading h2 { margin-bottom: 3px; font-size: 20px; }
  .page-heading p { font-size: 12px; line-height: 1.45; }
  .page-heading__actions { display: grid; grid-template-columns: minmax(0, 1fr); width: 100%; }
  .page-heading__actions .el-button { width: 100%; margin: 0; }
  .user-view-tabs :deep(.el-tabs__nav-wrap) { padding-inline: 2px; }
  .user-pagination { justify-content: center; }
}
</style>
