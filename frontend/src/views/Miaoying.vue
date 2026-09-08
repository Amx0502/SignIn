<template>
  <div class="my-page" v-loading="loading">
    <MiaoyingOverviewPanel
      v-if="isOverview"
      :metrics="overviewMetrics"
      :webhook="settings.miaoying_webhook_url"
      :configured="settings.webhook_configured"
      :is-admin="isAdmin"
      :saving="settingsSaving"
      :testing="notificationTesting"
      @update:webhook="value => settings.miaoying_webhook_url = value"
      @save="saveSettings"
      @test="testNotification"
    />

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
              <div class="location-info-editor">
                <div class="location-info-title"><div><strong>提交给秒应的位置字段</strong><small>地图选点后会自动填写，也可以手动修改；提交时以这里的内容为准。</small></div><el-tag size="small" type="success">可编辑</el-tag></div>
                <div class="location-info-grid">
                  <label><span>省份</span><el-input v-model="manualLocationInfo.province" clearable maxlength="255" placeholder="例如：福建省" /></label>
                  <label><span>城市</span><el-input v-model="manualLocationInfo.city" clearable maxlength="255" placeholder="例如：福州市" /></label>
                  <label><span>区县</span><el-input v-model="manualLocationInfo.district" clearable maxlength="255" placeholder="例如：马尾区" /></label>
                  <label><span>街道名称</span><el-input v-model="manualLocationInfo.street" clearable maxlength="255" placeholder="例如：马尾隧道" /></label>
                  <label class="location-name-field"><span>地点名称</span><el-input v-model="manualLocationInfo.name" clearable maxlength="255" placeholder="例如：阳光学院（福州校本部）" /></label>
                </div>
                <small class="location-submit-preview">实际位置：{{ locationDisplayName(manualLocationInfo, manualLocationName) || '请通过地图选点或手动填写' }}</small>
              </div>
              <LocationSearchPanel v-model="manualCoordinate" :location-api="api" @select-location="selectManualLocation" />
            </div>
          </section>
          <div class="manual-actions"><div class="manual-action-summary"><strong>{{ selectedAccount?.remark || selectedAccount?.nickname }} / {{ selectedManualForm.title }}</strong><el-checkbox v-model="manualNotify">发送企业微信通知</el-checkbox><small>{{ manualValidationHint }}</small></div><el-button type="primary" size="large" :loading="manualChecking" :disabled="!canManualCheckin" @click="submitManualCheckin">执行签到</el-button></div>
        </div>
      </div>
    </section>

    <MiaoyingAutoTaskPanel
      v-else-if="isAuto"
      :tasks="tasks"
      :accounts="accounts"
      :forms="taskForms"
      :running-task-id="runningTaskId"
      :batch-loading="batchTaskLoading"
      @create="openCreateTask"
      @edit="editTask"
      @run="runNow"
      @toggle="toggleTask"
      @remove="removeTask"
      @batch-state="batchSetTaskState"
      @batch-delete="batchDeleteTasks"
    />

    <div v-else-if="isLogs"><LogConsole title="秒应日志" empty-text="暂无秒应日志" :logs="miaoyingLogEntries" :loading="loading" @refresh="load" /></div>
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
      <el-form label-position="top">
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
              <section v-if="selectedTaskForm.requirements?.location" class="task-location-section">
                <div class="section-heading"><div><strong>签到位置</strong><small>搜索地点或直接在腾讯地图上选点</small></div><el-tag size="small" type="primary">腾讯地图</el-tag></div>
                <div class="location-info-editor">
                  <div class="location-info-title"><div><strong>提交给秒应的位置字段</strong><small>地图会自动填写，保存任务前也可以手动修改。</small></div><el-tag size="small" type="success">可编辑</el-tag></div>
                  <div class="location-info-grid">
                    <label><span>省份</span><el-input v-model="form.location_info.province" clearable maxlength="255" placeholder="例如：福建省" /></label>
                    <label><span>城市</span><el-input v-model="form.location_info.city" clearable maxlength="255" placeholder="例如：福州市" /></label>
                    <label><span>区县</span><el-input v-model="form.location_info.district" clearable maxlength="255" placeholder="例如：马尾区" /></label>
                    <label><span>街道名称</span><el-input v-model="form.location_info.street" clearable maxlength="255" placeholder="例如：马尾隧道" /></label>
                    <label class="location-name-field"><span>地点名称</span><el-input v-model="form.location_info.name" clearable maxlength="255" placeholder="例如：阳光学院（福州校本部）" /></label>
                  </div>
                  <small class="location-submit-preview">实际位置：{{ locationDisplayName(form.location_info, form.location_name) || '请通过地图选点或手动填写' }}</small>
                </div>
                <LocationSearchPanel v-model="taskCoordinate" :location-api="api" @select-location="selectTaskLocation" />
              </section>
              <el-alert v-if="!selectedTaskForm.requirements?.identity?.fixed && !taskFields.length && !selectedTaskForm.requirements?.location" type="info" :closable="false" title="该项目没有需要预设的签到参数" />
            </template>
          </section>
        </div>
      </el-form>
      <template #footer><el-button @click="taskEditorVisible = false">取消</el-button><el-button type="primary" :loading="taskSaving" @click="saveTask">保存任务</el-button></template>
    </el-dialog>

    <el-drawer v-model="scheduleDrawerVisible" title="设置签到日期计划" size="min(760px, 100vw)" append-to-body :close-on-click-modal="false">
      <div class="schedule-drawer-body"><div class="schedule-drawer-intro"><strong>控制具体哪天执行或跳过</strong><small>指定日期、排除日期和周末策略会保存到当前秒应任务。</small></div><TaskDateSchedule v-model:date-mode="scheduleDraft.date_mode" v-model:run-dates="scheduleDraft.run_dates" v-model:skip-dates="scheduleDraft.skip_dates" v-model:skip-weekends="scheduleDraft.skip_weekends" v-model:auto-disable-after-finish="scheduleDraft.auto_disable_after_finish" :times="form.schedule_times" min-date="" max-date="" /></div>
      <template #footer><el-button @click="scheduleDrawerVisible = false">取消</el-button><el-button type="primary" @click="applyScheduleDraft">应用日期计划</el-button></template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import api from '../api/miaoying.js'
import TaskDateSchedule from '../components/TaskDateSchedule.vue'
import LogConsole from '../components/LogConsole.vue'
import DynamicFormFields from '../components/miaoying/DynamicFormFields.vue'
import MiaoyingAutoTaskPanel from '../components/miaoying/AutoTaskPanel.vue'
import MiaoyingOverviewPanel from '../components/miaoying/OverviewPanel.vue'
import MiaoyingRunHistoryPanel from '../components/miaoying/RunHistoryPanel.vue'
import RosterIdentity from '../components/miaoying/RosterIdentity.vue'
import QrLoginDialog from '../components/class-cube/QrLoginDialog.vue'
import { normalizeScheduleTimes, parseCoordinates } from '../utils/classCubeTaskForm.js'

const LocationSearchPanel=defineAsyncComponent(()=>import('../components/class-cube/LocationSearchPanel.vue'))

const route=useRoute(),loading=ref(false),keyword=ref(''),accounts=ref([]),forms=ref([]),taskForms=ref([]),tasks=ref([]),runs=ref([])
const qrVisible=ref(false),qrImage=ref(''),qrState=ref('pending'),qrId=ref(''),qrLoading=ref(false),qrRemainingSeconds=ref(0),qrExpiresAt=ref(0);let qrTimer,qrCountdownTimer
const miaoyingQrSession=computed(()=>({status:qrState.value,qrImage:qrImage.value}))
const editingId=ref(null),taskEditorVisible=ref(false),taskSaving=ref(false),runningTaskId=ref(null),batchTaskLoading=ref(false),scheduleDrawerVisible=ref(false)
const user=JSON.parse(localStorage.getItem('user')||'{}'),isAdmin=computed(()=>user.role==='admin')
const settings=reactive({miaoying_webhook_url:'',webhook_configured:false}),settingsSaving=ref(false),notificationTesting=ref(false)
const overviewMetrics=reactive({accounts:0,tasks:0,enabled_tasks:0,successful_runs:0})
const selectedAccountId=ref(null),selectedFormId=ref(null),accountForms=ref([]),formsSyncing=ref(false)
const emptyLocationInfo=()=>({province:'',city:'',district:'',street:'',name:''})
const manualCoordinate=ref(''),manualLocationName=ref(''),manualLocationInfo=ref(emptyLocationInfo()),manualNotify=ref(true),manualChecking=ref(false),manualAnswers=ref({}),profileSaving=ref(false)
const manualProfile=reactive({class_name:'',real_name:'',school_no:''})
const emptyForm=()=>({account_id:null,form_id:null,name:'',enabled:true,schedule_times:['08:00:00'],start_date:null,end_date:null,date_mode:'daily',run_dates:[],skip_dates:[],skip_weekends:false,auto_disable_after_finish:true,location_name:'',location_info:{},latitude:null,longitude:null,answers:{},answer_schema:[]})
const form=reactive(emptyForm())
const scheduleDraft=reactive({date_mode:'daily',run_dates:[],skip_dates:[],skip_weekends:false,auto_disable_after_finish:true})
const path=computed(()=>route.path),isOverview=computed(()=>path.value.endsWith('/overview')),isAccounts=computed(()=>path.value.endsWith('/accounts')),isAuto=computed(()=>path.value.endsWith('/auto')),isLogs=computed(()=>path.value.endsWith('/logs'))
const filteredAccounts=computed(()=>accounts.value.filter(v=>`${v.nickname}${v.remark}${v.remote_user_id}`.toLowerCase().includes(keyword.value.toLowerCase())))
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
const miaoyingLogEntries=computed(()=>runs.value.flatMap(run=>miaoyingAuditLogEvents(run)).sort((a,b)=>a.timestamp-b.timestamp).map(item=>item.line))
const canManualCheckin=computed(()=>{
  const item=selectedManualForm.value
  if(!item||item.is_closed||item.requirements?.unsupported?.length)return false
  if(identityLabels.value.fixed&&!manualAnswers.value.__identity)return false
  if(!identityLabels.value.fixed&&(!manualProfile.real_name.trim()||!manualProfile.school_no.trim()))return false
  if(!answersValid(manualFields.value,manualAnswers.value))return false
  if(!item.requirements?.location)return true
  try{return Boolean(parseCoordinates(manualCoordinate.value))}catch{return false}
})
const manualValidationHint=computed(()=>{
  const item=selectedManualForm.value
  if(!selectedAccount.value)return'请先选择一个秒应账号'
  if(!item)return'请先选择一个签到项目'
  if(item.is_closed)return'该签到项目已经关闭'
  if(item.requirements?.unsupported?.length)return`暂不支持：${item.requirements.unsupported.join('、')}`
  if(identityLabels.value.fixed&&!manualAnswers.value.__identity)return'请选择项目固定名单中的班级和姓名'
  if(!identityLabels.value.fixed&&(!manualProfile.real_name.trim()||!manualProfile.school_no.trim()))return`请填写${identityLabels.value.name_label}和${identityLabels.value.number_label}`
  if(!answersValid(manualFields.value,manualAnswers.value))return'请完成所有必填的项目填写项'
  if(item.requirements?.location){try{parseCoordinates(manualCoordinate.value)}catch{return'请定位或填写有效的签到坐标'}}
  return'已完成所有必填项，可以执行签到'
})
const taskCoordinate=computed({
  get:()=>form.latitude==null||form.longitude==null?'':`${form.latitude}, ${form.longitude}`,
  set:value=>{try{const point=parseCoordinates(value);form.latitude=point.latitude;form.longitude=point.longitude;if(form.location_name==='地图选点')form.location_name=''}catch{form.latitude=null;form.longitude=null;if(!String(value||'').trim()&&form.location_name==='地图选点')form.location_name=''}},
})
const logTime=value=>value?new Date(value).toLocaleString('sv-SE',{hour12:false}).replace('T',' '):'0000-00-00 00:00:00'
const taskAccountName=id=>{const row=accounts.value.find(item=>item.id===id);return row?.remark||row?.nickname||`账号 ${id}`}
const taskFormName=id=>taskForms.value.find(item=>item.id===id)?.title||`签到项目 ${id}`
const taskName=id=>tasks.value.find(item=>item.id===id)?.name||`任务 ${id}`
const cleanLogValue=value=>String(value??'').replace(/[\r\n|]+/g,' ').replace(/\s+/g,' ').trim()
const durationText=(startedAt,finishedAt)=>{if(!startedAt||!finishedAt)return'—';const duration=new Date(finishedAt)-new Date(startedAt);return Number.isFinite(duration)&&duration>=0?(duration<1000?`${duration}ms`:`${(duration/1000).toFixed(2)}s`):'—'}
function miaoyingAuditLogEvents(run){
  const summary=run.request_summary||{},location=summary.location_info||{}
  const identity=[]
  if(summary.student_number)identity.push(`学号=${cleanLogValue(summary.student_number)}`)
  if(summary.roster_number!==undefined&&summary.roster_number!==null&&String(summary.roster_number)!==String(summary.student_number||''))identity.push(`名单序号=${cleanLogValue(summary.roster_number)}`)
  const submitted=(summary.submitted_fields||[]).map(field=>`${cleanLogValue(field.label)}=${cleanLogValue(field.value)}`).filter(Boolean)
  const address=[location.province,location.city,location.district,location.street,location.name].map(cleanLogValue).filter((value,index,array)=>value&&array.indexOf(value)===index).join('-')
  const hasCoordinates=location.lattitude!==undefined&&location.lattitude!==null&&location.longtitude!==undefined&&location.longtitude!==null
  const common=[`审计ID=${run.id}`,`账号=${taskAccountName(run.account_id)}（ID=${run.account_id}）`,`项目=${taskFormName(run.form_id)}（ID=${run.form_id}）`]
  if(run.task_id)common.push(`任务=${taskName(run.task_id)}（ID=${run.task_id}）`)
  common.push(`触发=${run.trigger==='manual'?'手动签到':'定时自动执行'}`,`操作=${summary.operation||run.operation||'createBaomingByInput'}`)
  if(summary.tongji_id)common.push(`远程项目ID=${cleanLogValue(summary.tongji_id)}`)
  if(summary.remote_user_id)common.push(`远程用户ID=${cleanLogValue(summary.remote_user_id)}`)
  if(identity.length)common.push(`身份=${identity.join('，')}`)
  if(submitted.length)common.push(`提交字段=${submitted.join('；')}`)
  if(address)common.push(`完整位置=${address}`)
  if(hasCoordinates)common.push(`坐标=${location.lattitude},${location.longtitude}`)
  const startedAt=run.started_at||run.finished_at
  const request={timestamp:new Date(startedAt||0).getTime()||0,line:`${logTime(startedAt)} [INFO] [请求] ${common.join(' | ')}`}
  const responseParts=[`审计ID=${run.id}`,`状态=${run.status==='success'?'签到成功':run.status==='running'?'等待响应':'签到失败'}`,`耗时=${durationText(run.started_at,run.finished_at)}`]
  if(run.remote_submission_id)responseParts.push(`秒应记录ID=${cleanLogValue(run.remote_submission_id)}`)
  if(run.message)responseParts.push(`消息=${cleanLogValue(run.message)}`)
  const level=run.status==='success'?'INFO':run.status==='running'?'WARNING':'ERROR'
  const finishedAt=run.finished_at||run.started_at
  return[request,{timestamp:new Date(finishedAt||0).getTime()||0,line:`${logTime(finishedAt)} [${level}] [响应] ${responseParts.join(' | ')}`}]
}
function schedulePlanSummary(plan){const excluded=(plan.skip_dates||[]).length;if((plan.date_mode||'daily')==='daily')return ['每天执行',plan.skip_weekends?'周末跳过':'',excluded?`排除 ${excluded} 天`:''].filter(Boolean).join(' · ');return [`指定 ${(plan.run_dates||[]).length} 天`,plan.auto_disable_after_finish?'结束后关闭':''].filter(Boolean).join(' · ')}
function openScheduleDrawer(){Object.assign(scheduleDraft,{date_mode:form.date_mode||'daily',run_dates:[...(form.run_dates||[])],skip_dates:[...(form.skip_dates||[])],skip_weekends:form.skip_weekends===true,auto_disable_after_finish:form.auto_disable_after_finish===true});scheduleDrawerVisible.value=true}
function applyScheduleDraft(){if(scheduleDraft.date_mode==='specific'&&!scheduleDraft.run_dates.length){ElMessage.warning('指定日期模式下请至少选择一个执行日期');return}Object.assign(form,{...scheduleDraft,run_dates:[...scheduleDraft.run_dates],skip_dates:[...scheduleDraft.skip_dates]});scheduleDrawerVisible.value=false}
async function loadTaskContext(){const groups=await Promise.all(accounts.value.map(account=>api.listForms(account.id).catch(()=>[])));taskForms.value=groups.flat()}
async function loadOptionalRunContext(){const [accountResult,taskResult]=await Promise.allSettled([api.listAccounts(),api.listTasks()]);if(accountResult.status==='fulfilled')accounts.value=accountResult.value;if(taskResult.status==='fulfilled')tasks.value=taskResult.value;await loadTaskContext()}
async function loadOverview(){try{const overview=await api.getOverview();if(overview?.metrics){Object.assign(overviewMetrics,overview.metrics);Object.assign(settings,overview.settings||{});return}}catch{/* 兼容尚未重启到聚合接口版本的后端 */}const [accountRows,taskRows,runRows,currentSettings]=await Promise.all([api.listAccounts(),api.listTasks(),api.listRuns(),api.getSettings()]);Object.assign(overviewMetrics,{accounts:accountRows.length,tasks:taskRows.length,enabled_tasks:taskRows.filter(item=>item.enabled).length,successful_runs:runRows.filter(item=>item.status==='success').length});Object.assign(settings,currentSettings)}
function auditForRun(run,audits){return audits.find(audit=>run.remote_submission_id&&audit.remote_submission_id===run.remote_submission_id)||audits.find(audit=>audit.task_id===run.task_id&&audit.account_id===run.account_id&&audit.form_id===run.form_id&&Math.abs(new Date(audit.started_at)-new Date(run.started_at))<60000)}
async function load(){loading.value=true;try{if(isAccounts.value){accounts.value=await api.listAccounts();if(!accounts.value.some(item=>item.id===selectedAccountId.value))selectedAccountId.value=accounts.value[0]?.id||null;await loadAccountForms()}else if(isAuto.value){[accounts.value,tasks.value]=await Promise.all([api.listAccounts(),api.listTasks()]);await loadTaskContext();if(form.account_id)forms.value=await api.listForms(form.account_id)}else if(isOverview.value){await loadOverview()}else if(isLogs.value){runs.value=await api.listSubmissionAudits(500);await loadOptionalRunContext()}else{const [taskRuns,audits]=await Promise.all([api.listRuns(),api.listSubmissionAudits()]);const enriched=taskRuns.map(run=>{const audit=auditForRun(run,audits);return audit?{...run,operation:audit.operation,request_summary:audit.request_summary}:run});runs.value=[...enriched,...audits.filter(item=>!item.task_id)].sort((a,b)=>new Date(b.started_at)-new Date(a.started_at));await loadOptionalRunContext()}}catch(e){ElMessage.error(e.message)}finally{loading.value=false}}
async function openQr(){stopQr();qrVisible.value=true;qrLoading.value=true;qrState.value='pending';try{const data=await api.createQr();qrId.value=data.id;qrImage.value=await QRCode.toDataURL(data.qr_content,{width:440,margin:2,color:{dark:'#000000',light:'#ffffff'}});qrExpiresAt.value=new Date(data.expires_at).getTime();updateQrCountdown();qrCountdownTimer=window.setInterval(updateQrCountdown,1000);scheduleQrPoll(100)}catch(e){qrState.value='error';ElMessage.error(e.message)}finally{qrLoading.value=false}}
function scheduleQrPoll(delay=800){if(qrTimer)window.clearTimeout(qrTimer);qrTimer=window.setTimeout(pollQr,delay)}
function updateQrCountdown(){qrRemainingSeconds.value=Math.max(0,Math.ceil((qrExpiresAt.value-Date.now())/1000));if(qrExpiresAt.value&&qrRemainingSeconds.value===0){qrState.value='expired';clearQrTimers()}}
function clearQrTimers(){if(qrTimer)window.clearTimeout(qrTimer);if(qrCountdownTimer)window.clearInterval(qrCountdownTimer);qrTimer=null;qrCountdownTimer=null}
async function pollQr(){const sessionId=qrId.value;if(!sessionId)return;try{const data=await api.pollQr(sessionId);if(qrId.value!==sessionId)return;if(data.status==='completed'){clearQrTimers();qrState.value='success';ElMessage.success('秒应账号添加成功');window.setTimeout(()=>{qrVisible.value=false;stopQr();load()},700)}else if(data.status==='expired'){clearQrTimers();qrState.value='expired'}else scheduleQrPoll()}catch(e){if(qrId.value===sessionId){scheduleQrPoll(1400)}}}
function stopQr(){clearQrTimers();qrId.value='';qrImage.value='';qrExpiresAt.value=0;qrRemainingSeconds.value=0;qrState.value='pending';qrLoading.value=false}
const defaultFormId=items=>items.find(item=>!item.is_closed)?.id||items[0]?.id||null
async function accountCommand(command,item){
  if(command==='rescan')return openQr()
  if(command==='sync'){const result=await api.syncFormsDetailed(item.id);if(item.id===selectedAccountId.value){accountForms.value=result.forms;selectedFormId.value=defaultFormId(result.forms);manualAnswers.value=seedAnswers(manualFields.value,selectedAccount.value,{})}showSyncSummary(result.summary);return}
  if(command==='rename'){let value;try{({value}=await ElMessageBox.prompt('请输入账号备注','编辑账号',{inputValue:item.remark||item.nickname||'',inputPattern:/\S+/,inputErrorMessage:'备注不能为空'}))}catch{return}await api.updateAccount(item.id,{remark:value.trim(),class_name:item.class_name||'',real_name:item.real_name||'',school_no:item.school_no||'',enabled:item.enabled});ElMessage.success('备注已更新');await load();return}
  if(command==='delete'){try{await ElMessageBox.confirm(`删除账号「${item.remark||item.nickname}」及其项目和任务？`,'删除账号',{type:'warning'})}catch{return}await api.deleteAccount(item.id);ElMessage.success('已删除');await load()}
}
function syncManualProfile(){Object.assign(manualProfile,{class_name:selectedAccount.value?.class_name||'',real_name:selectedAccount.value?.real_name||'',school_no:selectedAccount.value?.school_no||''})}
async function loadAccountForms(){accountForms.value=selectedAccountId.value?await api.listForms(selectedAccountId.value):[];if(!accountForms.value.some(item=>item.id===selectedFormId.value))selectedFormId.value=defaultFormId(accountForms.value);syncManualProfile();manualCoordinate.value='';manualLocationName.value='';manualLocationInfo.value=emptyLocationInfo();manualAnswers.value=seedAnswers(manualFields.value,{...selectedAccount.value,...manualProfile},{})}
async function selectAccount(id){if(id===selectedAccountId.value)return;selectedAccountId.value=id;selectedFormId.value=null;await loadAccountForms()}
function showSyncSummary(summary={}){const elapsed=Number(summary.elapsed_ms||0);const duration=elapsed<1000?`${elapsed} 毫秒`:`${(elapsed/1000).toFixed(2)} 秒`;ElMessage.success({message:`同步完成：新增 ${summary.added||0}，更新 ${summary.updated||0}，关闭 ${summary.closed||0}，未变化 ${summary.unchanged||0}，共 ${summary.total||0} 项（${duration}）`,duration:5000})}
async function syncAccountForms(){if(!selectedAccountId.value)return;formsSyncing.value=true;try{const result=await api.syncFormsDetailed(selectedAccountId.value);accountForms.value=result.forms;selectedFormId.value=defaultFormId(accountForms.value);manualAnswers.value=seedAnswers(manualFields.value,selectedAccount.value,{});showSyncSummary(result.summary)}catch(e){ElMessage.error(e.message)}finally{formsSyncing.value=false}}
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
function mergeLocationInfo(automatic,preferred,point){const result={};for(const key of ['province','city','district','street','name'])result[key]=String(preferred?.[key]||automatic?.[key]||'').trim().slice(0,255);result.longtitude=Number(point.longitude);result.lattitude=Number(point.latitude);return result}
function locationDisplayName(info,fallback=''){const street=String(info?.street||'').trim(),name=String(info?.name||'').trim();if(street||name)return[street,name].filter((value,index,array)=>value&&array.indexOf(value)===index).join('-');return String(fallback||'').trim()}
function hasLocationInfo(info){return['province','city','district','street','name'].some(key=>String(info?.[key]||'').trim())}
async function reverseLocation(point){const result=await api.reverseLocation(point.latitude,point.longitude);const name=locationNameFromResult(result);if(!name)throw new Error('未识别到该坐标的位置名称，请手动填写');return result}
async function selectManualLocation(result){manualLocationName.value=locationNameFromResult(result);try{const resolved=await reverseLocation(result);manualLocationName.value=locationNameFromResult(resolved)||manualLocationName.value;manualLocationInfo.value=nativeLocationInfo(resolved,result)}catch{manualLocationInfo.value=emptyLocationInfo()}}
async function selectTaskLocation(result){form.location_name=locationNameFromResult(result);try{const resolved=await reverseLocation(result);form.location_name=locationNameFromResult(resolved)||form.location_name;form.location_info=nativeLocationInfo(resolved,result)}catch{form.location_info=emptyLocationInfo()}}
async function submitManualCheckin(){const item=selectedManualForm.value;if(!item)return;if(!answersValid(manualFields.value,manualAnswers.value)){ElMessage.warning('请完整填写项目必填项');return}let point={latitude:null,longitude:null};if(item.requirements?.location){try{point=parseCoordinates(manualCoordinate.value)}catch(e){ElMessage.warning(e.message);return}}manualChecking.value=true;try{if(item.requirements?.location){let automatic={},fallbackName='';try{const resolved=await reverseLocation(point);automatic=nativeLocationInfo(resolved,point);fallbackName=locationNameFromResult(resolved)}catch(e){if(!hasLocationInfo(manualLocationInfo.value))throw e}manualLocationInfo.value=mergeLocationInfo(automatic,manualLocationInfo.value,point);manualLocationName.value=locationDisplayName(manualLocationInfo.value,fallbackName)}if(!await saveManualProfile(false))return;const result=await api.manualCheckin(item.id,{account_id:selectedAccountId.value,location_name:manualLocationName.value.trim(),location_info:manualLocationInfo.value,answers:manualAnswers.value,...point,notify_wecom:manualNotify.value});ElMessage.success(result.message||'签到成功');if(result.notification?.reason==='send_failed')ElMessage.warning('签到成功，但企业微信通知发送失败')}catch(e){ElMessage.error(e.message)}finally{manualChecking.value=false}}
async function saveSettings(){settingsSaving.value=true;try{Object.assign(settings,await api.updateSettings({miaoying_webhook_url:settings.miaoying_webhook_url}));ElMessage.success('秒应通知配置已保存')}catch(e){ElMessage.error(e.message)}finally{settingsSaving.value=false}}
async function testNotification(){notificationTesting.value=true;try{await api.testNotification({miaoying_webhook_url:settings.miaoying_webhook_url});ElMessage.success('测试通知已发送，请在企业微信中确认')}catch(e){ElMessage.error(e.message)}finally{notificationTesting.value=false}}
async function accountChanged(){forms.value=form.account_id?await api.listForms(form.account_id):[];form.form_id=null;form.answers={};form.answer_schema=[];form.location_name='';form.location_info={};form.latitude=null;form.longitude=null}
async function syncSelected(){formsSyncing.value=true;try{const result=await api.syncFormsDetailed(form.account_id);forms.value=result.forms;taskForms.value=[...taskForms.value.filter(item=>item.account_id!==form.account_id),...forms.value];showSyncSummary(result.summary)}catch(e){ElMessage.error(e.message)}finally{formsSyncing.value=false}}
function selectForm(item){if(form.form_id!==item.id)form.answers={};form.form_id=item.id;if(!form.name)form.name=item.title;if(item.remote_schedule_times?.length)form.schedule_times=[...item.remote_schedule_times];form.answers=seedAnswers(item.requirements?.fields||[],accounts.value.find(a=>a.id===form.account_id),form.answers)}
function taskFormChanged(id){const item=forms.value.find(row=>row.id===id);if(!item)return;form.answers={};form.answer_schema=[];form.location_name='';form.location_info={};form.latitude=null;form.longitude=null;selectForm(item)}
function openCreateTask(){resetForm();taskEditorVisible.value=true}
async function saveTask(){if(selectedTaskForm.value?.requirements?.identity?.fixed&&!form.answers.__identity){ElMessage.warning('请选择项目的班级和姓名');return}if(!form.account_id||!form.form_id||!form.name.trim()){ElMessage.warning('请选择账号和签到项目并填写任务名称');return}if(selectedTaskForm.value?.is_closed){ElMessage.warning('该签到项目已关闭，请选择其他项目');return}if(selectedTaskForm.value?.requirements?.unsupported?.length){ElMessage.warning(`暂不支持：${selectedTaskForm.value.requirements.unsupported.join('、')}`);return}if(!answersValid(taskFields.value,form.answers)){ElMessage.warning('请完整填写项目必填项');return}try{form.schedule_times=normalizeScheduleTimes(form.schedule_times);if(!form.schedule_times.length)throw new Error('请至少添加一个执行时间');if(form.date_mode==='specific'&&!form.run_dates.length)throw new Error('指定日期模式下请至少选择一个执行日期')}catch(e){ElMessage.warning(e.message);return}taskSaving.value=true;try{if(selectedTaskForm.value?.requirements?.location&&form.latitude!=null&&form.longitude!=null){const current={latitude:form.latitude,longitude:form.longitude};let automatic={},fallbackName='';try{const resolved=await reverseLocation(current);automatic=nativeLocationInfo(resolved,current);fallbackName=locationNameFromResult(resolved)}catch(e){if(!hasLocationInfo(form.location_info))throw e}form.location_info=mergeLocationInfo(automatic,form.location_info,current);form.location_name=locationDisplayName(form.location_info,fallbackName)}const payload={...form,name:form.name.trim(),start_date:null,end_date:null};const fn=editingId.value?api.updateTask(editingId.value,payload):api.createTask(payload);await fn;ElMessage.success(editingId.value?'任务已更新':'任务已创建');taskEditorVisible.value=false;resetForm();await load()}catch(e){ElMessage.error(e.message)}finally{taskSaving.value=false}}
function resetForm(){Object.assign(form,emptyForm());forms.value=[];editingId.value=null}
async function toggleTask(row,enabled){try{await api.updateTask(row.id,{...row,enabled});row.enabled=enabled;ElMessage.success(enabled?'任务已启用':'任务已停用')}catch(e){ElMessage.error(e.message)}}
async function batchSetTaskState(ids,enabled){if(!ids.length)return;batchTaskLoading.value=true;try{const result=await api.batchSetTaskState(ids,enabled);ElMessage.success(`已${enabled?'启用':'停用'} ${result.updated||0} 个任务`);await load()}catch(e){ElMessage.error(e.message)}finally{batchTaskLoading.value=false}}
async function batchDeleteTasks(ids){if(!ids.length)return;try{await ElMessageBox.confirm(`确认批量删除选中的 ${ids.length} 个任务？此操作不可撤销。`,'批量删除任务',{type:'warning',confirmButtonText:'删除'});batchTaskLoading.value=true;const result=await api.batchDeleteTasks(ids);ElMessage.success(`已删除 ${result.deleted||0} 个任务`);await load()}catch(e){if(!['cancel','close'].includes(e))ElMessage.error(e.message)}finally{batchTaskLoading.value=false}}
async function runNow(row){runningTaskId.value=row.id;try{const result=await api.runTask(row.id);result.status==='success'?ElMessage.success(result.message):ElMessage.error(result.message);await load()}catch(e){ElMessage.error(e.message)}finally{runningTaskId.value=null}}
async function editTask(row){try{forms.value=await api.listForms(row.account_id);editingId.value=row.id;Object.assign(form,emptyForm(),JSON.parse(JSON.stringify(row)),{start_date:null,end_date:null});taskEditorVisible.value=true}catch(e){ElMessage.error(e.message)}}
async function removeTask(row){try{await ElMessageBox.confirm(`确认删除任务“${row.name}”？`,'删除任务',{type:'warning'});await api.deleteTask(row.id);ElMessage.success('已删除');await load()}catch(e){if(!['cancel','close'].includes(e))ElMessage.error(e.message)}}
function seedAnswers(fields,account,current={}){const result={...current};for(const field of fields){if(result[field.key]!==undefined&&result[field.key]!==''&&result[field.key]?.length!==0)continue;const title=String(field.title||'').replaceAll(' ','');let value='';if(title.includes('姓名'))value=account?.real_name||'';else if(title.includes('学号'))value=account?.school_no||'';else if(title.includes('班级'))value=account?.class_name||'';if(value&&field.options?.length){const matched=field.options.find(option=>String(option.value)===String(value)||String(option.label)===String(value));value=matched?.value||''}if(field.control==='multiple')value=value?[value]:[];if(value!==''||field.control==='multiple')result[field.key]=value}return result}
function answersValid(fields,answers){return fields.every(field=>{if(field.control==='unsupported')return !field.required;const value=answers?.[field.key];if(!field.required)return true;if(Array.isArray(value)){const size=value.length;return size>=Number(field.min_select||1)&&(!field.max_select||size<=Number(field.max_select))}return value!==undefined&&value!==null&&String(value).trim()!==''})}
watch(selectedFormId,()=>{manualCoordinate.value='';manualLocationName.value='';manualLocationInfo.value=emptyLocationInfo();manualAnswers.value=seedAnswers(manualFields.value,{...selectedAccount.value,...manualProfile},{})})
watch(()=>route.path,load);onMounted(load);onUnmounted(stopQr)
</script>

<style scoped>
.my-page{display:grid;gap:18px;min-width:0}.panel p{color:#64748b;font-size:13px}.panel{min-width:0;padding:20px;border:1px solid #dbeafe;border-radius:20px;background:#ffffffde;box-shadow:0 14px 34px #0f172a0a}.panel>header{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px}.panel h2{margin:0;color:#172033;font-size:18px}.panel header p{margin:4px 0 0}.panel header .el-input{max-width:320px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metrics article{display:grid;gap:5px;padding:22px;border:1px solid #dbeafe;border-radius:18px;background:#fff}.metrics b{font-size:28px;color:#1677ff}.metrics span{color:#64748b}.accounts-workspace{display:grid;grid-template-columns:minmax(300px,340px) minmax(0,1fr);align-items:start;gap:18px}.accounts-pane{position:sticky;top:16px;align-self:start}.checkin-pane{min-height:420px}.account-search{display:flex;align-items:center;gap:10px;margin-bottom:14px}.account-search .el-input{flex:1}.account-search span{flex:none;color:#64748b;font-size:12px}.account-list{display:grid;gap:10px;max-height:calc(100vh - 310px);padding-right:4px;overflow-y:auto;scrollbar-gutter:stable}.account-card{display:flex;align-items:center;gap:12px;min-width:0;padding:14px;border:1px solid #dbeafe;border-radius:16px;background:#f8fbff;cursor:pointer;transition:.18s}.account-card:hover,.account-card.active{border-color:#60a5fa;background:#eff6ff;box-shadow:0 8px 20px #2563eb12}.avatar{display:grid;place-items:center;width:44px;height:44px;flex:none;border-radius:14px;color:white;font-weight:800;background:linear-gradient(135deg,#2563eb,#06b6d4)}.account-info{display:grid;min-width:0;flex:1}.account-info span,.account-info small{overflow:hidden;color:#64748b;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.project-picker{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:12px;margin-bottom:14px;padding:12px 14px;border:1px solid #dbeafe;border-radius:14px;background:#f8fbff}.project-picker>span{color:#475569;font-size:13px;font-weight:700}.form-select{width:100%;margin:0}.option-state{float:right;margin-left:24px;color:#94a3b8}.manual-checkin{display:grid;gap:14px}.manual-head{display:grid;gap:6px;padding:14px 16px;border:1px solid #bfdbfe;border-radius:14px;background:linear-gradient(135deg,#eff6ff,#f8fbff)}.manual-head>div{display:flex;align-items:center;gap:9px}.manual-head small{color:#64748b;line-height:1.6;overflow-wrap:anywhere;white-space:normal}.manual-checkin :deep(.roster){margin-bottom:0;background:#fff}.location-section{display:grid;gap:12px;padding:16px;border:1px solid #bfdbfe;border-radius:16px;background:#fff}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-bottom:12px;border-bottom:1px solid #dbeafe}.section-heading strong,.section-heading small{display:block}.section-heading strong{color:#1e293b}.section-heading small{margin-top:3px;color:#64748b;font-size:12px}.manual-actions{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 16px;border:1px solid #bfdbfe;border-radius:16px;background:#eff6ff}.manual-actions>div{display:grid;gap:3px}.manual-actions small{color:#64748b;font-size:12px}.manual-actions .el-button{min-width:170px;margin:0}
.identity-fields{display:grid;gap:12px;padding:15px;border:1px solid #bfdbfe;border-radius:16px;background:#fff}.identity-title{display:flex;align-items:center;justify-content:space-between;gap:12px}.identity-title strong,.identity-title small{display:block}.identity-title small{margin-top:3px;color:#64748b;font-size:12px}.identity-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.identity-grid label{display:grid;gap:6px;min-width:0}.identity-grid label>span{color:#475569;font-size:13px}
.location-editor{display:grid;gap:10px;width:100%;min-width:0}.location-info-editor{display:grid;gap:12px;padding:14px;border:1px solid #dbeafe;border-radius:14px;background:#f8fbff}.location-info-title{display:flex;align-items:center;justify-content:space-between;gap:12px}.location-info-title strong,.location-info-title small{display:block}.location-info-title strong{color:#1e293b;font-size:13px}.location-info-title small{margin-top:3px;color:#64748b;font-size:11px}.location-info-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.location-info-grid label{display:grid;gap:6px;min-width:0}.location-info-grid label>span{color:#475569;font-size:12px;font-weight:600}.location-name-field{grid-column:span 2}.location-submit-preview{padding:9px 11px;border-radius:10px;background:#eff6ff;color:#1d4ed8;font-size:12px;overflow-wrap:anywhere}.task-panel{padding:0;overflow:hidden}.task-panel>header{padding:20px 20px 0}.task-panel :deep(.el-table){padding:0 20px 20px}.task-panel-head{align-items:flex-start!important}.task-panel-actions{display:flex;align-items:center;justify-content:flex-end;gap:10px}.task-panel-actions .el-input{width:260px}.task-panel-actions .el-button{margin:0}.task-cell{display:grid;gap:4px}.task-cell strong{color:#172033}.task-cell small{color:#64748b;font-size:11px}.muted{color:#94a3b8;font-size:12px}
:global(.miaoying-task-dialog){border-radius:20px;overflow:hidden}:global(.miaoying-task-dialog .el-dialog__body){max-height:calc(100vh - 170px);padding-top:8px;overflow-y:auto}:global(.miaoying-task-dialog .el-dialog__footer){border-top:1px solid #e2e8f0}.task-editor-layout{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.task-editor-section{min-width:0;padding:16px;border:1px solid #dbeafe;border-radius:18px;background:linear-gradient(145deg,#fff,#f8fbff)}.task-editor-section--wide{grid-column:1/-1}.task-editor-section>header{display:flex;align-items:center;gap:10px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #dbeafe}.task-editor-section>header strong,.task-editor-section>header small{display:block}.task-editor-section>header small{margin-top:2px;color:#64748b;font-size:11px}.section-index{display:grid;width:35px;height:35px;place-items:center;color:#fff;border-radius:11px;background:linear-gradient(135deg,#2563eb,#3b82f6);font-size:12px;font-weight:800}.task-editor-section :deep(.el-select),.task-editor-section :deep(.el-date-editor){width:100%}.project-select-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;width:100%}.schedule-list{display:grid;gap:8px;width:100%}.schedule-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.schedule-list>.el-button{width:100%;margin:0}.date-plan-card{display:flex;align-items:center;justify-content:space-between;gap:14px;width:100%;padding:13px;border:1px solid #bfdbfe;border-radius:14px;background:#eff6ff}.date-plan-card>div{display:grid;gap:5px}.date-plan-card strong{color:#1e3a8a;font-size:13px}.date-plan-card small{color:#64748b;font-size:11px}.task-enable-box{display:grid;gap:3px;padding:13px;border-radius:13px;background:#eff6ff}.task-enable-box small{color:#64748b;font-size:11px}.task-location-section{display:grid;gap:12px;margin-top:14px;padding:14px;border:1px solid #bfdbfe;border-radius:15px;background:#fff}.schedule-drawer-body{display:grid;gap:16px}.schedule-drawer-intro{display:grid;gap:4px;padding:14px;border:1px solid #dbeafe;border-radius:14px;background:#eff6ff}.schedule-drawer-intro small{color:#64748b;font-size:12px}
@media(max-width:1280px){.accounts-workspace{grid-template-columns:1fr}.accounts-pane{position:static}.account-list{grid-template-columns:repeat(2,minmax(0,1fr));max-height:360px}.metrics{grid-template-columns:repeat(2,1fr)}}@media(max-width:850px){.task-editor-layout{grid-template-columns:1fr}.task-editor-section--wide{grid-column:auto}.task-panel-actions{align-items:stretch;flex-direction:column}.task-panel-actions .el-input{width:100%}.location-info-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.location-name-field{grid-column:span 1}}@media(max-width:700px){.metrics{grid-template-columns:1fr}.panel{padding:14px}.task-panel{padding:0}.panel>header{align-items:flex-start;flex-direction:column}.panel header .el-input{max-width:none}.account-search{align-items:flex-start;flex-direction:column}.account-search .el-input{width:100%}.account-list{grid-template-columns:1fr;max-height:420px}.project-picker,.project-select-row{grid-template-columns:1fr}.identity-title,.location-info-title{align-items:flex-start}.identity-grid,.location-info-grid{grid-template-columns:1fr}.manual-actions{align-items:stretch;flex-direction:column}.manual-actions .el-button{width:100%;margin:0}}
.account-card{position:relative}.account-card.active{box-shadow:inset 4px 0 #3b82f6,0 8px 20px #2563eb12}.manual-actions{position:sticky;bottom:12px;z-index:8;border-color:#93c5fd;background:#eff6fff2;box-shadow:0 14px 30px #0f172a20;backdrop-filter:blur(12px)}.manual-action-summary{display:grid;min-width:0;gap:3px}.manual-action-summary>strong{overflow:hidden;color:#1e3a8a;text-overflow:ellipsis;white-space:nowrap}
@media(min-width:1051px) and (max-width:1280px){.accounts-workspace{grid-template-columns:minmax(270px,300px) minmax(0,1fr)}.accounts-pane{position:sticky}.account-list{display:grid;grid-template-columns:1fr;max-height:calc(100vh - 310px)}}@media(max-width:700px){.manual-actions{position:static}.manual-action-summary>strong{white-space:normal}}
</style>
