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
      <section class="panel"><header><h2>最近运行</h2></header><RunList :runs="runs.slice(0, 8)" /></section>
    </template>

    <section v-else-if="isAccounts" class="accounts-workspace">
      <div class="panel accounts-pane">
        <header><div><h2>秒应账号</h2><p>微信扫码登录并管理签到资料</p></div><el-button type="primary" @click="openQr">扫码添加</el-button></header>
        <div v-if="accounts.length" class="account-search"><el-input v-model="keyword" clearable placeholder="搜索昵称、备注或用户 ID" :prefix-icon="Search" /><span>显示 {{ filteredAccounts.length }}/{{ accounts.length }}</span></div>
        <div v-if="filteredAccounts.length" class="account-list">
          <article v-for="item in filteredAccounts" :key="item.id" class="account-card" :class="{ active: item.id === selectedAccountId }" @click="selectAccount(item.id)">
            <div class="avatar">{{ (item.remark || item.nickname || '秒').slice(0,1) }}</div>
            <div class="account-info"><b>{{ item.remark || item.nickname }}</b><span>{{ item.nickname }} · UID {{ item.remote_user_id }}</span><small>{{ item.class_name || '未填写班级' }} · {{ item.real_name || '未填写姓名' }} · {{ item.school_no || '未填写学号' }}</small></div>
            <el-tag :type="item.status === 'active' ? 'success' : 'danger'">{{ item.status === 'active' ? '有效' : '需重登' }}</el-tag>
            <el-dropdown @command="command => accountCommand(command,item)" @click.stop><el-button text>•••</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="edit">编辑资料</el-dropdown-item><el-dropdown-item command="sync">同步项目</el-dropdown-item><el-dropdown-item command="relogin">重新扫码</el-dropdown-item><el-dropdown-item command="delete" divided>删除</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
          </article>
        </div><el-empty v-else :description="accounts.length ? '没有找到匹配账号' : '暂无账号，请先扫码登录'" />
      </div>
      <div class="panel checkin-pane">
        <header><div><h2>签到中心</h2><p>选择签到项目后可直接地图选点并提交</p></div><el-button :icon="Refresh" :disabled="!selectedAccountId" :loading="formsSyncing" @click="syncAccountForms">同步签到项目</el-button></header>
        <el-select v-model="selectedFormId" class="form-select" :disabled="!selectedAccountId" placeholder="请选择签到项目">
          <el-option v-for="item in accountForms" :key="item.id" :value="item.id" :label="item.title"><span>{{ item.title }}</span><small class="option-state">{{ item.is_closed ? '已关闭' : item.requirements?.location ? '需要位置' : '普通签到' }}</small></el-option>
        </el-select>
        <el-empty v-if="!selectedAccountId" description="请先选择秒应账号" />
        <el-empty v-else-if="!accountForms.length" description="暂无签到项目，请点击同步签到项目" />
        <div v-else-if="selectedManualForm" class="manual-checkin">
          <div class="manual-head"><div><el-tag size="small" type="primary">{{ selectedManualForm.requirements?.location ? '位置签到' : '普通签到' }}</el-tag><strong>{{ selectedManualForm.title }}</strong></div><small>{{ selectedManualForm.content || '按项目要求提交签到' }}</small></div>
          <el-alert v-if="selectedManualForm.is_closed" type="warning" :closable="false" title="该签到项目已关闭" />
          <el-alert v-else-if="selectedManualForm.requirements?.unsupported?.length" type="warning" :closable="false" :title="`暂不支持：${selectedManualForm.requirements.unsupported.join('、')}`" />
          <div class="identity-fields">
            <div class="identity-title"><div><strong>签到身份</strong><small>保存到当前账号，并作为签到默认资料</small></div><el-button :loading="profileSaving" @click="saveManualProfile()">保存资料</el-button></div>
            <div class="identity-grid">
              <label><span>班级</span><el-input v-model="manualProfile.class_name" clearable placeholder="请输入班级" /></label>
              <label><span>{{ identityLabels.name_label }}</span><el-input v-model="manualProfile.real_name" clearable :placeholder="`请输入${identityLabels.name_label}`" /></label>
              <label><span>{{ identityLabels.number_label }}</span><el-input v-model="manualProfile.school_no" clearable :placeholder="`请输入${identityLabels.number_label}`" /></label>
            </div>
          </div>
          <DynamicFormFields v-if="manualFields.length" v-model="manualAnswers" :fields="manualFields" />
          <LocationSearchPanel v-if="selectedManualForm.requirements?.location" v-model="manualCoordinate" :location-api="api" />
          <div class="manual-actions"><el-checkbox v-model="manualNotify">发送企业微信通知</el-checkbox><el-button type="primary" size="large" :loading="manualChecking" :disabled="!canManualCheckin" @click="submitManualCheckin">执行签到</el-button></div>
        </div>
      </div>
    </section>

    <section v-else-if="isAuto" class="workspace">
      <div class="panel picker"><header><h2>账号与签到项目</h2></header>
        <el-select v-model="form.account_id" filterable placeholder="选择秒应账号" @change="accountChanged"><el-option v-for="a in accounts" :key="a.id" :label="a.remark || a.nickname" :value="a.id" /></el-select>
        <el-button :disabled="!form.account_id" @click="syncSelected">同步签到项目</el-button>
        <div class="form-list"><button v-for="item in forms" :key="item.id" :class="{active:form.form_id===item.id}" @click="selectForm(item)"><b>{{ item.title }}</b><span>{{ item.is_closed ? '已关闭' : item.requirements?.unsupported?.length ? '需人工处理' : '可配置自动签到' }}</span></button></div>
      </div>
      <div class="panel editor"><header><h2>{{ editingId ? '编辑任务' : '新建自动签到任务' }}</h2></header>
        <el-form label-width="88px"><el-form-item label="任务名称" required><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="每日时间" required><el-select v-model="form.schedule_times" multiple allow-create filterable default-first-option placeholder="输入 08:00:00 后回车" /></el-form-item>
          <el-form-item label="有效范围"><div class="range"><el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" /><el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" /></div></el-form-item>
          <el-form-item label="日期计划"><TaskDateSchedule v-model:date-mode="form.date_mode" v-model:run-dates="form.run_dates" v-model:skip-dates="form.skip_dates" v-model:skip-weekends="form.skip_weekends" v-model:auto-disable-after-finish="form.auto_disable_after_finish" :times="form.schedule_times" :min-date="form.start_date || ''" :max-date="form.end_date || ''" /></el-form-item>
          <DynamicFormFields v-if="taskFields.length" v-model="form.answers" :fields="taskFields" class="task-dynamic-fields" />
          <el-form-item label="签到位置"><LocationSearchPanel v-model="taskCoordinate" :location-api="api" /></el-form-item>
          <el-form-item><el-checkbox v-model="form.enabled">保存后启用</el-checkbox><el-button type="primary" @click="saveTask">保存任务</el-button><el-button @click="resetForm">重置</el-button></el-form-item>
        </el-form>
      </div>
    </section>

    <section v-else-if="isTasks" class="panel"><header><div><h2>自动签到任务</h2><p>可启停、立即执行或回到编辑页调整。</p></div><el-input v-model="keyword" clearable placeholder="搜索任务" :prefix-icon="Search" /></header>
      <el-table :data="filteredTasks"><el-table-column prop="name" label="任务" min-width="180" /><el-table-column label="时间" min-width="160"><template #default="{row}">{{ row.schedule_times.join('、') }}</template></el-table-column><el-table-column label="日期策略" width="120"><template #default="{row}">{{ row.date_mode === 'specific' ? '指定日期' : '每天执行' }}</template></el-table-column><el-table-column label="启用" width="90"><template #default="{row}"><el-switch v-model="row.enabled" @change="toggleTask(row)" /></template></el-table-column><el-table-column label="操作" width="230"><template #default="{row}"><el-button link type="primary" @click="runNow(row)">立即执行</el-button><el-button link @click="editTask(row)">编辑</el-button><el-button link type="danger" @click="removeTask(row)">删除</el-button></template></el-table-column></el-table>
    </section>

    <section v-else class="panel"><header><h2>{{ isLogs ? '秒应日志' : '运行记录' }}</h2></header><RunList :runs="runs" /></section>

    <el-dialog v-model="qrVisible" title="微信扫码登录秒应" width="420px" destroy-on-close @closed="stopQr">
      <div class="qr-box"><canvas ref="qrCanvas"></canvas><b>{{ qrStatus }}</b><span>请使用微信扫码，二维码 5 分钟内有效</span></div>
    </el-dialog>
    <el-dialog v-model="editVisible" title="编辑秒应账号" width="520px"><el-form label-width="82px"><el-form-item label="备注"><el-input v-model="accountForm.remark" /></el-form-item><el-form-item label="班级"><el-input v-model="accountForm.class_name" placeholder="作为签到项目班级字段的默认值" /></el-form-item><el-form-item label="姓名"><el-input v-model="accountForm.real_name" /></el-form-item><el-form-item label="学号"><el-input v-model="accountForm.school_no" /></el-form-item><el-form-item label="启用"><el-switch v-model="accountForm.enabled" /></el-form-item></el-form><template #footer><el-button @click="editVisible=false">取消</el-button><el-button type="primary" @click="saveAccount">保存</el-button></template></el-dialog>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, defineComponent, h, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import api from '../api/miaoying.js'
import TaskDateSchedule from '../components/TaskDateSchedule.vue'
import DynamicFormFields from '../components/miaoying/DynamicFormFields.vue'
import { parseCoordinates } from '../utils/classCubeTaskForm.js'

const LocationSearchPanel=defineAsyncComponent(()=>import('../components/class-cube/LocationSearchPanel.vue'))

const route=useRoute(), router=useRouter(), loading=ref(false), keyword=ref(''), accounts=ref([]),forms=ref([]),tasks=ref([]),runs=ref([])
const qrVisible=ref(false),qrCanvas=ref(),qrStatus=ref('正在生成二维码…'),qrId=ref('');let qrTimer
const editVisible=ref(false),editingAccount=ref(null),accountForm=reactive({remark:'',class_name:'',real_name:'',school_no:'',enabled:true}),editingId=ref(null)
const user=JSON.parse(localStorage.getItem('user')||'{}'),isAdmin=computed(()=>user.role==='admin')
const settings=reactive({miaoying_webhook_url:'',webhook_configured:false}),settingsSaving=ref(false)
const selectedAccountId=ref(null),selectedFormId=ref(null),accountForms=ref([]),formsSyncing=ref(false)
const manualCoordinate=ref(''),manualNotify=ref(true),manualChecking=ref(false),manualAnswers=ref({}),profileSaving=ref(false)
const manualProfile=reactive({class_name:'',real_name:'',school_no:''})
const emptyForm=()=>({account_id:null,form_id:null,name:'',enabled:true,schedule_times:['08:00:00'],start_date:null,end_date:null,date_mode:'daily',run_dates:[],skip_dates:[],skip_weekends:false,auto_disable_after_finish:true,location_name:'',latitude:null,longitude:null,answers:{},answer_schema:[]})
const form=reactive(emptyForm())
const path=computed(()=>route.path),isOverview=computed(()=>path.value.endsWith('/overview')),isAccounts=computed(()=>path.value.endsWith('/accounts')),isAuto=computed(()=>path.value.endsWith('/auto')),isTasks=computed(()=>path.value.endsWith('/tasks')),isLogs=computed(()=>path.value.endsWith('/logs'))
const filteredAccounts=computed(()=>accounts.value.filter(v=>`${v.nickname}${v.remark}${v.remote_user_id}`.toLowerCase().includes(keyword.value.toLowerCase())))
const filteredTasks=computed(()=>tasks.value.filter(v=>v.name.toLowerCase().includes(keyword.value.toLowerCase())))
const selectedManualForm=computed(()=>accountForms.value.find(item=>item.id===selectedFormId.value)||null)
const selectedAccount=computed(()=>accounts.value.find(item=>item.id===selectedAccountId.value)||null)
const manualFields=computed(()=>selectedManualForm.value?.requirements?.fields||[])
const identityLabels=computed(()=>selectedManualForm.value?.requirements?.identity||{class_label:'班级',name_label:'姓名',number_label:'学号'})
const selectedTaskForm=computed(()=>forms.value.find(item=>item.id===form.form_id)||null)
const taskFields=computed(()=>selectedTaskForm.value?.requirements?.fields||form.answer_schema||[])
const canManualCheckin=computed(()=>{
  const item=selectedManualForm.value
  if(!item||item.is_closed||item.requirements?.unsupported?.length)return false
  if(!answersValid(manualFields.value,manualAnswers.value))return false
  if(!item.requirements?.location)return true
  try{return Boolean(parseCoordinates(manualCoordinate.value))}catch{return false}
})
const taskCoordinate=computed({
  get:()=>form.latitude==null||form.longitude==null?'':`${form.latitude}, ${form.longitude}`,
  set:value=>{try{const point=parseCoordinates(value);form.latitude=point.latitude;form.longitude=point.longitude;form.location_name='地图选点'}catch{form.latitude=null;form.longitude=null;if(!String(value||'').trim())form.location_name=''}},
})
const format=v=>v?new Date(v).toLocaleString('zh-CN',{hour12:false}):'—'
const RunList=defineComponent({props:{runs:{type:Array,default:()=>[]}},setup(p){return()=>p.runs.length?h('div',{class:'run-list'},p.runs.map(v=>h('article',{class:`run ${v.status}`},[h('i'),h('div',[h('b',v.message||v.status),h('span',`${v.trigger==='manual'?'手动执行':'自动调度'} · ${format(v.started_at)}`)]),h('em',v.status==='success'?'成功':'失败')]))):h('div',{class:'empty-inline'},'暂无运行记录')}})
async function load(){loading.value=true;try{if(isAccounts.value){accounts.value=await api.listAccounts();if(!accounts.value.some(item=>item.id===selectedAccountId.value))selectedAccountId.value=accounts.value[0]?.id||null;await loadAccountForms()}else if(isAuto.value){[accounts.value,tasks.value]=await Promise.all([api.listAccounts(),api.listTasks()]);if(form.account_id)forms.value=await api.listForms(form.account_id)}else if(isTasks.value){tasks.value=await api.listTasks()}else if(isOverview.value){[accounts.value,tasks.value,runs.value]=await Promise.all([api.listAccounts(),api.listTasks(),api.listRuns()]);Object.assign(settings,await api.getSettings())}else{runs.value=await api.listRuns()}}catch(e){ElMessage.error(e.message)}finally{loading.value=false}}
async function openQr(){qrVisible.value=true;qrStatus.value='正在生成二维码…';try{const data=await api.createQr();qrId.value=data.id;await nextTick();await QRCode.toCanvas(qrCanvas.value,data.qr_content,{width:250,margin:2,color:{dark:'#0f172a',light:'#ffffff'}});qrStatus.value='等待扫码确认';qrTimer=window.setInterval(pollQr,1800)}catch(e){qrStatus.value=e.message;ElMessage.error(e.message)}}
async function pollQr(){if(!qrId.value)return;try{const data=await api.pollQr(qrId.value);if(data.status==='completed'){stopQr();qrStatus.value='登录成功';ElMessage.success('秒应账号添加成功');setTimeout(()=>{qrVisible.value=false;load()},500)}else if(data.status==='expired'){stopQr();qrStatus.value='二维码已过期，请关闭后重试'}}catch(e){stopQr();qrStatus.value=e.message}}
function stopQr(){if(qrTimer)window.clearInterval(qrTimer);qrTimer=null;qrId.value=''}
async function accountCommand(command,item){if(command==='edit'){editingAccount.value=item;Object.assign(accountForm,{remark:item.remark,class_name:item.class_name||'',real_name:item.real_name,school_no:item.school_no,enabled:item.enabled});editVisible.value=true}else if(command==='sync'){const synced=await api.syncForms(item.id);if(item.id===selectedAccountId.value){accountForms.value=synced;selectedFormId.value=synced[0]?.id||null;manualAnswers.value=seedAnswers(manualFields.value,selectedAccount.value,{})}ElMessage.success('项目同步完成')}else if(command==='relogin')openQr();else if(command==='delete'){await ElMessageBox.confirm('删除账号会同时删除关联项目和任务，是否继续？','删除账号',{type:'warning'});await api.deleteAccount(item.id);ElMessage.success('已删除');load()}}
async function saveAccount(){await api.updateAccount(editingAccount.value.id,{...accountForm});editVisible.value=false;ElMessage.success('保存成功');load()}
function syncManualProfile(){Object.assign(manualProfile,{class_name:selectedAccount.value?.class_name||'',real_name:selectedAccount.value?.real_name||'',school_no:selectedAccount.value?.school_no||''})}
async function loadAccountForms(){accountForms.value=selectedAccountId.value?await api.listForms(selectedAccountId.value):[];if(!accountForms.value.some(item=>item.id===selectedFormId.value))selectedFormId.value=accountForms.value[0]?.id||null;syncManualProfile();manualCoordinate.value='';manualAnswers.value=seedAnswers(manualFields.value,{...selectedAccount.value,...manualProfile},{})}
async function selectAccount(id){if(id===selectedAccountId.value)return;selectedAccountId.value=id;selectedFormId.value=null;await loadAccountForms()}
async function syncAccountForms(){if(!selectedAccountId.value)return;formsSyncing.value=true;try{accountForms.value=await api.syncForms(selectedAccountId.value);selectedFormId.value=accountForms.value[0]?.id||null;manualAnswers.value=seedAnswers(manualFields.value,selectedAccount.value,{});ElMessage.success('签到项目同步完成')}catch(e){ElMessage.error(e.message)}finally{formsSyncing.value=false}}
async function saveManualProfile(showMessage=true){const account=selectedAccount.value;if(!account)return false;if(!manualProfile.real_name.trim()||!manualProfile.school_no.trim()){ElMessage.warning(`请填写${identityLabels.value.name_label}和${identityLabels.value.number_label}`);return false}profileSaving.value=true;try{const updated=await api.updateAccount(account.id,{remark:account.remark||'',enabled:account.enabled,...manualProfile});Object.assign(account,updated);manualAnswers.value=seedAnswers(manualFields.value,account,manualAnswers.value);if(showMessage)ElMessage.success('签到资料已保存');return true}catch(e){ElMessage.error(e.message);return false}finally{profileSaving.value=false}}
async function submitManualCheckin(){const item=selectedManualForm.value;if(!item)return;if(!answersValid(manualFields.value,manualAnswers.value)){ElMessage.warning('请完整填写项目必填项');return}let point={latitude:null,longitude:null};if(item.requirements?.location){try{point=parseCoordinates(manualCoordinate.value)}catch(e){ElMessage.warning(e.message);return}}manualChecking.value=true;try{if(!await saveManualProfile(false))return;const result=await api.manualCheckin(item.id,{account_id:selectedAccountId.value,location_name:'地图选点',answers:manualAnswers.value,...point,notify_wecom:manualNotify.value});ElMessage.success(result.message||'签到成功');if(result.notification?.reason==='send_failed')ElMessage.warning('签到成功，但企业微信通知发送失败')}catch(e){ElMessage.error(e.message)}finally{manualChecking.value=false}}
async function saveSettings(){settingsSaving.value=true;try{Object.assign(settings,await api.updateSettings({miaoying_webhook_url:settings.miaoying_webhook_url}));ElMessage.success('秒应通知配置已保存')}catch(e){ElMessage.error(e.message)}finally{settingsSaving.value=false}}
async function accountChanged(){forms.value=form.account_id?await api.listForms(form.account_id):[];form.form_id=null;form.answers={}}
async function syncSelected(){forms.value=await api.syncForms(form.account_id);ElMessage.success('项目同步完成')}
function selectForm(item){form.form_id=item.id;if(!form.name)form.name=item.title;if(item.remote_schedule_times?.length)form.schedule_times=[...item.remote_schedule_times];form.answers=seedAnswers(item.requirements?.fields||[],accounts.value.find(a=>a.id===form.account_id),form.answers)}
async function saveTask(){if(!form.account_id||!form.form_id||!form.name){ElMessage.warning('请选择账号和签到项目并填写任务名称');return}if(selectedTaskForm.value?.requirements?.unsupported?.length){ElMessage.warning(`暂不支持：${selectedTaskForm.value.requirements.unsupported.join('、')}`);return}if(!answersValid(taskFields.value,form.answers)){ElMessage.warning('请完整填写项目必填项');return}const fn=editingId.value?api.updateTask(editingId.value,{...form}):api.createTask({...form});await fn;ElMessage.success('任务保存成功');resetForm();await load()}
function resetForm(){Object.assign(form,emptyForm());forms.value=[];editingId.value=null}
async function toggleTask(row){await api.updateTask(row.id,{...row});ElMessage.success(row.enabled?'任务已启用':'任务已停用')}
async function runNow(row){const result=await api.runTask(row.id);result.status==='success'?ElMessage.success(result.message):ElMessage.error(result.message);load()}
function editTask(row){editingId.value=row.id;Object.assign(form,JSON.parse(JSON.stringify(row)));router.push('/miaoying/auto')}
async function removeTask(row){await ElMessageBox.confirm(`确认删除任务“${row.name}”？`,'删除任务',{type:'warning'});await api.deleteTask(row.id);ElMessage.success('已删除');load()}
function seedAnswers(fields,account,current={}){const result={...current};for(const field of fields){if(result[field.key]!==undefined&&result[field.key]!==''&&result[field.key]?.length!==0)continue;const title=String(field.title||'').replaceAll(' ','');let value='';if(title.includes('姓名'))value=account?.real_name||'';else if(title.includes('学号'))value=account?.school_no||'';else if(title.includes('班级'))value=account?.class_name||'';if(value&&field.options?.length){const matched=field.options.find(option=>String(option.value)===String(value)||String(option.label)===String(value));value=matched?.value||''}if(field.control==='multiple')value=value?[value]:[];if(value!==''||field.control==='multiple')result[field.key]=value}return result}
function answersValid(fields,answers){return fields.every(field=>{if(field.control==='unsupported')return !field.required;const value=answers?.[field.key];if(!field.required)return true;if(Array.isArray(value)){const size=value.length;return size>=Number(field.min_select||1)&&(!field.max_select||size<=Number(field.max_select))}return value!==undefined&&value!==null&&String(value).trim()!==''})}
watch(selectedFormId,()=>{manualCoordinate.value='';manualAnswers.value=seedAnswers(manualFields.value,{...selectedAccount.value,...manualProfile},{})})
watch(()=>route.path,load);onMounted(load);onUnmounted(stopQr)
</script>

<style scoped>
.my-page{display:grid;gap:18px;min-width:0}.panel p{color:#64748b;font-size:13px}.panel{min-width:0;padding:20px;border:1px solid #dbeafe;border-radius:20px;background:#ffffffde;box-shadow:0 14px 34px #0f172a0a}.panel>header{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px}.panel h2{margin:0;color:#172033;font-size:18px}.panel header p{margin:4px 0 0}.panel header .el-input{max-width:320px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metrics article{display:grid;gap:5px;padding:22px;border:1px solid #dbeafe;border-radius:18px;background:#fff}.metrics b{font-size:28px;color:#1677ff}.metrics span{color:#64748b}.settings-panel{max-width:none}.accounts-workspace{display:grid;grid-template-columns:minmax(320px,.42fr) minmax(520px,.58fr);align-items:start;gap:16px}.accounts-pane,.checkin-pane{min-height:420px}.account-search{display:flex;align-items:center;gap:10px;margin-bottom:14px}.account-search .el-input{flex:1}.account-search span{flex:none;color:#64748b;font-size:12px}.account-list{display:grid;gap:10px;max-height:620px;padding-right:6px;overflow-y:auto;scrollbar-gutter:stable}.account-card{display:flex;align-items:center;gap:12px;min-width:0;padding:14px;border:1px solid #dbeafe;border-radius:16px;background:#f8fbff;cursor:pointer;transition:.18s}.account-card:hover,.account-card.active{border-color:#60a5fa;background:#eff6ff;box-shadow:0 8px 20px #2563eb12}.avatar{display:grid;place-items:center;width:44px;height:44px;flex:none;border-radius:14px;color:white;font-weight:800;background:linear-gradient(135deg,#2563eb,#06b6d4)}.account-info{display:grid;min-width:0;flex:1}.account-info span,.account-info small{overflow:hidden;color:#64748b;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.form-select{width:100%;margin-bottom:14px}.option-state{float:right;margin-left:24px;color:#94a3b8}.manual-checkin{display:grid;gap:14px}.manual-head{display:grid;gap:6px;padding:14px;border:1px solid #dbeafe;border-radius:14px;background:#f8fbff}.manual-head>div{display:flex;align-items:center;gap:9px}.manual-head small{overflow:hidden;color:#64748b;text-overflow:ellipsis;white-space:nowrap}.manual-actions{display:flex;align-items:center;justify-content:space-between;gap:14px;padding-top:4px}.manual-actions .el-button{min-width:150px}.workspace{display:grid;grid-template-columns:minmax(280px,.72fr) minmax(480px,1.28fr);gap:16px}.picker>.el-select{width:100%;margin-bottom:10px}.picker>.el-button{width:100%;margin:0 0 14px}.form-list{display:grid;gap:8px;max-height:520px;overflow:auto}.form-list button{display:grid;gap:4px;padding:13px;text-align:left;border:1px solid #dbeafe;border-radius:13px;background:#f8fbff;color:#1e293b;cursor:pointer}.form-list button.active{border-color:#60a5fa;background:#eff6ff;box-shadow:inset 3px 0 #3b82f6}.form-list span{font-size:12px;color:#64748b}.range{display:flex;gap:8px;width:100%;flex-wrap:wrap}.range>*{flex:1}.task-dynamic-fields{margin:0 0 18px 88px}.qr-box{display:grid;place-items:center;gap:10px;text-align:center}.qr-box canvas{border:1px solid #dbeafe;border-radius:16px}.qr-box span{color:#64748b;font-size:12px}:deep(.run-list){display:grid;gap:9px}:deep(.run){display:flex;align-items:center;gap:12px;padding:14px;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc}:deep(.run i){width:10px;height:10px;border-radius:50%;background:#ef4444}:deep(.run.success i){background:#22c55e}:deep(.run div){display:grid;flex:1}:deep(.run span){color:#64748b;font-size:12px}:deep(.run em){font-style:normal;color:#ef4444}:deep(.run.success em){color:#16a34a}:deep(.empty-inline){padding:50px;text-align:center;color:#94a3b8}
.identity-fields{display:grid;gap:12px;padding:15px;border:1px solid #bfdbfe;border-radius:16px;background:#fff}.identity-title{display:flex;align-items:center;justify-content:space-between;gap:12px}.identity-title strong,.identity-title small{display:block}.identity-title small{margin-top:3px;color:#64748b;font-size:12px}.identity-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.identity-grid label{display:grid;gap:6px;min-width:0}.identity-grid label>span{color:#475569;font-size:13px}
@media(max-width:1180px){.accounts-workspace,.workspace{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}}@media(max-width:700px){.metrics{grid-template-columns:1fr}.panel>header{align-items:flex-start;flex-direction:column}.panel header .el-input{max-width:none}.account-search{align-items:flex-start;flex-direction:column}.account-search .el-input{width:100%}.editor{padding:14px}:deep(.editor .el-form-item){display:block}:deep(.editor .el-form-item__label){justify-content:flex-start}.task-dynamic-fields{margin-left:0}.identity-title{align-items:flex-start}.identity-grid{grid-template-columns:1fr}.manual-actions{align-items:stretch;flex-direction:column}.manual-actions .el-button{width:100%;margin:0}.range>*{min-width:100%!important}}
</style>
