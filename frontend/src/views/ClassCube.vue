<template>
  <div class="class-cube-page">
    <section class="cube-hero">
      <div>
        <span class="cube-hero__eyebrow">CLASS CUBE AUTOMATION</span>
        <h1>班级魔方签到工作台</h1>
        <p>集中管理扫码账号、课程签到与 30 秒自动监控任务。</p>
      </div>
      <div class="hero-badges">
        <span><el-icon><Lock /></el-icon>用户数据隔离</span>
        <span><el-icon><Timer /></el-icon>低内存调度</span>
      </div>
    </section>

    <el-alert
      v-if="error"
      class="cube-error"
      :title="error"
      type="error"
      show-icon
      closable
      @close="error = ''"
    />

    <el-tabs v-model="activeTab" class="cube-tabs">
      <el-tab-pane name="accounts">
        <template #label><span class="tab-label"><el-icon><User /></el-icon>账号与签到</span></template>
        <AccountCheckinPanel
          :accounts="accounts"
          :courses="courses"
          :items="items"
          :tasks="tasks"
          :selected-account-id="selectedAccountId"
          :selected-course-id="selectedCourseId"
          :selected-item-id="selectedItemId"
          :selected-course="selectedCourse"
          :selected-item="selectedItem"
          :upload-photo-action="uploadPhoto"
          :manual-checkin-action="manualCheckin"
          @qr-login="openQrLogin"
          @select-account="handleSelectAccount"
          @select-course="handleSelectCourse"
          @select-item="value => selectedItemId = value"
          @sync-courses="handleSyncCourses"
          @sync-items="handleSyncItems"
          @rename-account="handleRenameAccount"
          @delete-account="handleDeleteAccount"
        />
      </el-tab-pane>
      <el-tab-pane name="tasks">
        <template #label><span class="tab-label"><el-icon><Calendar /></el-icon>自动任务</span></template>
        <AutoTaskPanel
          :tasks="tasks"
          :accounts="accounts"
          :courses="courses"
          :selected-task-ids="selectedTaskIds"
          :is-admin="isAdmin"
          :save-task-action="saveTask"
          :remove-tasks-action="removeTasks"
          :run-task-action="runTask"
          :upload-photo-action="uploadPhoto"
          @update:selected-task-ids="value => selectedTaskIds = value"
          @select-account="handleSelectAccount"
          @refresh="refreshBackground"
        />
      </el-tab-pane>
      <el-tab-pane name="runs">
        <template #label><span class="tab-label"><el-icon><List /></el-icon>运行记录</span></template>
        <RunHistoryPanel
          :runs="runs"
          :tasks="tasks"
          :accounts="accounts"
          :courses="courses"
          :is-admin="isAdmin"
          :load-runs-action="loadRuns"
          :retry-claim-action="retryClaim"
        />
      </el-tab-pane>
    </el-tabs>

    <QrLoginDialog
      v-model="qrVisible"
      :session="qrSession"
      :qr-remaining-seconds="qrRemainingSeconds"
      :loading="qrLoading"
      @regenerate="regenerateQr"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Calendar, List, Lock, Timer, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AccountCheckinPanel from '../components/class-cube/AccountCheckinPanel.vue'
import AutoTaskPanel from '../components/class-cube/AutoTaskPanel.vue'
import QrLoginDialog from '../components/class-cube/QrLoginDialog.vue'
import RunHistoryPanel from '../components/class-cube/RunHistoryPanel.vue'
import { useClassCube } from '../composables/useClassCube.js'

const {
  accounts, courses, items, tasks, runs,
  selectedAccountId, selectedCourseId, selectedItemId, selectedTaskIds,
  selectedCourse, selectedItem, qrSession, qrRemainingSeconds, error,
  loadInitial, loadAccounts, loadTasks, loadRuns, selectAccount, selectCourse,
  syncCourses, syncItems, saveTask, removeTasks, refreshBackground,
  startBackgroundPolling, startQrLogin, uploadPhoto, manualCheckin,
  updateAccount, deleteAccount, runTask, retryClaim,
} = useClassCube()

const activeTab = ref('accounts')
const qrVisible = ref(false)
const qrLoading = ref(false)
const qrAccountId = ref(null)
const currentUser = (() => {
  try { return JSON.parse(localStorage.getItem('user') || 'null') || {} } catch { return {} }
})()
const isAdmin = computed(() => currentUser.role === 'admin')

async function safely(action, successMessage = '') {
  try {
    const result = await action()
    if (successMessage) ElMessage.success(successMessage)
    return result
  } catch (caught) {
    ElMessage.error(caught.message || '操作失败')
    return null
  }
}
async function handleSelectAccount(id) { await safely(() => selectAccount(id)) }
async function handleSelectCourse(id) { await safely(() => selectCourse(id)) }
async function handleSyncCourses(id) { await safely(() => syncCourses(id), '课程同步完成') }
async function handleSyncItems(id) { await safely(() => syncItems(id), '签到项同步完成') }
async function handleRenameAccount(id, name) {
  const changed = await safely(() => updateAccount(id, { name }), '账号备注已更新')
  if (changed) await loadAccounts()
}
async function handleDeleteAccount(id) {
  const changed = await safely(() => deleteAccount(id), '账号已删除')
  if (changed) {
    await Promise.all([loadAccounts(), loadTasks(), loadRuns()])
    await selectAccount(selectedAccountId.value)
  }
}
async function openQrLogin(accountId = null) {
  qrAccountId.value = accountId
  qrVisible.value = true
  await regenerateQr()
}
async function regenerateQr() {
  qrLoading.value = true
  try { await startQrLogin(qrAccountId.value) }
  catch (caught) { ElMessage.error(caught.message || '二维码生成失败') }
  finally { qrLoading.value = false }
}

onMounted(async () => {
  await safely(() => loadInitial())
  startBackgroundPolling()
})
</script>

<style scoped>
.class-cube-page { display:grid;gap:18px;padding:0;animation:cubeIn .42s ease both }
.cube-hero { position:relative;display:flex;align-items:flex-end;justify-content:space-between;gap:20px;min-height:158px;padding:26px 28px;overflow:hidden;color:#fff;border-radius:25px;background:radial-gradient(circle at 88% 8%,rgb(255 255 255 / 24%),transparent 28%),linear-gradient(125deg,#1d4ed8 0%,#2563eb 42%,#0ea5e9 100%);box-shadow:0 20px 50px rgb(37 99 235 / 22%) }
.cube-hero::after{content:"";position:absolute;width:230px;height:230px;right:-90px;bottom:-165px;border:36px solid rgb(255 255 255 / 9%);border-radius:50%}.cube-hero>div{position:relative;z-index:1}.cube-hero__eyebrow{font-size:10px;font-weight:800;letter-spacing:.18em;opacity:.75}.cube-hero h1{margin:8px 0 7px;color:#fff;font-size:30px;letter-spacing:-.04em}.cube-hero p{margin:0;color:rgb(255 255 255 / 82%);font-size:13px}.hero-badges{display:flex;gap:9px;flex-wrap:wrap}.hero-badges span{display:flex;align-items:center;gap:6px;padding:8px 11px;border:1px solid rgb(255 255 255 / 22%);border-radius:12px;background:rgb(255 255 255 / 12%);font-size:11px;backdrop-filter:blur(10px)}
.cube-error{border-radius:14px}.cube-tabs{padding:4px 0}.tab-label{display:flex;align-items:center;gap:7px;padding:0 6px;font-weight:700}.cube-tabs :deep(.el-tabs__header){margin-bottom:18px}.cube-tabs :deep(.el-tabs__nav-wrap::after){height:1px;background:#dbe7f5}.cube-tabs :deep(.el-tabs__active-bar){height:3px;border-radius:3px;background:linear-gradient(90deg,#2563eb,#0ea5e9)}
@keyframes cubeIn{from{opacity:0;transform:translateY(10px)}}@media(max-width:768px){.cube-hero{align-items:flex-start;flex-direction:column;min-height:145px;padding:20px}.cube-hero h1{font-size:24px}.cube-tabs :deep(.el-tabs__item){padding:0 10px;font-size:12px}.tab-label{gap:4px}}@media(max-width:480px){.hero-badges{display:none}.cube-hero{min-height:128px}.cube-hero h1{font-size:21px}}
</style>
