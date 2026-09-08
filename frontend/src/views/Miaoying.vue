<template>
  <div class="my-page" v-loading="loading">
    <template v-if="isOverview">
      <div class="metrics">
        <article><b>{{ accounts.length }}</b><span>登录账号</span></article><article><b>{{ tasks.length }}</b><span>全部任务</span></article>
        <article><b>{{ tasks.filter(v => v.enabled).length }}</b><span>启用任务</span></article><article><b>{{ runs.filter(v => v.status === 'success').length }}</b><span>成功执行</span></article>
      </div>
      <section class="panel settings-panel">
        <header><div><h2>企业微信机器人通知</h2><p>配置秒应签到结果通知，与小小签到和班级魔方相互独立。</p></div><el-tag :type="settings.webhook_configured ? 'success' : 'info'">{{ settings.webhook_configured ? '已配置' : '未配置' }}</el-tag></header>
        <el-form v-if="isAdmin" label-position="top">
          <el-form-item label="机器人 Webhook"><el-input v-model="settings.miaoying_webhook_url" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." /></el-form-item>
          <el-button type="primary" :loading="settingsSaving" @click="saveSettings">保存配置</el-button>
        </el-form>
        <el-alert v-else :closable="false" :type="settings.webhook_configured ? 'success' : 'info'" :title="settings.webhook_configured ? '管理员已配置企业微信机器人' : '管理员尚未配置企业微信机器人'" />
      </section>
    </template>

    <section v-else-if="isAccounts" class="accounts-workspace">
      <div class="panel accounts-pane">
        <header><div><h2>秒应账号</h2><p>微信扫码登录并管理签到资料</p></div><el-button type="primary" @click="openQr">扫码添加</el-button></header>
        <div v-if="accounts.length" class="account-search"><el-input v-model="keyword" clearable placeholder="搜索昵称、备注或用户 ID" :prefix-icon="Search" /><span>显示 {{ filteredAccounts.length }}/{{ accounts.length }}</span></div>
        <div v-if="filteredAccounts.length" class="account-list">
          <article v-for="item in filteredAccounts" :key="item.id" class="account-card" :class="{ active: item.id === selectedAccountId }" @click="selectAccount(item.id)">
            <div class="avatar">{{ (item.remark || item.nickname || '秒').slice(0,1) }}</div>
            <div class="account-info"><b>{{ item.remark || item.nickname }}</b><span>{{ item.nickname }} · UID {{ item.remote_user_id }}</span></div>
            <el-tag :type="item.status === 'active' ? 'success' : 'danger'">{{ item.status === 'active' ? '有效' : '需重登' }}</el-tag>
            <el-dropdown trigger="click" @command="command => accountCommand(command,item)" @click.stop><el-button text>•••</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="rescan">重新扫码</el-dropdown-item><el-dropdown-item command="rename">编辑备注</el-dropdown-item><el-dropdown-item command="sync">同步项目</el-dropdown-item><el-dropdown-item command="delete" divided>删除账号</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
          </article>
        </div><el-empty v-else :description="accounts.length ? '没有找到匹配账号' : '暂无账号，请先扫码登录'" />
      </div>
      <div class="panel checkin-pane">
        <header><div><h2>签到中心</h2><p>选择签到项目后可直接地图选点并提交</p></div><el-button :icon="Refresh" :disabled="!selectedAccountId" :loading="formsSyncing" @click="syncAccountForms">同步签到项目</el-button></header>
        <div class="project-picker">
          <span>签到项目</span>
          <el-select v-model="selectedFormId" class="form-select" :disabled="!selectedAccountId" placeholder="请选择签到项目">
            <el-option-group v-if="activeAccountForms.length" label="可签到项目">
              <el-option v-for="item in activeAccountForms" :key="item.id" :value="item.id" :label="item.title"><span>{{ item.title }}</span><small class="option-state">{{ item.requirements?.location ? '需要位置' : '普通签到' }}</small></el-option>
            </el-option-group>
            <el-option-group v-if="closedAccountForms.length" label="已关闭项目">
              <el-option v-for="item in closedAccountForms" :key="item.id" :value="item.id" :label="item.title"><span>{{ item.title }}</span><small class="option-state">已关闭</small></el-option>
            </el-option-group>
          </el-select>
        </div>
        <el-empty v-if="!selectedAccountId" description="请先选择秒应账号" />
        <el-empty v-else-if="!accountForms.length" description="暂无签到项目，请点击同步签到项目" />
        <div v-else-if="selectedManualForm" class="manual-checkin">
          <div class="manual-head"><div><el-tag size="small" type="primary">{{ selectedManualForm.requirements?.location ? '位置签到' : '普通签到' }}</el-tag><strong>{{ selectedManualForm.title }}</strong></div><small>{{ selectedManualForm.content || '按项目要求提交签到' }}</small></div>
          <el-alert v-if="selectedManualForm.is_closed" type="warning" :closable="false" title="该签到项目已关闭" />
          <el-alert v-else-if="selectedManualForm.requirements?.unsupported?.length" type="warning" :closable="false" :title="`暂不支持：${selectedManualForm.requirements.unsupported.join('、')}`" />
          <RosterIdentity v-if="identityLabels.fixed" v-model="manualAnswers" :identity="identityLabels" />
          <div v-else class="identity-fields">
            <div class="identity-title"><div><strong>签到身份</strong><small>保存到当前账号，并作为签到默认资料</small></div><el-button :loading="profileSaving" @click="saveManualProfile()">保存资料</el-button></div>
            <div class="identity-grid">
              <label><span>班级</span><el-input v-model="manualProfile.class_name" clearable placeholder="请输入班级" /></label>
              <label><span>{{ identityLabels.name_label }}</span><el-input v-model="manualProfile.real_name" clearable :placeholder="`请输入${identityLabels.name_label}`" /></label>
              <label><span>{{ identityLabels.number_label }}</span><el-input v-model="manualProfile.school_no" clearable :placeholder="`请输入${identityLabels.number_label}`" /></label>
            </div>
          </div>
          <DynamicFormFields v-if="manualFields.length" v-model="manualAnswers" :fields="manualFields" />
          <section v-if="selectedManualForm.requirements?.location" class="location-section">
            <div class="section-heading"><div><strong>签到位置</strong><small>搜索地点或直接在腾讯地图上选点</small></div><el-tag size="small" type="primary">腾讯地图</el-tag></div>
            <el-alert
              v-if="selectedManualForm.requirements?.location_detail_visible === false"
              type="info"
              :closable="false"
              title="该项目的原生位置只公开省、市；系统会把完整地址和经纬度作为“打卡实时位置（详细）”一并提交。"
            />
            <div class="location-editor">
              <el-input v-model="manualLocationName" clearable maxlength="255" show-word-limit placeholder="位置名称，例如：教学楼、宿舍楼或图书馆" />
              <LocationSearchPanel v-model="manualCoordinate" :location-api="api" @select-location="selectManualLocation" />
            </div>
          </section>
          <div class="manual-actions"><div><el-checkbox v-model="manualNotify">发送企业微信通知</el-checkbox><small>提交前会按最终坐标重新识别完整位置</small></div><el-button type="primary" size="large" :loading="manualChecking" :disabled="!canManualCheckin" @click="submitManualCheckin">执行签到</el-button></div>
        </div>
      </div>
    </section>

    <section v-else-if="isAuto || isTasks" class="panel task-panel">
      <header class="task-panel-head">
        <div><h2>自动签到任务</h2><p>集中创建、编辑和执行秒应自动签到任务</p></div>
        <div class="task-panel-actions"><el-input v-model="keyword" clearable placeholder="搜索任务" :prefix-icon="Search" /><el-button type="primary" :icon="Plus" @click="openCreateTask">新增任务</el-button></div>
      </header>
      <el-table :data="filteredTasks" row-key="id" stripe>
        <el-table-column label="任务" min-width="190"><template #default="{row}"><div class="task-cell"><strong>{{ row.name }}</strong><small>{{ (row.schedule_times || []).join('、') || '未设置时间' }}</small><small>{{ schedulePlanSummary(row) }}</small></div></template></el-table-column>
        <el-table-column label="账号 / 签到项目" min-width="210"><template #default="{row}"><div class="task-cell"><span>{{ taskAccountName(row.account_id) }}</span><small>{{ taskFormName(row.form_id) }}</small></div></template></el-table-column>
        <el-table-column label="预设参数" min-width="180"><template #default="{row}"><el-space wrap><el-tag v-if="row.latitude != null && row.longitude != null" size="small" type="primary">位置</el-tag><el-tag v-if="row.answers?.__identity" size="small" type="success">名单身份</el-tag><el-tag v-if="(row.answer_schema || []).length" size="small" type="info">填写项 {{ row.answer_schema.length }}</el-tag><span v-if="row.latitude == null && !row.answers?.__identity && !(row.answer_schema || []).length" class="muted">无</span></el-space></template></el-table-column>
        <el-table-column label="状态" width="92"><template #default="{row}"><el-switch :model-value="row.enabled" inline-prompt active-text="启" inactive-text="停" @change="value => toggleTask(row, value)" /></template></el-table-column>
        <el-table-column label="最近更新" min-width="165"><template #default="{row}"><span class="muted">{{ format(row.updated_at) }}</span></template></el-table-column>
        <el-table-column label="操作" width="230" fixed="right"><template #default="{row}"><el-button link type="primary" @click="editTask(row)">编辑</el-button><el-button link type="success" :loading="runningTaskId === row.id" :disabled="runningTaskId !== null && runningTaskId !== row.id" @click="runNow(row)">立即执行</el-button><el-button link type="danger" @click="removeTask(row)">删除</el-button></template></el-table-column>
        <template #empty><el-empty description="暂无自动任务，点击右上角新增任务" :image-size="90" /></template>
      </el-table>
    </section>

    <div v-else-if="isLogs" class="miaoying-log-page"><LogConsole title="秒应日志" empty-text="暂无秒应日志" :logs="miaoyingLogEntries" :loading="loading" @refresh="load" /></div>
    <MiaoyingRunHistoryPanel v-else :runs="runs" :tasks="tasks" :accounts="accounts" :forms="taskForms" details :loading="loading" @refresh="load" />

    <QrLoginDialog
      v-model="qrVisible"
      :session="miaoyingQrSession"
      :qr-remaining-seconds="qrRemainingSeconds"
      :loading="qrLoading"
      :countdown-total-seconds="120"
      title="微信扫码登录"
      subtitle="使用秒应绑定的微信扫码"
      image-alt="秒应微信登录二维码"
      @regenerate="openQr"
      @update:model-value="value => { if (!value) stopQr() }"
    />

    <el-dialog v-model="taskEditorVisible" :title="editingId ? '编辑自动任务' : '新增自动任务'" width="min(1180px, 96vw)" class="miaoying-task-dialog" align-center append-to-body :close-on-click-modal="false" @closed="resetForm">
      <el-form label-position="top" class="task-editor-form">
        <div class="task-editor-layout">
          <section class="task-editor-section">
            <header><span class="section-index">01</span><div><strong>基本信息</strong><small>选择账号及秒应签到项目</small></div></header>
            <el-form-item label="任务名称" required><el-input v-model="form.name" maxlength="255" placeholder="例如：每日健康签到" /></el-form-item>
            <el-form-item label="秒应账号" required><el-select v-model="form.account_id" filterable placeholder="请选择账号" @change="accountChanged"><el-option v-for="account in accounts" :key="account.id" :label="account.remark || account.nickname" :value="account.id" /></el-select></el-form-item>
            <el-form-item label="签到项目" required>
              <div class="project-select-row"><el-select v-model="form.form_id" filterable placeholder="请选择签到项目" :disabled="!form.account_id" @change="taskFormChanged"><el-option-group v-if="activeTaskForms.length" label="可签到项目"><el-option v-for="item in activeTaskForms" :key="item.id" :label="item.title" :value="item.id" /></el-option-group><el-option-group v-if="closedTaskForms.length" label="已关闭项目"><el-option v-for="item in closedTaskForms" :key="item.id" :label="item.title" :value="item.id" disabled /></el-option-group></el-select><el-button :icon="Refresh" :disabled="!form.account_id" :loading="formsSyncing" @click="syncSelected">同步项目</el-button></div>
            </el-form-item>
            <el-alert v-if="selectedTaskForm?.is_closed" type="warning" :closable="false" title="该签到项目已关闭，请选择其他项目" />
            <el-alert v-else-if="selectedTaskForm?.requirements?.unsupported?.length" type="warning" :closable="false" :title="`暂不支持：${selectedTaskForm.requirements.unsupported.join('、')}`" />
          </section>

          <section class="task-editor-section">
            <header><span class="section-index">03</span><div><strong>执行策略</strong><small>设置执行时间、日期范围与启用状态</small></div></header>
            <el-form-item label="每日执行时间" required><div class="schedule-list"><div v-for="(_, index) in form.schedule_times" :key="index" class="schedule-row"><el-time-picker v-model="form.schedule_times[index]" value-format="HH:mm:ss" format="HH:mm:ss" placeholder="执行时间" /><el-button type="danger" plain :disabled="form.schedule_times.length === 1" @click="form.schedule_times.splice(index, 1)">删除</el-button></div><el-button plain @click="form.schedule_times.push('08:00:00')">添加执行时间</el-button></div></el-form-item>
            <el-form-item label="执行日期计划"><div class="date-plan-card"><div><el-space wrap><el-tag size="small" type="primary">{{ form.date_mode === 'specific' ? '指定日期' : '每天执行' }}</el-tag><el-tag v-if="form.skip_weekends" size="small" type="info">周末跳过</el-tag><el-tag v-if="form.auto_disable_after_finish && form.date_mode === 'specific'" size="small" type="success">结束后关闭</el-tag></el-space><strong>{{ schedulePlanSummary(form) }}</strong></div><el-button type="primary" plain @click="openScheduleDrawer">设置签到日期</el-button></div></el-form-item>
            <div class="task-enable-box"><el-checkbox v-model="form.enabled">保存后立即启用</el-checkbox><small>执行结果将按系统概览中的企业微信机器人配置发送通知</small></div>
          </section>

          <section class="task-editor-section task-editor-section--wide">
            <header><span class="section-index">02</span><div><strong>签到参数</strong><small>名单、动态填写项与位置均跟随所选项目</small></div></header>
            <el-empty v-if="!selectedTaskForm" description="请先选择签到项目" :image-size="70" />
            <template v-else>
              <RosterIdentity v-if="selectedTaskForm.requirements?.identity?.fixed" v-model="form.answers" :identity="selectedTaskForm.requirements.identity" />
              <DynamicFormFields v-if="taskFields.length" v-model="form.answers" :fields="taskFields" />
              <section v-if="selectedTaskForm.requirements?.location" class="task-location-section"><div class="section-heading"><div><strong>签到位置</strong><small>搜索地点或直接在腾讯地图上选点</small></div><el-tag size="small" type="primary">腾讯地图</el-tag></div><el-input v-model="form.location_name" clearable maxlength="255" show-word-limit placeholder="位置名称，例如：教学楼、宿舍楼或图书馆" /><LocationSearchPanel v-model="taskCoordinate" :location-api="api" @select-location="selectTaskLocation" /></section>
              <el-alert v-if="!selectedTaskForm.requirements?.identity?.fixed && !taskFields.length && !selectedTaskForm.requirements?.location" type="info" :closable="false" title="该项目没有需要预设的签到参数" />
            </template>
          </section>
        </div>
      </el-form>
      <template #footer><el-button @click="taskEditorVisible = false">取消</el-button><el-button type="primary" :loading="taskSaving" @click="saveTask">保存任务</el-button></template>
    </el-dialog>

    <el-drawer v-model="scheduleDrawerVisible" title="设置签到日期计划" size="min(760px, 100vw)" append-to-body :close-on-click-modal="false" class="miaoying-schedule-drawer">
      <div class="schedule-drawer-body"><div class="schedule-drawer-intro"><strong>控制具体哪天执行或跳过</strong><small>指定日期、排除日期和周末策略会保存到当前秒应任务。</small></div><TaskDateSchedule v-model:date-mode="scheduleDraft.date_mode" v-model:run-dates="scheduleDraft.run_dates" v-model:skip-dates="scheduleDraft.skip_dates" v-model:skip-weekends="scheduleDraft.skip_weekends" v-model:auto-disable-after-finish="scheduleDraft.auto_disable_after_finish" :times="form.schedule_times" min-date="" max-date="" /></div>
      <template #footer><el-button @click="scheduleDrawerVisible = false">取消</el-button><el-button type="primary" @click="applyScheduleDraft">应用日期计划</el-button></template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import api from '../api/miaoying.js'
import TaskDateSchedule from '../components/TaskDateSchedule.vue'
import LogConsole from '../components/LogConsole.vue'
import DynamicFormFields from '../components/miaoying/DynamicFormFields.vue'
import MiaoyingRunHistoryPanel from '../components/miaoying/RunHistoryPanel.vue'
import RosterIdentity from '../components/miaoying/RosterIdentity.vue'
import QrLoginDialog from '../components/class-cube/QrLoginDialog.vue'
import { normalizeScheduleTimes, parseCoordinates } from '../utils/classCubeTaskForm.js'

const LocationSearchPanel=defineAsyncComponent(()=>import('../components/class-cube/LocationSearchPanel.vue'))

const route=useRoute(),loading=ref(false),keyword=ref(''),accounts=ref([]),forms=ref([]),taskForms=ref([]),tasks=ref([]),runs=ref([])
const qrVisible=ref(false),qrImage=ref(''),qrState=ref('pending'),qrId=ref(''),qrLoading=ref(false),qrRemainingSeconds=ref(0),qrExpiresAt=ref(0);let qrTimer,qrCountdownTimer
const miaoyingQrSession=computed(()=>({status:qrState.value,qrImage:qrImage.value}))
const editingId=ref(null),taskEditorVisible=ref(false),taskSaving=ref(false),runningTaskId=ref(null),scheduleDrawerVisible=ref(false)
const user=JSON.parse(localStorage.getItem('user')||'{}'),isAdmin=computed(()=>user.role==='admin')
const settings=reactive({miaoying_webhook_url:'',webhook_configured:false}),settingsSaving=ref(false)
const selectedAccountId=ref(null),selectedFormId=ref(null),accountForms=ref([]),formsSyncing=ref(false)
const manualCoordinate=ref(''),manualLocationName=ref(''),manualLocationInfo=ref({}),manualNotify=ref(true),manualChecking=ref(false),manualAnswers=ref({}),profileSaving=ref(false)
const manualProfile=reactive({class_name:'',real_name:'',school_no:''})
const emptyForm=()=>({account_id:null,form_id:null,name:'',enabled:true,schedule_times:['08:00:00'],start_date:null,end_date:null,date_mode:'daily',run_dates:[],skip_dates:[],skip_weekends:false,auto_disable_after_finish:true,location_name:'',location_info:{},latitude:null,longitude:null,answers:{},answer_schema:[]})
const form=reactive(emptyForm())
const scheduleDraft=reactive({date_mode:'daily',run_dates:[],skip_dates:[],skip_weekends:false,auto_disable_after_finish:true})
const path=computed(()=>route.path),isOverview=computed(()=>path.value.endsWith('/overview')),isAccounts=computed(()=>path.value.endsWith('/accounts')),isAuto=computed(()=>path.value.endsWith('/auto')),isTasks=computed(()=>path.value.endsWith('/tasks')),isLogs=computed(()=>path.value.endsWith('/logs'))
const filteredAccounts=computed(()=>accounts.value.filter(v=>`${v.nickname}${v.remark}${v.remote_user_id}`.toLowerCase().includes(keyword.value.toLowerCase())))
const filteredTasks=computed(()=>tasks.value.filter(v=>`${v.name}${taskAccountName(v.account_id)}${taskFormName(v.form_id)}`.toLowerCase().includes(keyword.value.toLowerCase())))
const selectedManualForm=computed(()=>accountForms.value.find(item=>item.id===selectedFormId.value)||null)
const selectedAccount=computed(()=>accounts.value.find(item=>item.id===selectedAccountId.value)||null)
const activeAccountForms=computed(()=>accountForms.value.filter(item=>!item.is_closed))
const closedAccountForms=computed(()=>accountForms.value.filter(item=>item.is_closed))
const manualFields=computed(()=>selectedManualForm.value?.requirements?.fields||[])
const identityLabels=computed(()=>selectedManualForm.value?.requirements?.identity||{class_label:'班级',name_label:'姓名',number_label:'学号'})
const selectedTaskForm=computed(()=>forms.value.find(item=>item.id===form.form_id)||null)
const activeTaskForms=computed(()=>forms.value.filter(item=>!item.is_closed))
const closedTaskForms=computed(()=>forms.value.filter(item=>item.is_closed))
const taskFields=computed(()=>selectedTaskForm.value?.requirements?.fields||form.answer_schema||[])
const miaoyingLogEntries=computed(()=>runs.value.map(run=>{const summary=run.request_summary||{},location=summary.location_info||{};const parts=[taskAccountName(run.account_id),taskFormName(run.form_id),run.trigger==='manual'?'手动执行':'定时自动执行',run.message||run.status,`operation=${summary.operation||run.operation||'createBaomingByInput'}`];if(summary.tongji_id)parts.push(`项目ID=${summary.tongji_id}`);if(run.remote_submission_id)parts.push(`秒应记录ID=${run.remote_submission_id}`);if(location.lattitude!=null&&location.longtitude!=null)parts.push(`坐标=${location.lattitude},${location.longtitude}`);if(location.street||location.name)parts.push(`位置=${[location.street,location.name].filter(Boolean).join('-')}`);return`${logTime(run.started_at)} [${run.status==='success'?'INFO':'ERROR'}] ${parts.join(' | ')}`}))
const canManualCheckin=computed(()=>{
  const item=selectedManualForm.value
  if(!item||item.is_closed||item.requirements?.unsupported?.length)return false
  if(identityLabels.value.fixed&&!manualAnswers.value.__identity)return false
  if(!answersValid(manualFields.value,manualAnswers.value))return false
  if(!item.requirements?.location)return true
  try{return Boolean(parseCoordinates(manualCoordinate.value))}catch{return false}
})
const taskCoordinate=computed({
  get:()=>form.latitude==null||form.longitude==null?'':`${form.latitude}, ${form.longitude}`,
  set:value=>{try{const point=parseCoordinates(value);form.latitude=point.latitude;form.longitude=point.longitude;if(form.location_name==='地图选点')form.location_name=''}catch{form.latitude=null;form.longitude=null;if(!String(value||'').trim()&&form.location_name==='地图选点')form.location_name=''}},
})
const format=v=>v?new Date(v).toLocaleString('zh-CN',{hour12:false}):'—'
const logTime=value=>value?new Date(value).toLocaleString('sv-SE',{hour12:false}).replace('T',' '):'0000-00-00 00:00:00'
const taskAccountName=id=>{const row=accounts.value.find(item=>item.id===id);return row?.remark||row?.nickname||`账号 ${id}`}
const taskFormName=id=>taskForms.value.find(item=>item.id===id)?.title||`签到项目 ${id}`
function schedulePlanSummary(plan){const excluded=(plan.skip_dates||[]).length;if((plan.date_mode||'daily')==='daily')return ['每天执行',plan.skip_weekends?'周末跳过':'',excluded?`排除 ${excluded} 天`:''].filter(Boolean).join(' · ');return [`指定 ${(plan.run_dates||[]).length} 天`,plan.auto_disable_after_finish?'结束后关闭':''].filter(Boolean).join(' · ')}
function openScheduleDrawer(){Object.assign(scheduleDraft,{date_mode:form.date_mode||'daily',run_dates:[...(form.run_dates||[])],skip_dates:[...(form.skip_dates||[])],skip_weekends:form.skip_weekends===true,auto_disable_after_finish:form.auto_disable_after_finish===true});scheduleDrawerVisible.value=true}
function applyScheduleDraft(){if(scheduleDraft.date_mode==='specific'&&!scheduleDraft.run_dates.length){ElMessage.warning('指定日期模式下请至少选择一个执行日期');return}Object.assign(form,{...scheduleDraft,run_dates:[...scheduleDraft.run_dates],skip_dates:[...scheduleDraft.skip_dates]});scheduleDrawerVisible.value=false}
async function loadTaskContext(){const groups=await Promise.all(accounts.value.map(account=>api.listForms(account.id).catch(()=>[])));taskForms.value=groups.flat()}
async function loadOptionalRunContext(){const [accountResult,taskResult]=await Promise.allSettled([api.listAccounts(),api.listTasks()]);if(accountResult.status==='fulfilled')accounts.value=accountResult.value;if(taskResult.status==='fulfilled')tasks.value=taskResult.value;await loadTaskContext()}
function auditForRun(run,audits){return audits.find(audit=>run.remote_submission_id&&audit.remote_submission_id===run.remote_submission_id)||audits.find(audit=>audit.task_id===run.task_id&&audit.account_id===run.account_id&&audit.form_id===run.form_id&&Math.abs(new Date(audit.started_at)-new Date(run.started_at))<60000)}
async function load(){loading.value=true;try{if(isAccounts.value){accounts.value=await api.listAccounts();if(!accounts.value.some(item=>item.id===selectedAccountId.value))selectedAccountId.value=accounts.value[0]?.id||null;await loadAccountForms()}else if(isAuto.value||isTasks.value){[accounts.value,tasks.value]=await Promise.all([api.listAccounts(),api.listTasks()]);await loadTaskContext();if(form.account_id)forms.value=await api.listForms(form.account_id)}else if(isOverview.value){[accounts.value,tasks.value,runs.value]=await Promise.all([api.listAccounts(),api.listTasks(),api.listRuns()]);Object.assign(settings,await api.getSettings())}else if(isLogs.value){runs.value=await api.listSubmissionAudits();await loadOptionalRunContext()}else{const [taskRuns,audits]=await Promise.all([api.listRuns(),api.listSubmissionAudits()]);const enriched=taskRuns.map(run=>{const audit=auditForRun(run,audits);return audit?{...run,operation:audit.operation,request_summary:audit.request_summary}:run});runs.value=[...enriched,...audits.filter(item=>!item.task_id)].sort((a,b)=>new Date(b.started_at)-new Date(a.started_at));await loadOptionalRunContext()}}catch(e){ElMessage.error(e.message)}finally{loading.value=false}}
async function openQr(){stopQr();qrVisible.value=true;qrLoading.value=true;qrState.value='pending';try{const data=await api.createQr();qrId.value=data.id;qrImage.value=await QRCode.toDataURL(data.qr_content,{width:440,margin:2,color:{dark:'#000000',light:'#ffffff'}});qrExpiresAt.value=new Date(data.expires_at).getTime();updateQrCountdown();qrCountdownTimer=window.setInterval(updateQrCountdown,1000);scheduleQrPoll(100)}catch(e){qrState.value='error';ElMessage.error(e.message)}finally{qrLoading.value=false}}
function scheduleQrPoll(delay=800){if(qrTimer)window.clearTimeout(qrTimer);qrTimer=window.setTimeout(pollQr,delay)}
function updateQrCountdown(){qrRemainingSeconds.value=Math.max(0,Math.ceil((qrExpiresAt.value-Date.now())/1000));if(qrExpiresAt.value&&qrRemainingSeconds.value===0){qrState.value='expired';clearQrTimers()}}
function clearQrTimers(){if(qrTimer)window.clearTimeout(qrTimer);if(qrCountdownTimer)window.clearInterval(qrCountdownTimer);qrTimer=null;qrCountdownTimer=null}
async function pollQr(){const sessionId=qrId.value;if(!sessionId)return;try{const data=await api.pollQr(sessionId);if(qrId.value!==sessionId)return;if(data.status==='completed'){clearQrTimers();qrState.value='success';ElMessage.success('秒应账号添加成功');window.setTimeout(()=>{qrVisible.value=false;stopQr();load()},700)}else if(data.status==='expired'){clearQrTimers();qrState.value='expired'}else scheduleQrPoll()}catch(e){if(qrId.value===sessionId){scheduleQrPoll(1400)}}}
function stopQr(){clearQrTimers();qrId.value='';qrImage.value='';qrExpiresAt.value=0;qrRemainingSeconds.value=0;qrState.value='pending';qrLoading.value=false}
const defaultFormId=items=>items.find(item=>!item.is_closed)?.id||items[0]?.id||null
async function accountCommand(command,item){
  if(command==='rescan')return openQr()
  if(command==='sync'){const synced=await api.syncForms(item.id);if(item.id===selectedAccountId.value){accountForms.value=synced;selectedFormId.value=defaultFormId(synced);manualAnswers.value=seedAnswers(manualFields.value,selectedAccount.value,{})}ElMessage.success('项目同步完成');return}
  if(command==='rename'){let value;try{({value}=await ElMessageBox.prompt('请输入账号备注','编辑账号',{inputValue:item.remark||item.nickname||'',inputPattern:/\S+/,inputErrorMessage:'备注不能为空'}))}catch{return}await api.updateAccount(item.id,{remark:value.trim(),class_name:item.class_name||'',real_name:item.real_name||'',school_no:item.school_no||'',enabled:item.enabled});ElMessage.success('备注已更新');await load();return}
  if(command==='delete'){try{await ElMessageBox.confirm(`删除账号「${item.remark||item.nickname}」及其项目和任务？`,'删除账号',{type:'warning'})}catch{return}await api.deleteAccount(item.id);ElMessage.success('已删除');await load()}
}
function syncManualProfile(){Object.assign(manualProfile,{class_name:selectedAccount.value?.class_name||'',real_name:selectedAccount.value?.real_name||'',school_no:selectedAccount.value?.school_no||''})}
async function loadAccountForms(){accountForms.value=selectedAccountId.value?await api.listForms(selectedAccountId.value):[];if(!accountForms.value.some(item=>item.id===selectedFormId.value))selectedFormId.value=defaultFormId(accountForms.value);syncManualProfile();manualCoordinate.value='';manualLocationName.value='';manualLocationInfo.value={};manualAnswers.value=seedAnswers(manualFields.value,{...selectedAccount.value,...manualProfile},{})}
async function selectAccount(id){if(id===selectedAccountId.value)return;selectedAccountId.value=id;selectedFormId.value=null;await loadAccountForms()}
async function syncAccountForms(){if(!selectedAccountId.value)return;formsSyncing.value=true;try{accountForms.value=await api.syncForms(selectedAccountId.value);selectedFormId.value=defaultFormId(accountForms.value);manualAnswers.value=seedAnswers(manualFields.value,selectedAccount.value,{});ElMessage.success('签到项目同步完成')}catch(e){ElMessage.error(e.message)}finally{formsSyncing.value=false}}
async function saveManualProfile(showMessage=true){if(identityLabels.value.fixed)return Boolean(manualAnswers.value.__identity);const account=selectedAccount.value;if(!account)return false;if(!manualProfile.real_name.trim()||!manualProfile.school_no.trim()){ElMessage.warning(`请填写${identityLabels.value.name_label}和${identityLabels.value.number_label}`);return false}profileSaving.value=true;try{const updated=await api.updateAccount(account.id,{remark:account.remark||'',enabled:account.enabled,...manualProfile});Object.assign(account,updated);manualAnswers.value=seedAnswers(manualFields.value,account,manualAnswers.value);if(showMessage)ElMessage.success('签到资料已保存');return true}catch(e){ElMessage.error(e.message);return false}finally{profileSaving.value=false}}
const locationNameFromResult=result=>String(result?.display_name||result?.name||result?.address||'').trim()
function nativeLocationInfo(result,point){
  const province=String(result?.province||'').trim(),city=String(result?.city||'').trim(),district=String(result?.district||'').trim(),street=String(result?.street||'').trim()
  const landmark=String(result?.landmark||'').trim()
  let name=landmark||String(result?.name||result?.address||'').trim()
  if(street&&name.startsWith(`${street}-`))name=name.slice(street.length+1).trim()
  if(district&&name.startsWith(district)&&name.length>district.length)name=name.slice(district.length).trim()
  return{name:name||'地图选点',province,city,district,street,longtitude:Number(point.longitude),lattitude:Number(point.latitude)}
}
async function reverseLocation(point){const result=await api.reverseLocation(point.latitude,point.longitude);const name=locationNameFromResult(result);if(!name)throw new Error('未识别到该坐标的位置名称，请手动填写');return result}
async function selectManualLocation(result){manualLocationName.value=locationNameFromResult(result);try{const resolved=await reverseLocation(result);manualLocationName.value=locationNameFromResult(resolved)||manualLocationName.value;manualLocationInfo.value=nativeLocationInfo(resolved,result)}catch{manualLocationInfo.value={}}}
async function selectTaskLocation(result){form.location_name=locationNameFromResult(result);try{const resolved=await reverseLocation(result);form.location_name=locationNameFromResult(resolved)||form.location_name;form.location_info=nativeLocationInfo(resolved,result)}catch{form.location_info={}}}
async function submitManualCheckin(){const item=selectedManualForm.value;if(!item)return;if(!answersValid(manualFields.value,manualAnswers.value)){ElMessage.warning('请完整填写项目必填项');return}let point={latitude:null,longitude:null};if(item.requirements?.location){try{point=parseCoordinates(manualCoordinate.value)}catch(e){ElMessage.warning(e.message);return}}manualChecking.value=true;try{if(item.requirements?.location){const resolved=await reverseLocation(point);manualLocationName.value=locationNameFromResult(resolved);manualLocationInfo.value=nativeLocationInfo(resolved,point)}if(!await saveManualProfile(false))return;const result=await api.manualCheckin(item.id,{account_id:selectedAccountId.value,location_name:manualLocationName.value.trim(),location_info:manualLocationInfo.value,answers:manualAnswers.value,...point,notify_wecom:manualNotify.value});ElMessage.success(result.message||'签到成功');if(result.notification?.reason==='send_failed')ElMessage.warning('签到成功，但企业微信通知发送失败')}catch(e){ElMessage.error(e.message)}finally{manualChecking.value=false}}
async function saveSettings(){settingsSaving.value=true;try{Object.assign(settings,await api.updateSettings({miaoying_webhook_url:settings.miaoying_webhook_url}));ElMessage.success('秒应通知配置已保存')}catch(e){ElMessage.error(e.message)}finally{settingsSaving.value=false}}
async function accountChanged(){forms.value=form.account_id?await api.listForms(form.account_id):[];form.form_id=null;form.answers={};form.answer_schema=[];form.location_name='';form.location_info={};form.latitude=null;form.longitude=null}
async function syncSelected(){formsSyncing.value=true;try{forms.value=await api.syncForms(form.account_id);taskForms.value=[...taskForms.value.filter(item=>item.account_id!==form.account_id),...forms.value];ElMessage.success('项目同步完成')}catch(e){ElMessage.error(e.message)}finally{formsSyncing.value=false}}
function selectForm(item){if(form.form_id!==item.id)form.answers={};form.form_id=item.id;if(!form.name)form.name=item.title;if(item.remote_schedule_times?.length)form.schedule_times=[...item.remote_schedule_times];form.answers=seedAnswers(item.requirements?.fields||[],accounts.value.find(a=>a.id===form.account_id),form.answers)}
function taskFormChanged(id){const item=forms.value.find(row=>row.id===id);if(!item)return;form.answers={};form.answer_schema=[];form.location_name='';form.location_info={};form.latitude=null;form.longitude=null;selectForm(item)}
function openCreateTask(){resetForm();taskEditorVisible.value=true}
async function saveTask(){if(selectedTaskForm.value?.requirements?.identity?.fixed&&!form.answers.__identity){ElMessage.warning('请选择项目的班级和姓名');return}if(!form.account_id||!form.form_id||!form.name.trim()){ElMessage.warning('请选择账号和签到项目并填写任务名称');return}if(selectedTaskForm.value?.is_closed){ElMessage.warning('该签到项目已关闭，请选择其他项目');return}if(selectedTaskForm.value?.requirements?.unsupported?.length){ElMessage.warning(`暂不支持：${selectedTaskForm.value.requirements.unsupported.join('、')}`);return}if(!answersValid(taskFields.value,form.answers)){ElMessage.warning('请完整填写项目必填项');return}try{form.schedule_times=normalizeScheduleTimes(form.schedule_times);if(!form.schedule_times.length)throw new Error('请至少添加一个执行时间');if(form.date_mode==='specific'&&!form.run_dates.length)throw new Error('指定日期模式下请至少选择一个执行日期')}catch(e){ElMessage.warning(e.message);return}taskSaving.value=true;try{if(selectedTaskForm.value?.requirements?.location&&form.latitude!=null&&form.longitude!=null){const current={latitude:form.latitude,longitude:form.longitude};const resolved=await reverseLocation(current);form.location_name=locationNameFromResult(resolved);form.location_info=nativeLocationInfo(resolved,current)}const payload={...form,name:form.name.trim(),start_date:null,end_date:null};const fn=editingId.value?api.updateTask(editingId.value,payload):api.createTask(payload);await fn;ElMessage.success(editingId.value?'任务已更新':'任务已创建');taskEditorVisible.value=false;resetForm();await load()}catch(e){ElMessage.error(e.message)}finally{taskSaving.value=false}}
function resetForm(){Object.assign(form,emptyForm());forms.value=[];editingId.value=null}
async function toggleTask(row,enabled){try{await api.updateTask(row.id,{...row,enabled});row.enabled=enabled;ElMessage.success(enabled?'任务已启用':'任务已停用')}catch(e){ElMessage.error(e.message)}}
async function runNow(row){runningTaskId.value=row.id;try{const result=await api.runTask(row.id);result.status==='success'?ElMessage.success(result.message):ElMessage.error(result.message);await load()}catch(e){ElMessage.error(e.message)}finally{runningTaskId.value=null}}
async function editTask(row){try{forms.value=await api.listForms(row.account_id);editingId.value=row.id;Object.assign(form,emptyForm(),JSON.parse(JSON.stringify(row)),{start_date:null,end_date:null});taskEditorVisible.value=true}catch(e){ElMessage.error(e.message)}}
async function removeTask(row){try{await ElMessageBox.confirm(`确认删除任务“${row.name}”？`,'删除任务',{type:'warning'});await api.deleteTask(row.id);ElMessage.success('已删除');await load()}catch(e){if(!['cancel','close'].includes(e))ElMessage.error(e.message)}}
function seedAnswers(fields,account,current={}){const result={...current};for(const field of fields){if(result[field.key]!==undefined&&result[field.key]!==''&&result[field.key]?.length!==0)continue;const title=String(field.title||'').replaceAll(' ','');let value='';if(title.includes('姓名'))value=account?.real_name||'';else if(title.includes('学号'))value=account?.school_no||'';else if(title.includes('班级'))value=account?.class_name||'';if(value&&field.options?.length){const matched=field.options.find(option=>String(option.value)===String(value)||String(option.label)===String(value));value=matched?.value||''}if(field.control==='multiple')value=value?[value]:[];if(value!==''||field.control==='multiple')result[field.key]=value}return result}
function answersValid(fields,answers){return fields.every(field=>{if(field.control==='unsupported')return !field.required;const value=answers?.[field.key];if(!field.required)return true;if(Array.isArray(value)){const size=value.length;return size>=Number(field.min_select||1)&&(!field.max_select||size<=Number(field.max_select))}return value!==undefined&&value!==null&&String(value).trim()!==''})}
watch(selectedFormId,()=>{manualCoordinate.value='';manualLocationName.value='';manualLocationInfo.value={};manualAnswers.value=seedAnswers(manualFields.value,{...selectedAccount.value,...manualProfile},{})})
watch(()=>route.path,load);onMounted(load);onUnmounted(stopQr)
</script>

<style scoped>
.my-page{display:grid;gap:18px;min-width:0}.panel p{color:#64748b;font-size:13px}.panel{min-width:0;padding:20px;border:1px solid #dbeafe;border-radius:20px;background:#ffffffde;box-shadow:0 14px 34px #0f172a0a}.panel>header{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px}.panel h2{margin:0;color:#172033;font-size:18px}.panel header p{margin:4px 0 0}.panel header .el-input{max-width:320px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metrics article{display:grid;gap:5px;padding:22px;border:1px solid #dbeafe;border-radius:18px;background:#fff}.metrics b{font-size:28px;color:#1677ff}.metrics span{color:#64748b}.settings-panel{max-width:none}.accounts-workspace{display:grid;grid-template-columns:minmax(300px,340px) minmax(0,1fr);align-items:start;gap:18px}.accounts-pane{position:sticky;top:16px;align-self:start}.checkin-pane{min-height:420px}.account-search{display:flex;align-items:center;gap:10px;margin-bottom:14px}.account-search .el-input{flex:1}.account-search span{flex:none;color:#64748b;font-size:12px}.account-list{display:grid;gap:10px;max-height:calc(100vh - 310px);padding-right:4px;overflow-y:auto;scrollbar-gutter:stable}.account-card{display:flex;align-items:center;gap:12px;min-width:0;padding:14px;border:1px solid #dbeafe;border-radius:16px;background:#f8fbff;cursor:pointer;transition:.18s}.account-card:hover,.account-card.active{border-color:#60a5fa;background:#eff6ff;box-shadow:0 8px 20px #2563eb12}.avatar{display:grid;place-items:center;width:44px;height:44px;flex:none;border-radius:14px;color:white;font-weight:800;background:linear-gradient(135deg,#2563eb,#06b6d4)}.account-info{display:grid;min-width:0;flex:1}.account-info span,.account-info small{overflow:hidden;color:#64748b;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.project-picker{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:12px;margin-bottom:14px;padding:12px 14px;border:1px solid #dbeafe;border-radius:14px;background:#f8fbff}.project-picker>span{color:#475569;font-size:13px;font-weight:700}.form-select{width:100%;margin:0}.option-state{float:right;margin-left:24px;color:#94a3b8}.manual-checkin{display:grid;gap:14px}.manual-head{display:grid;gap:6px;padding:14px 16px;border:1px solid #bfdbfe;border-radius:14px;background:linear-gradient(135deg,#eff6ff,#f8fbff)}.manual-head>div{display:flex;align-items:center;gap:9px}.manual-head small{overflow:hidden;color:#64748b;text-overflow:ellipsis;white-space:nowrap}.manual-checkin :deep(.roster){margin-bottom:0;background:#fff}.location-section{display:grid;gap:12px;padding:16px;border:1px solid #bfdbfe;border-radius:16px;background:#fff}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-bottom:12px;border-bottom:1px solid #dbeafe}.section-heading strong,.section-heading small{display:block}.section-heading strong{color:#1e293b}.section-heading small{margin-top:3px;color:#64748b;font-size:12px}.manual-actions{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 16px;border:1px solid #bfdbfe;border-radius:16px;background:#eff6ff}.manual-actions>div{display:grid;gap:3px}.manual-actions small{color:#64748b;font-size:12px}.manual-actions .el-button{min-width:170px;margin:0}.workspace{display:grid;grid-template-columns:minmax(280px,.72fr) minmax(480px,1.28fr);gap:16px}.picker>.el-select{width:100%;margin-bottom:10px}.picker>.el-button{width:100%;margin:0 0 14px}.form-list{display:grid;gap:12px;max-height:520px;overflow:auto}.form-group{display:grid;gap:8px}.form-group>strong{padding:2px 4px;color:#64748b;font-size:12px}.form-group.closed{padding-top:10px;border-top:1px solid #e2e8f0}.form-group.closed button{opacity:.72}.form-list button{display:grid;gap:4px;padding:13px;text-align:left;border:1px solid #dbeafe;border-radius:13px;background:#f8fbff;color:#1e293b;cursor:pointer}.form-list button.active{border-color:#60a5fa;background:#eff6ff;box-shadow:inset 3px 0 #3b82f6}.form-list span{font-size:12px;color:#64748b}.range{display:flex;gap:8px;width:100%;flex-wrap:wrap}.range>*{flex:1}.task-dynamic-fields{margin:0 0 18px 88px}:deep(.run-list){display:grid;gap:9px}:deep(.run){display:flex;align-items:center;gap:12px;padding:14px;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc}:deep(.run i){width:10px;height:10px;border-radius:50%;background:#ef4444}:deep(.run.success i){background:#22c55e}:deep(.run div){display:grid;flex:1}:deep(.run span){color:#64748b;font-size:12px}:deep(.run-audit){margin-top:7px;color:#334155;font-size:12px;line-height:1.65;overflow-wrap:anywhere}:deep(.run em){font-style:normal;color:#ef4444}:deep(.run.success em){color:#16a34a}:deep(.empty-inline){padding:50px;text-align:center;color:#94a3b8}
.identity-fields{display:grid;gap:12px;padding:15px;border:1px solid #bfdbfe;border-radius:16px;background:#fff}.identity-title{display:flex;align-items:center;justify-content:space-between;gap:12px}.identity-title strong,.identity-title small{display:block}.identity-title small{margin-top:3px;color:#64748b;font-size:12px}.identity-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.identity-grid label{display:grid;gap:6px;min-width:0}.identity-grid label>span{color:#475569;font-size:13px}
.location-editor{display:grid;gap:10px;width:100%;min-width:0}.location-editor>.el-input{width:100%}.task-panel{padding:0;overflow:hidden}.task-panel>header{padding:20px 20px 0}.task-panel :deep(.el-table){padding:0 20px 20px}.task-panel-head{align-items:flex-start!important}.task-panel-actions{display:flex;align-items:center;justify-content:flex-end;gap:10px}.task-panel-actions .el-input{width:260px}.task-panel-actions .el-button{margin:0}.task-cell{display:grid;gap:4px}.task-cell strong{color:#172033}.task-cell small{color:#64748b;font-size:11px}.muted{color:#94a3b8;font-size:12px}
:global(.miaoying-task-dialog){border-radius:20px;overflow:hidden}:global(.miaoying-task-dialog .el-dialog__body){max-height:calc(100vh - 170px);padding-top:8px;overflow-y:auto}:global(.miaoying-task-dialog .el-dialog__footer){border-top:1px solid #e2e8f0}.task-editor-layout{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.task-editor-section{min-width:0;padding:16px;border:1px solid #dbeafe;border-radius:18px;background:linear-gradient(145deg,#fff,#f8fbff)}.task-editor-section--wide{grid-column:1/-1}.task-editor-section>header{display:flex;align-items:center;gap:10px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #dbeafe}.task-editor-section>header strong,.task-editor-section>header small{display:block}.task-editor-section>header small{margin-top:2px;color:#64748b;font-size:11px}.section-index{display:grid;width:35px;height:35px;place-items:center;color:#fff;border-radius:11px;background:linear-gradient(135deg,#2563eb,#3b82f6);font-size:12px;font-weight:800}.task-editor-section :deep(.el-select),.task-editor-section :deep(.el-date-editor){width:100%}.project-select-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;width:100%}.schedule-list{display:grid;gap:8px;width:100%}.schedule-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.schedule-list>.el-button{width:100%;margin:0}.date-plan-card{display:flex;align-items:center;justify-content:space-between;gap:14px;width:100%;padding:13px;border:1px solid #bfdbfe;border-radius:14px;background:#eff6ff}.date-plan-card>div{display:grid;gap:5px}.date-plan-card strong{color:#1e3a8a;font-size:13px}.date-plan-card small{color:#64748b;font-size:11px}.task-enable-box{display:grid;gap:3px;padding:13px;border-radius:13px;background:#eff6ff}.task-enable-box small{color:#64748b;font-size:11px}.task-location-section{display:grid;gap:12px;margin-top:14px;padding:14px;border:1px solid #bfdbfe;border-radius:15px;background:#fff}.schedule-drawer-body{display:grid;gap:16px}.schedule-drawer-intro{display:grid;gap:4px;padding:14px;border:1px solid #dbeafe;border-radius:14px;background:#eff6ff}.schedule-drawer-intro small{color:#64748b;font-size:12px}
@media(max-width:1280px){.accounts-workspace,.workspace{grid-template-columns:1fr}.accounts-pane{position:static}.account-list{grid-template-columns:repeat(2,minmax(0,1fr));max-height:360px}.metrics{grid-template-columns:repeat(2,1fr)}}@media(max-width:850px){.task-editor-layout{grid-template-columns:1fr}.task-editor-section--wide{grid-column:auto}.task-panel-actions{align-items:stretch;flex-direction:column}.task-panel-actions .el-input{width:100%}}@media(max-width:700px){.metrics{grid-template-columns:1fr}.panel{padding:14px}.task-panel{padding:0}.panel>header{align-items:flex-start;flex-direction:column}.panel header .el-input{max-width:none}.account-search{align-items:flex-start;flex-direction:column}.account-search .el-input{width:100%}.account-list{grid-template-columns:1fr;max-height:420px}.project-picker,.project-select-row{grid-template-columns:1fr}.editor{padding:14px}:deep(.editor .el-form-item){display:block}:deep(.editor .el-form-item__label){justify-content:flex-start}.task-dynamic-fields{margin-left:0}.identity-title{align-items:flex-start}.identity-grid{grid-template-columns:1fr}.manual-actions{align-items:stretch;flex-direction:column}.manual-actions .el-button{width:100%;margin:0}.range>*{min-width:100%!important}}
</style>
