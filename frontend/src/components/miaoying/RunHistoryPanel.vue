<template>
  <el-card class="run-panel" shadow="never">
    <template #header>
      <div class="panel-head">
        <div><strong>签到运行记录</strong><small>包含自动任务与账号管理中的手动签到结果，可展开查看提交字段</small></div>
        <el-button :icon="Refresh" :loading="loading" @click="emit('refresh')">刷新记录</el-button>
      </div>
    </template>
    <div class="filters">
      <el-select v-model="filters.account_id" clearable placeholder="全部账号"><el-option v-for="row in accounts" :key="row.id" :value="row.id" :label="row.remark || row.nickname" /></el-select>
      <el-select v-model="filters.form_id" clearable placeholder="全部签到项目"><el-option v-for="row in forms" :key="row.id" :value="row.id" :label="row.title" /></el-select>
      <el-select v-model="filters.task_id" clearable placeholder="全部任务"><el-option v-for="row in tasks" :key="row.id" :value="row.id" :label="row.name" /></el-select>
      <el-select v-model="filters.status" clearable placeholder="全部状态"><el-option label="成功" value="success" /><el-option label="失败" value="failed" /><el-option label="已跳过" value="skipped" /></el-select>
      <el-button type="primary" @click="applyFilters">筛选</el-button><el-button @click="resetFilters">重置</el-button>
    </div>
    <div class="run-list">
      <article v-for="run in filteredRuns" :key="run.id" class="run-row">
        <span class="run-mark" :class="run.status"><el-icon><component :is="statusMeta(run.status).icon" /></el-icon></span>
        <div class="run-main">
          <div class="run-title"><strong>{{ taskName(run) }}</strong><span class="run-account">{{ accountName(run.account_id) }}</span><el-tag :type="statusMeta(run.status).type" size="small">{{ statusMeta(run.status).label }}</el-tag></div>
          <p>{{ run.message || statusMeta(run.status).tip }}</p>
          <small>{{ formatTime(run.started_at) }} · {{ triggerName(run.trigger) }} · {{ formName(run.form_id) }}</small>
          <details v-if="details" class="audit-details">
            <summary>查看提交字段</summary>
            <div class="audit-grid">
              <span><b>上游操作</b>{{ run.request_summary?.operation || run.operation || 'createBaomingByInput' }}</span>
              <span><b>项目 ID</b>{{ run.request_summary?.tongji_id || '—' }}</span>
              <span><b>秒应记录 ID</b>{{ run.remote_submission_id || '未返回' }}</span>
              <span><b>经纬度</b>{{ coordinate(run.request_summary?.location_info) }}</span>
              <span><b>省 / 市 / 区</b>{{ administrativeArea(run.request_summary?.location_info) }}</span>
              <span><b>街道 / 地点</b>{{ locationLabel(run.request_summary?.location_info) }}</span>
            </div>
          </details>
        </div>
      </article>
      <el-empty v-if="!filteredRuns.length" description="暂无符合条件的运行记录" :image-size="90" />
    </div>
  </el-card>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { CircleCheckFilled, CircleCloseFilled, Clock, Refresh } from '@element-plus/icons-vue'

const props=defineProps({runs:{type:Array,default:()=>[]},tasks:{type:Array,default:()=>[]},accounts:{type:Array,default:()=>[]},forms:{type:Array,default:()=>[]},details:{type:Boolean,default:false},loading:{type:Boolean,default:false}})
const emit=defineEmits(['refresh'])
const filters=reactive({account_id:null,form_id:null,task_id:null,status:''})
const applied=ref({...filters})
const statuses={success:{label:'成功',type:'success',icon:CircleCheckFilled,tip:'签到成功'},failed:{label:'失败',type:'danger',icon:CircleCloseFilled,tip:'签到执行失败'},skipped:{label:'已跳过',type:'info',icon:Clock,tip:'本轮未提交'}}
const filteredRuns=computed(()=>props.runs.filter(run=>Object.entries(applied.value).every(([key,value])=>value===null||value===''||run[key]===value)))
const statusMeta=status=>statuses[status]||statuses.failed
const taskName=run=>!run.task_id?'账号手动签到':props.tasks.find(row=>row.id===run.task_id)?.name||`任务 ${run.task_id}`
const accountName=id=>{const row=props.accounts.find(item=>item.id===id);return row?.remark||row?.nickname||`账号 ${id}`}
const formName=id=>props.forms.find(item=>item.id===id)?.title||`签到项目 ${id}`
const triggerName=value=>value==='manual'?'手动执行':'定时自动执行'
const formatTime=value=>value?new Date(value).toLocaleString('zh-CN',{hour12:false}):'—'
const coordinate=location=>location?.lattitude!=null&&location?.longtitude!=null?`${location.lattitude}, ${location.longtitude}`:'未提交'
const administrativeArea=location=>[location?.province,location?.city,location?.district].filter(Boolean).join(' / ')||'未填写'
const locationLabel=location=>[location?.street,location?.name].filter(Boolean).join(' / ')||'未填写'
function applyFilters(){applied.value={...filters}}
function resetFilters(){Object.assign(filters,{account_id:null,form_id:null,task_id:null,status:''});applyFilters()}
</script>

<style scoped>
.run-panel{border:1px solid rgb(191 219 254 / 58%);border-radius:22px;background:rgb(255 255 255 / 84%);box-shadow:0 18px 42px rgb(15 23 42 / 7%);backdrop-filter:blur(18px)}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.panel-head strong,.panel-head small{display:block}.panel-head small{margin-top:4px;color:#64748b;font-size:11px}.filters{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr)) auto auto;gap:10px;margin-bottom:18px}.filters .el-button+.el-button{margin-left:0}.run-list{display:grid;gap:10px;max-height:680px;overflow:auto}.run-row{display:flex;align-items:flex-start;gap:13px;padding:15px;border:1px solid #e2e8f0;border-radius:17px;background:linear-gradient(145deg,#fff,#f8fafc)}.run-mark{display:grid;width:44px;height:44px;flex:none;place-items:center;color:#64748b;border-radius:14px;background:#e2e8f0;font-size:21px}.run-mark.success{color:#059669;background:#d1fae5}.run-mark.failed{color:#dc2626;background:#fee2e2}.run-main{min-width:0;flex:1}.run-title{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.run-account{color:#2563eb;font-size:12px;font-weight:600}.run-main p{margin:6px 0;color:#475569;font-size:13px;line-height:1.5}.run-main>small{color:#64748b;font-size:11px}.audit-details{margin-top:11px;border-top:1px dashed #cbd5e1;padding-top:9px}.audit-details summary{width:max-content;color:#2563eb;font-size:12px;cursor:pointer}.audit-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:10px}.audit-grid span{display:grid;gap:3px;min-width:0;padding:9px 10px;border-radius:10px;background:#eff6ff;color:#475569;font-size:11px;overflow-wrap:anywhere}.audit-grid b{color:#1e3a8a;font-size:11px}.muted{color:#94a3b8}@media(max-width:1100px){.filters,.audit-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.panel-head,.run-row{align-items:stretch;flex-direction:column}.filters,.audit-grid{grid-template-columns:1fr 1fr}.filters .el-button{width:100%}.run-mark{width:38px;height:38px}}
</style>
