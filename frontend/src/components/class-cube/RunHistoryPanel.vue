<template>
  <el-card class="run-panel" shadow="never">
    <template #header>
      <div class="panel-head"><div><strong>签到运行记录</strong><small>包含自动任务与课程签到中心的严格结果记录</small></div><el-button :icon="Refresh" @click="applyFilters">刷新记录</el-button></div>
    </template>
    <div class="filters">
      <el-input-number v-if="isAdmin" v-model="filters.owner_user_id" :min="1" :controls="false" placeholder="后台用户 ID" aria-label="后台用户 ID" />
      <el-select v-model="filters.account_id" clearable placeholder="全部账号"><el-option v-for="row in accounts" :key="row.id" :value="row.id" :label="row.name || row.remote_user_name" /></el-select>
      <el-select v-model="filters.course_id" clearable placeholder="全部课程"><el-option v-for="row in courses" :key="row.id" :value="row.id" :label="row.name" /></el-select>
      <el-select v-model="filters.task_id" clearable placeholder="全部任务"><el-option v-for="row in tasks" :key="row.id" :value="row.id" :label="row.name" /></el-select>
      <el-select v-model="filters.status" clearable placeholder="全部状态"><el-option v-for="(meta, status) in statuses" :key="status" :value="status" :label="meta.label" /></el-select>
      <el-button type="primary" @click="applyFilters">筛选</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>
    <div class="run-list">
      <article v-for="run in runs" :key="run.id" class="run-row">
        <span class="run-mark" :class="run.status"><el-icon><component :is="statusMeta(run.status).icon" /></el-icon></span>
        <div class="run-main">
          <div><strong>{{ taskName(run) }}</strong><el-tag :type="statusMeta(run.status).type" size="small">{{ statusMeta(run.status).label }}</el-tag></div>
          <p>{{ run.message || statusMeta(run.status).tip }}</p>
          <small>{{ formatTime(run.started_at) }} · {{ modeName(run.mode) }} · 签到项 {{ run.remote_item_id }}</small>
          <code v-if="run.response_summary?.photo_res" class="photo-res">res: {{ run.response_summary.photo_res }}</code>
        </div>
        <el-button v-if="run.status === 'unknown_result' && run.claim_id" type="warning" plain @click="confirmRetry(run)">确认重试</el-button>
      </article>
      <el-empty v-if="!runs.length" description="暂无符合条件的运行记录" :image-size="90" />
    </div>
  </el-card>
</template>

<script setup>
import { reactive } from 'vue'
import { CircleCheckFilled, CircleCloseFilled, Clock, Refresh, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  runs: { type: Array, default: () => [] }, tasks: { type: Array, default: () => [] },
  accounts: { type: Array, default: () => [] }, courses: { type: Array, default: () => [] },
  isAdmin: { type: Boolean, default: false }, loadRunsAction: { type: Function, required: true },
  retryClaimAction: { type: Function, required: true },
})
const statuses = {
  success: { label:'成功',type:'success',icon:CircleCheckFilled,tip:'签到成功' },
  already_signed: { label:'已签到',type:'success',icon:CircleCheckFilled,tip:'已经完成签到' },
  waiting_parameter: { label:'等待参数',type:'warning',icon:Clock,tip:'等待补充位置、照片或密码' },
  unknown_result: { label:'结果未知',type:'warning',icon:WarningFilled,tip:'需要人工确认后才能重试' },
  failed: { label:'失败',type:'danger',icon:CircleCloseFilled,tip:'签到执行失败' },
  skipped: { label:'已跳过',type:'info',icon:Clock,tip:'本轮未提交' },
}
const filters = reactive({ owner_user_id:null, account_id:null, course_id:null, task_id:null, status:'' })
function statusMeta(status){return statuses[status]||statuses.failed}
function taskName(run){if(run.source==='course_manual')return '课程手动签到';return props.tasks.find(row=>row.id===run.task_id)?.name||`任务 ${run.task_id}`}
function modeName(mode){return {qr:'二维码签到',gps:'GPS 签到',gps_photo:'GPS+拍照签到',password:'密码签到'}[mode]||mode||'未知类型'}
function formatTime(value){return value?new Date(value).toLocaleString('zh-CN',{hour12:false}):'—'}
function filterPayload(){return Object.fromEntries(Object.entries(filters).filter(([key,value])=>value!==null&&value!==''&&(props.isAdmin||key!=='owner_user_id')))}
async function applyFilters(){try{await props.loadRunsAction(filterPayload())}catch(error){ElMessage.error(error.message||'加载运行记录失败')}}
function resetFilters(){Object.assign(filters,{owner_user_id:null,account_id:null,course_id:null,task_id:null,status:''});applyFilters()}
async function confirmRetry(run){
  try{await ElMessageBox.confirm('该操作仅解除未知结果保护，不代表上次签到失败。确认允许任务再次尝试？','确认重试',{type:'warning'});await props.retryClaimAction(run.claim_id);await applyFilters();ElMessage.success('已允许再次尝试')}
  catch(error){if(!['cancel','close'].includes(error))ElMessage.error(error.message||'确认失败')}
}
</script>

<style scoped>
.run-panel{border:1px solid rgb(191 219 254 / 58%);border-radius:22px;background:rgb(255 255 255 / 84%);box-shadow:0 18px 42px rgb(15 23 42 / 7%);backdrop-filter:blur(18px)}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.panel-head strong,.panel-head small{display:block}.panel-head small{margin-top:4px;color:#64748b;font-size:11px}.filters{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr)) auto auto;gap:10px;margin-bottom:18px}.filters .el-input-number{width:100%}.run-list{display:grid;gap:10px;max-height:650px;overflow:auto}.run-row{display:flex;align-items:center;gap:13px;padding:15px;border:1px solid #e2e8f0;border-radius:17px;background:linear-gradient(145deg,#fff,#f8fafc)}.run-mark{display:grid;width:44px;height:44px;flex:none;place-items:center;color:#64748b;border-radius:14px;background:#e2e8f0;font-size:21px}.run-mark.success,.run-mark.already_signed{color:#059669;background:#d1fae5}.run-mark.waiting_parameter,.run-mark.unknown_result{color:#d97706;background:#fef3c7}.run-mark.failed{color:#dc2626;background:#fee2e2}.run-main{min-width:0;flex:1}.run-main>div{display:flex;align-items:center;gap:8px}.run-main p{margin:6px 0;color:#475569;font-size:13px;line-height:1.5}.run-main small{color:#64748b;font-size:11px}.photo-res{display:block;max-width:100%;margin-top:7px;overflow-wrap:anywhere;color:#2563eb;font-size:11px;white-space:pre-wrap}
@media(max-width:1100px){.filters{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.panel-head,.run-row{align-items:stretch;flex-direction:column}.filters{grid-template-columns:1fr 1fr}.filters .el-button{width:100%}.run-mark{width:38px;height:38px}}
</style>
