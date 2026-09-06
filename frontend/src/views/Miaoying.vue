<template>
  <div class="my-page" v-loading="loading">
    <section class="hero">
      <img src="../img/miaoying.png" alt="秒应" />
      <div><p>MIAOYING AUTOMATION</p><h1>{{ pageTitle }}</h1><span>微信扫码登录，集中管理签到项目、日期计划与执行结果。</span></div>
      <el-button v-if="isAccounts" type="primary" @click="openQr">微信扫码添加账号</el-button>
      <el-button v-else :icon="Refresh" @click="load">刷新数据</el-button>
    </section>

    <template v-if="isOverview">
      <div class="metrics">
        <article><b>{{ accounts.length }}</b><span>登录账号</span></article><article><b>{{ tasks.length }}</b><span>全部任务</span></article>
        <article><b>{{ tasks.filter(v => v.enabled).length }}</b><span>启用任务</span></article><article><b>{{ runs.filter(v => v.status === 'success').length }}</b><span>成功执行</span></article>
      </div>
      <section class="panel"><header><h2>最近运行</h2></header><RunList :runs="runs.slice(0, 8)" /></section>
    </template>

    <section v-else-if="isAccounts" class="panel">
      <header><div><h2>秒应账号</h2><p>仅支持微信扫码登录，凭据加密保存。</p></div><el-input v-model="keyword" clearable placeholder="搜索昵称、备注或用户 ID" :prefix-icon="Search" /></header>
      <div v-if="filteredAccounts.length" class="account-grid">
        <article v-for="item in filteredAccounts" :key="item.id" class="account-card">
          <div class="avatar">{{ (item.remark || item.nickname || '秒').slice(0,1) }}</div>
          <div class="account-info"><b>{{ item.remark || item.nickname }}</b><span>{{ item.nickname }} · UID {{ item.remote_user_id }}</span><small>最近验证 {{ format(item.last_verified_at) }}</small></div>
          <el-tag :type="item.status === 'active' ? 'success' : 'danger'">{{ item.status === 'active' ? '有效' : '需重登' }}</el-tag>
          <el-dropdown @command="command => accountCommand(command,item)"><el-button text>•••</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="edit">编辑资料</el-dropdown-item><el-dropdown-item command="sync">同步项目</el-dropdown-item><el-dropdown-item command="relogin">重新扫码</el-dropdown-item><el-dropdown-item command="delete" divided>删除</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
        </article>
      </div><el-empty v-else description="暂无秒应账号" />
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
          <el-form-item label="签到位置"><div class="location"><el-input v-model="form.location_name" placeholder="位置名称（项目要求位置时填写）" /><el-input-number v-model="form.latitude" :precision="8" placeholder="纬度" /><el-input-number v-model="form.longitude" :precision="8" placeholder="经度" /></div></el-form-item>
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
    <el-dialog v-model="editVisible" title="编辑秒应账号" width="520px"><el-form label-width="82px"><el-form-item label="备注"><el-input v-model="accountForm.remark" /></el-form-item><el-form-item label="姓名"><el-input v-model="accountForm.real_name" /></el-form-item><el-form-item label="学号"><el-input v-model="accountForm.school_no" /></el-form-item><el-form-item label="启用"><el-switch v-model="accountForm.enabled" /></el-form-item></el-form><template #footer><el-button @click="editVisible=false">取消</el-button><el-button type="primary" @click="saveAccount">保存</el-button></template></el-dialog>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import api from '../api/miaoying.js'
import TaskDateSchedule from '../components/TaskDateSchedule.vue'

const route=useRoute(), router=useRouter(), loading=ref(false), keyword=ref(''), accounts=ref([]),forms=ref([]),tasks=ref([]),runs=ref([])
const qrVisible=ref(false),qrCanvas=ref(),qrStatus=ref('正在生成二维码…'),qrId=ref('');let qrTimer
const editVisible=ref(false),editingAccount=ref(null),accountForm=reactive({remark:'',real_name:'',school_no:'',enabled:true}),editingId=ref(null)
const emptyForm=()=>({account_id:null,form_id:null,name:'',enabled:true,schedule_times:['08:00:00'],start_date:null,end_date:null,date_mode:'daily',run_dates:[],skip_dates:[],skip_weekends:false,auto_disable_after_finish:true,location_name:'',latitude:null,longitude:null})
const form=reactive(emptyForm())
const path=computed(()=>route.path),isOverview=computed(()=>path.value.endsWith('/overview')),isAccounts=computed(()=>path.value.endsWith('/accounts')),isAuto=computed(()=>path.value.endsWith('/auto')),isTasks=computed(()=>path.value.endsWith('/tasks')),isLogs=computed(()=>path.value.endsWith('/logs'))
const pageTitle=computed(()=>isOverview.value?'秒应系统概览':isAccounts.value?'秒应账号管理':isAuto.value?'秒应自动签到':isTasks.value?'秒应任务管理':isLogs.value?'秒应日志':'秒应运行记录')
const filteredAccounts=computed(()=>accounts.value.filter(v=>`${v.nickname}${v.remark}${v.remote_user_id}`.toLowerCase().includes(keyword.value.toLowerCase())))
const filteredTasks=computed(()=>tasks.value.filter(v=>v.name.toLowerCase().includes(keyword.value.toLowerCase())))
const format=v=>v?new Date(v).toLocaleString('zh-CN',{hour12:false}):'—'
const RunList=defineComponent({props:{runs:{type:Array,default:()=>[]}},setup(p){return()=>p.runs.length?h('div',{class:'run-list'},p.runs.map(v=>h('article',{class:`run ${v.status}`},[h('i'),h('div',[h('b',v.message||v.status),h('span',`${v.trigger==='manual'?'手动执行':'自动调度'} · ${format(v.started_at)}`)]),h('em',v.status==='success'?'成功':'失败')]))):h('div',{class:'empty-inline'},'暂无运行记录')}})
async function load(){loading.value=true;try{if(isAccounts.value){accounts.value=await api.listAccounts()}else if(isAuto.value){[accounts.value,tasks.value]=await Promise.all([api.listAccounts(),api.listTasks()]);if(form.account_id)forms.value=await api.listForms(form.account_id)}else if(isTasks.value){tasks.value=await api.listTasks()}else if(isOverview.value){[accounts.value,tasks.value,runs.value]=await Promise.all([api.listAccounts(),api.listTasks(),api.listRuns()])}else{runs.value=await api.listRuns()}}catch(e){ElMessage.error(e.message)}finally{loading.value=false}}
async function openQr(){qrVisible.value=true;qrStatus.value='正在生成二维码…';try{const data=await api.createQr();qrId.value=data.id;await nextTick();await QRCode.toCanvas(qrCanvas.value,data.qr_content,{width:250,margin:2,color:{dark:'#0f172a',light:'#ffffff'}});qrStatus.value='等待扫码确认';qrTimer=window.setInterval(pollQr,1800)}catch(e){qrStatus.value=e.message;ElMessage.error(e.message)}}
async function pollQr(){if(!qrId.value)return;try{const data=await api.pollQr(qrId.value);if(data.status==='completed'){stopQr();qrStatus.value='登录成功';ElMessage.success('秒应账号添加成功');setTimeout(()=>{qrVisible.value=false;load()},500)}else if(data.status==='expired'){stopQr();qrStatus.value='二维码已过期，请关闭后重试'}}catch(e){stopQr();qrStatus.value=e.message}}
function stopQr(){if(qrTimer)window.clearInterval(qrTimer);qrTimer=null;qrId.value=''}
async function accountCommand(command,item){if(command==='edit'){editingAccount.value=item;Object.assign(accountForm,{remark:item.remark,real_name:item.real_name,school_no:item.school_no,enabled:item.enabled});editVisible.value=true}else if(command==='sync'){await api.syncForms(item.id);ElMessage.success('项目同步完成')}else if(command==='relogin')openQr();else if(command==='delete'){await ElMessageBox.confirm('删除账号会同时删除关联项目和任务，是否继续？','删除账号',{type:'warning'});await api.deleteAccount(item.id);ElMessage.success('已删除');load()}}
async function saveAccount(){await api.updateAccount(editingAccount.value.id,{...accountForm});editVisible.value=false;ElMessage.success('保存成功');load()}
async function accountChanged(){forms.value=form.account_id?await api.listForms(form.account_id):[];form.form_id=null}
async function syncSelected(){forms.value=await api.syncForms(form.account_id);ElMessage.success('项目同步完成')}
function selectForm(item){form.form_id=item.id;if(!form.name)form.name=item.title;if(item.remote_schedule_times?.length)form.schedule_times=[...item.remote_schedule_times]}
async function saveTask(){if(!form.account_id||!form.form_id||!form.name){ElMessage.warning('请选择账号和签到项目并填写任务名称');return}const fn=editingId.value?api.updateTask(editingId.value,{...form}):api.createTask({...form});await fn;ElMessage.success('任务保存成功');resetForm();await load()}
function resetForm(){Object.assign(form,emptyForm());forms.value=[];editingId.value=null}
async function toggleTask(row){await api.updateTask(row.id,{...row});ElMessage.success(row.enabled?'任务已启用':'任务已停用')}
async function runNow(row){const result=await api.runTask(row.id);result.status==='success'?ElMessage.success(result.message):ElMessage.error(result.message);load()}
function editTask(row){editingId.value=row.id;Object.assign(form,JSON.parse(JSON.stringify(row)));router.push('/miaoying/auto')}
async function removeTask(row){await ElMessageBox.confirm(`确认删除任务“${row.name}”？`,'删除任务',{type:'warning'});await api.deleteTask(row.id);ElMessage.success('已删除');load()}
watch(()=>route.path,load);onMounted(load);onUnmounted(stopQr)
</script>

<style scoped>
.my-page{display:grid;gap:18px;min-width:0}.hero{display:flex;align-items:center;gap:18px;padding:22px 26px;border:1px solid #dbeafe;border-radius:22px;background:linear-gradient(125deg,#eff8ff,#f0fdf4);box-shadow:0 16px 38px #0f172a0d}.hero img{width:64px;height:64px;padding:6px;border-radius:18px;background:#fff}.hero div{flex:1;min-width:0}.hero p{margin:0;color:#168ac5;font-size:11px;font-weight:800;letter-spacing:.15em}.hero h1{margin:5px 0 4px;font-size:25px;color:#0f172a}.hero span,.panel p{color:#64748b;font-size:13px}.panel{min-width:0;padding:20px;border:1px solid #dbeafe;border-radius:20px;background:#ffffffde;box-shadow:0 14px 34px #0f172a0a}.panel>header{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px}.panel h2{margin:0;color:#172033;font-size:18px}.panel header p{margin:4px 0 0}.panel header .el-input{max-width:320px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metrics article{display:grid;gap:5px;padding:22px;border:1px solid #dbeafe;border-radius:18px;background:#fff}.metrics b{font-size:28px;color:#1677ff}.metrics span{color:#64748b}.account-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;max-height:560px;overflow:auto;padding-right:6px}.account-card{display:flex;align-items:center;gap:12px;min-width:0;padding:16px;border:1px solid #dbeafe;border-radius:16px;background:#f8fbff}.avatar{display:grid;place-items:center;width:44px;height:44px;flex:none;border-radius:14px;color:white;font-weight:800;background:linear-gradient(135deg,#2563eb,#06b6d4)}.account-info{display:grid;min-width:0;flex:1}.account-info span,.account-info small{overflow:hidden;color:#64748b;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.workspace{display:grid;grid-template-columns:minmax(280px,.72fr) minmax(480px,1.28fr);gap:16px}.picker>.el-select{width:100%;margin-bottom:10px}.picker>.el-button{width:100%;margin:0 0 14px}.form-list{display:grid;gap:8px;max-height:520px;overflow:auto}.form-list button{display:grid;gap:4px;padding:13px;text-align:left;border:1px solid #dbeafe;border-radius:13px;background:#f8fbff;color:#1e293b;cursor:pointer}.form-list button.active{border-color:#60a5fa;background:#eff6ff;box-shadow:inset 3px 0 #3b82f6}.form-list span{font-size:12px;color:#64748b}.range,.location{display:flex;gap:8px;width:100%;flex-wrap:wrap}.range>*{flex:1}.location .el-input{flex:2;min-width:220px}.location .el-input-number{flex:1;min-width:160px}.qr-box{display:grid;place-items:center;gap:10px;text-align:center}.qr-box canvas{border:1px solid #dbeafe;border-radius:16px}.qr-box span{color:#64748b;font-size:12px}:deep(.run-list){display:grid;gap:9px}:deep(.run){display:flex;align-items:center;gap:12px;padding:14px;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc}:deep(.run i){width:10px;height:10px;border-radius:50%;background:#ef4444}:deep(.run.success i){background:#22c55e}:deep(.run div){display:grid;flex:1}:deep(.run span){color:#64748b;font-size:12px}:deep(.run em){font-style:normal;color:#ef4444}:deep(.run.success em){color:#16a34a}:deep(.empty-inline){padding:50px;text-align:center;color:#94a3b8}
@media(max-width:1050px){.workspace{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}}@media(max-width:700px){.hero{align-items:flex-start;flex-wrap:wrap}.hero img{width:52px;height:52px}.hero h1{font-size:21px}.account-grid,.metrics{grid-template-columns:1fr}.panel>header{align-items:flex-start;flex-direction:column}.panel header .el-input{max-width:none}.editor{padding:14px}:deep(.editor .el-form-item){display:block}:deep(.editor .el-form-item__label){justify-content:flex-start}.location>*{min-width:100%!important}}
</style>
