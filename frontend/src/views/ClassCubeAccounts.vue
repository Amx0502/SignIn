<template>
  <div class="cube-subpage"><el-card><template #header><div class="page-head"><span>账号管理</span><el-button type="primary" @click="openQrLogin">微信扫码添加账号</el-button></div></template>
    <AccountCheckinPanel :accounts="accounts" :courses="courses" :items="items" :tasks="tasks" :batch-targets="batchTargets" :selected-account-id="selectedAccountId" :selected-course-id="selectedCourseId" :selected-item-id="selectedItemId" :selected-course="selectedCourse" :selected-item="selectedItem" :courses-loading="coursesLoading" :items-loading="itemsLoading" :items-syncing="itemsSyncing" :is-admin="isAdmin" :manual-checkin-action="manualCheckinAndSync" :batch-checkin-action="batchCheckin" :sync-class-items-action="syncClassItemsAndRefresh" :sync-all-accounts-action="syncAllAccountsAndRefresh" :upload-photo-action="uploadPhoto" :batch-delete-accounts-action="removeAccounts" @qr-login="openQrLogin" @select-account="selectAccount" @select-course="selectCourse" @select-item="value => selectedItemId = value" @sync-courses="syncCourses" @sync-items="handleSyncItems" @rename-account="renameAccount" @delete-account="removeAccount" />
  </el-card><QrLoginDialog v-model="qrVisible" :session="qrSession" :qr-remaining-seconds="qrRemainingSeconds" :loading="qrLoading" @regenerate="regenerateQr" /></div>
</template>
<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AccountCheckinPanel from '../components/class-cube/AccountCheckinPanel.vue'
import QrLoginDialog from '../components/class-cube/QrLoginDialog.vue'
import { useClassCube } from '../composables/useClassCube.js'
import { syncAfterManualCheckin } from '../utils/classCubeCheckin.js'
const cube = useClassCube(); const { accounts,courses,items,tasks,batchTargets,selectedAccountId,selectedCourseId,selectedItemId,selectedCourse,selectedItem,coursesLoading,itemsLoading,itemsSyncing,qrSession,qrRemainingSeconds,manualCheckin,batchCheckin,syncClassItems,syncAllAccountItems,loadBatchTargets,loadItems,uploadPhoto,selectAccount,selectCourse,syncCourses,syncItems,updateAccount,deleteAccount,deleteAccounts,loadAccounts,loadTasks,loadRuns,loadInitial,startQrLogin } = cube
const isAdmin = JSON.parse(localStorage.getItem('user') || '{}')?.role === 'admin'
const qrVisible=ref(false); const qrLoading=ref(false); const qrAccountId=ref(null)
async function syncClassItemsAndRefresh(courseId) {
  const summary = await syncClassItems(courseId)
  await loadItems(selectedCourseId.value)
  return summary
}
async function syncAllAccountsAndRefresh() {
  const summary = await syncAllAccountItems()
  await Promise.all([loadAccounts(), selectedCourseId.value ? syncItems(selectedCourseId.value) : Promise.resolve([])])
  ElMessage.success(`已同步 ${summary.success} 个课程，失败 ${summary.failed} 个`)
  return summary
}
async function manualCheckinAndSync(itemId, payload) {
  const result = await manualCheckin(itemId, payload)
  try {
    return await syncAfterManualCheckin(
      result,
      () => syncItems(selectedCourseId.value),
    )
  } catch (error) {
    ElMessage.warning('签到已完成，但签到项同步失败，请稍后手动同步')
    return result
  }
}
async function safely(action){try{return await action()}catch(e){ElMessage.error(e.message||'操作失败');return null}}
async function renameAccount(id,name){if(await safely(()=>updateAccount(id,{name}))) await loadAccounts()}
async function handleSyncItems(courseId){
  const synced=await safely(()=>syncItems(courseId))
  if(synced===null) return
  ElMessage.success(`已同步 ${synced.length} 个签到项`)
}
async function refreshAfterAccountDelete(){
  await Promise.all([loadAccounts(),loadTasks(),loadRuns()])
  await selectAccount(selectedAccountId.value)
}
async function removeAccount(id){
  if(await safely(()=>deleteAccount(id))) await refreshAfterAccountDelete()
}
async function removeAccounts(ids){
  const deleted=await safely(()=>deleteAccounts(ids))
  if(deleted===null) return false
  await refreshAfterAccountDelete()
  ElMessage.success(`已删除 ${deleted} 个账号`)
  return true
}
async function openQrLogin(id=null){qrAccountId.value=id;qrVisible.value=true;await regenerateQr()}
async function regenerateQr(){qrLoading.value=true;try{await startQrLogin(qrAccountId.value)}catch(e){ElMessage.error(e.message||'二维码生成失败')}finally{qrLoading.value=false}}
onMounted(()=>loadInitial().catch(()=>{}))
watch(() => [selectedItemId.value, selectedItem.value?.mode], ([value, mode]) => {
  if (isAdmin && ['qr', 'password', 'gps'].includes(mode)) loadBatchTargets(value).catch(() => {})
  else batchTargets.value = []
}, { immediate: true })
</script>
<style scoped>.cube-subpage{display:grid;gap:18px}.page-head{display:flex;justify-content:space-between;align-items:center;font-weight:700}</style>
