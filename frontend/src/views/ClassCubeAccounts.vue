<template>
  <div class="cube-subpage"><el-card><template #header><div class="page-head"><span>账号管理</span><el-button type="primary" @click="openQrLogin">微信扫码添加账号</el-button></div></template>
    <AccountCheckinPanel :accounts="accounts" :courses="courses" :items="items" :tasks="tasks" :selected-account-id="selectedAccountId" :selected-course-id="selectedCourseId" :selected-item-id="selectedItemId" :selected-course="selectedCourse" :selected-item="selectedItem" :courses-loading="coursesLoading" :items-loading="itemsLoading" :manual-checkin-action="manualCheckin" :batch-delete-accounts-action="removeAccounts" @qr-login="openQrLogin" @select-account="selectAccount" @select-course="selectCourse" @select-item="value => selectedItemId = value" @sync-courses="syncCourses" @sync-items="syncItems" @rename-account="renameAccount" @delete-account="removeAccount" />
  </el-card><QrLoginDialog v-model="qrVisible" :session="qrSession" :qr-remaining-seconds="qrRemainingSeconds" :loading="qrLoading" @regenerate="regenerateQr" /></div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AccountCheckinPanel from '../components/class-cube/AccountCheckinPanel.vue'
import QrLoginDialog from '../components/class-cube/QrLoginDialog.vue'
import { useClassCube } from '../composables/useClassCube.js'
const cube = useClassCube(); const { accounts,courses,items,tasks,selectedAccountId,selectedCourseId,selectedItemId,selectedCourse,selectedItem,coursesLoading,itemsLoading,qrSession,qrRemainingSeconds,manualCheckin,selectAccount,selectCourse,syncCourses,syncItems,updateAccount,deleteAccount,deleteAccounts,loadAccounts,loadTasks,loadRuns,loadInitial,startQrLogin } = cube
const qrVisible=ref(false); const qrLoading=ref(false); const qrAccountId=ref(null)
async function safely(action){try{return await action()}catch(e){ElMessage.error(e.message||'操作失败');return null}}
async function renameAccount(id,name){if(await safely(()=>updateAccount(id,{name}))) await loadAccounts()}
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
</script>
<style scoped>.cube-subpage{display:grid;gap:18px}.page-head{display:flex;justify-content:space-between;align-items:center;font-weight:700}</style>
