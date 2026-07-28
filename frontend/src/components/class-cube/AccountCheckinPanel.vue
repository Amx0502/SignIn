<template>
  <div class="account-checkin">
    <section class="stats-grid">
      <article><span class="stat-icon blue"><el-icon><User /></el-icon></span><div><strong>{{ accounts.length }}</strong><small>登录账号</small></div></article>
      <article><span class="stat-icon cyan"><el-icon><Reading /></el-icon></span><div><strong>{{ courses.length }}</strong><small>当前课程</small></div></article>
      <article><span class="stat-icon green"><el-icon><CircleCheck /></el-icon></span><div><strong>{{ activeItems }}</strong><small>活动签到</small></div></article>
      <article><span class="stat-icon violet"><el-icon><Timer /></el-icon></span><div><strong>{{ enabledTasks }}</strong><small>启用任务</small></div></article>
    </section>

    <div class="workspace-grid">
      <el-card class="glass-card account-card" shadow="never">
        <template #header>
          <div class="section-head">
            <div><strong>班级魔方账号</strong><small>扫码登录并管理课程凭据</small></div>
            <el-button type="primary" :icon="Plus" @click="emit('qr-login', null)">扫码添加</el-button>
          </div>
        </template>
        <el-empty v-if="!accounts.length" description="暂无账号，请先扫码登录" :image-size="78" />
        <div v-else class="account-list">
          <article
            v-for="account in accounts"
            :key="account.id"
            class="account-row"
            :class="{ active: account.id === selectedAccountId }"
            @click="emit('select-account', account.id)"
          >
            <span class="avatar">{{ (account.remote_user_name || account.name || '班').slice(0, 1) }}</span>
            <div class="account-main">
              <strong>{{ account.name || account.remote_user_name || `账号 ${account.id}` }}</strong>
              <small>{{ account.remote_user_name || '未获取平台姓名' }}</small>
            </div>
            <el-tag :type="account.status === 'active' ? 'success' : 'danger'" size="small">
              {{ account.status === 'active' ? '有效' : account.status === 'expired' ? '已失效' : '已停用' }}
            </el-tag>
            <el-dropdown trigger="click" @command="command => accountCommand(command, account)" @click.stop>
              <el-button text circle :icon="MoreFilled" aria-label="账号操作" />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rescan">重新扫码</el-dropdown-item>
                  <el-dropdown-item command="rename">编辑备注</el-dropdown-item>
                  <el-dropdown-item command="sync">同步课程</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除账号</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </article>
        </div>
      </el-card>

      <el-card class="glass-card checkin-card" shadow="never">
        <template #header>
          <div class="section-head">
            <div><strong>课程签到中心</strong><small>选择课程后同步当前签到项</small></div>
            <el-button
              :icon="Refresh"
              :disabled="!selectedCourseId"
              :loading="syncing"
              @click="emit('sync-items', selectedCourseId)"
            >同步签到项</el-button>
          </div>
        </template>
        <div class="selector-row">
          <el-select
            :model-value="selectedCourseId"
            placeholder="请选择课程"
            :disabled="!selectedAccountId"
            @change="value => emit('select-course', value)"
          >
            <el-option v-for="course in courses" :key="course.id" :value="course.id" :label="course.name">
              <span>{{ course.name }}</span><small class="option-code">{{ course.class_code || course.remote_course_id }}</small>
            </el-option>
          </el-select>
          <span v-if="selectedCourse" class="course-code">班级码 {{ selectedCourse.class_code || '—' }}</span>
        </div>

        <el-empty v-if="!selectedCourseId" description="先选择账号与课程" :image-size="88" />
        <el-empty v-else-if="!items.length" description="当前课程暂无签到项" :image-size="88" />
        <div v-else class="item-list">
          <article
            v-for="item in items"
            :key="item.id"
            class="item-row"
            :class="{ active: item.id === selectedItemId }"
            @click="emit('select-item', item.id)"
          >
            <span class="mode-icon" :class="item.mode"><el-icon><component :is="modeMeta(item.mode).icon" /></el-icon></span>
            <div><strong>{{ item.title || `签到项 ${item.remote_item_id}` }}</strong><small>{{ modeMeta(item.mode).label }} · {{ item.remote_module }}</small></div>
            <el-tag :type="item.status === 'active' ? 'success' : 'info'" size="small">{{ item.status === 'active' ? '进行中' : item.status }}</el-tag>
          </article>
        </div>

        <div v-if="selectedItem" class="manual-form">
          <div class="manual-form__head">
            <div><span class="mode-chip">{{ modeMeta(selectedItem.mode).label }}</span><strong>{{ selectedItem.title }}</strong></div>
            <small>只提交页面要求的字段，结果由服务端严格判断</small>
          </div>
          <el-form label-position="top">
            <div v-if="['gps', 'gps_photo'].includes(selectedItem.mode)" class="location-grid">
              <el-form-item label="纬度"><el-input-number v-model="form.latitude" :precision="6" :controls="false" placeholder="例如 39.904200" /></el-form-item>
              <el-form-item label="经度"><el-input-number v-model="form.longitude" :precision="6" :controls="false" placeholder="例如 116.407400" /></el-form-item>
              <el-form-item label="定位精度（米）"><el-input-number v-model="form.accuracy" :min="0" :precision="1" :controls="false" /></el-form-item>
            </div>
            <el-form-item v-if="selectedItem.mode === 'gps_photo'" label="签到照片">
              <TaskImageUpload :file-list="photoFiles" :limit="1" :http-request="uploadPhoto" :on-remove="removePhoto" />
              <p class="field-tip">支持 JPEG、PNG、WEBP，预览使用服务端返回的完整 URL。</p>
            </el-form-item>
            <el-form-item v-if="selectedItem.mode === 'password'" label="签到密码">
              <el-input v-model="form.password" type="password" show-password maxlength="128" autocomplete="off" placeholder="请输入本次签到密码" />
            </el-form-item>
            <el-alert v-if="selectedItem.mode === 'qr'" title="二维码签到无需额外参数，将按远程签到页的明确表单提交。" type="info" :closable="false" show-icon />
            <el-button type="primary" size="large" :loading="checkingIn" @click="submitManual">
              <el-icon><Position /></el-icon>执行{{ modeMeta(selectedItem.mode).label }}
            </el-button>
          </el-form>
        </div>
      </el-card>
    </div>

    <el-dialog v-model="resultVisible" class="cube-result-dialog" width="500px" align-center append-to-body>
      <div v-if="result" class="result-content" :class="`is-${result.status}`">
        <span class="result-icon"><el-icon><component :is="resultMeta.icon" /></el-icon></span>
        <small>{{ resultMeta.eyebrow }}</small>
        <h2>{{ resultMeta.label }}</h2>
        <p>{{ result.message || resultMeta.tip }}</p>
        <el-tag :type="resultMeta.type" effect="dark">{{ result.status }}</el-tag>
      </div>
      <template #footer><el-button type="primary" @click="resultVisible = false">完成</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import {
  Aim, Camera, Cellphone, CircleCheck, CircleCheckFilled, CircleCloseFilled,
  Key, Lock, MoreFilled, Plus, Position, Reading, Refresh, Timer, User, WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import TaskImageUpload from '../TaskImageUpload.vue'

const props = defineProps({
  accounts: { type: Array, default: () => [] },
  courses: { type: Array, default: () => [] },
  items: { type: Array, default: () => [] },
  tasks: { type: Array, default: () => [] },
  selectedAccountId: { type: Number, default: null },
  selectedCourseId: { type: Number, default: null },
  selectedItemId: { type: Number, default: null },
  selectedCourse: { type: Object, default: null },
  selectedItem: { type: Object, default: null },
  uploadPhotoAction: { type: Function, required: true },
  manualCheckinAction: { type: Function, required: true },
})
const emit = defineEmits(['qr-login', 'select-account', 'select-course', 'select-item', 'sync-courses', 'sync-items', 'rename-account', 'delete-account'])
const syncing = ref(false)
const checkingIn = ref(false)
const resultVisible = ref(false)
const result = ref(null)
const photoFiles = ref([])
const form = reactive({ latitude: null, longitude: null, accuracy: 20, photo_path: '', password: '' })

const activeItems = computed(() => props.items.filter(item => item.status === 'active').length)
const enabledTasks = computed(() => props.tasks.filter(task => task.enabled).length)
const modes = {
  qr: { label: '二维码签到', icon: Cellphone },
  gps: { label: 'GPS 签到', icon: Aim },
  gps_photo: { label: 'GPS+拍照签到', icon: Camera },
  password: { label: '密码签到', icon: Key },
  unknown: { label: '未知类型', icon: WarningFilled },
}
const results = {
  success: { label: '签到成功', eyebrow: 'CHECK-IN COMPLETED', tip: '远程平台已明确确认签到成功', icon: CircleCheckFilled, type: 'success' },
  already_signed: { label: '已经签到', eyebrow: 'ALREADY COMPLETED', tip: '远程平台确认该签到已完成', icon: CircleCheckFilled, type: 'success' },
  waiting_parameter: { label: '等待补充参数', eyebrow: 'ACTION REQUIRED', tip: '请补充签到需要的位置、照片或密码', icon: WarningFilled, type: 'warning' },
  unknown_result: { label: '结果未知', eyebrow: 'RESULT UNKNOWN', tip: '提交结果无法确认，为避免重复签到不会自动重试', icon: WarningFilled, type: 'warning' },
  failed: { label: '签到失败', eyebrow: 'CHECK-IN FAILED', tip: '远程平台未确认签到成功', icon: CircleCloseFilled, type: 'danger' },
  skipped: { label: '已跳过', eyebrow: 'CHECK-IN SKIPPED', tip: '本次签到未发起提交', icon: Lock, type: 'info' },
}
const resultMeta = computed(() => results[result.value?.status] || results.failed)
function modeMeta(mode) { return modes[mode] || modes.unknown }

async function accountCommand(command, account) {
  if (command === 'rescan') return emit('qr-login', account.id)
  if (command === 'sync') return emit('sync-courses', account.id)
  if (command === 'rename') {
    try {
      const { value } = await ElMessageBox.prompt('请输入账号备注', '编辑账号', { inputValue: account.name || '', inputPattern: /.+/, inputErrorMessage: '备注不能为空' })
      emit('rename-account', account.id, value)
    } catch {}
  }
  if (command === 'delete') {
    try {
      await ElMessageBox.confirm(`删除账号「${account.name || account.remote_user_name}」及其课程和任务？`, '删除账号', { type: 'warning' })
      emit('delete-account', account.id)
    } catch {}
  }
}

async function uploadPhoto(options) {
  try {
    const uploaded = await props.uploadPhotoAction(options.file, props.selectedAccountId)
    const path = uploaded.path || uploaded.photo_path
    photoFiles.value = [{ uid: `${Date.now()}`, name: options.file.name, path, url: uploaded.url, status: 'success' }]
    form.photo_path = path
    options.onSuccess(uploaded)
    ElMessage.success('照片上传成功')
  } catch (error) {
    options.onError(error)
    ElMessage.error(error.message || '照片上传失败')
  }
}
function removePhoto() { photoFiles.value = []; form.photo_path = '' }

async function submitManual() {
  checkingIn.value = true
  try {
    const payload = {}
    if (['gps', 'gps_photo'].includes(props.selectedItem.mode)) {
      Object.assign(payload, { latitude: form.latitude, longitude: form.longitude, accuracy: form.accuracy })
    }
    if (props.selectedItem.mode === 'gps_photo') payload.photo_path = form.photo_path
    if (props.selectedItem.mode === 'password') payload.password = form.password
    result.value = await props.manualCheckinAction(props.selectedItem.id, payload)
    resultVisible.value = true
  } catch (error) {
    result.value = { status: 'failed', message: error.message || '签到请求失败' }
    resultVisible.value = true
  } finally {
    checkingIn.value = false
  }
}
</script>

<style scoped>
.account-checkin { display: grid; gap: 18px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.stats-grid article { display: flex; align-items: center; gap: 13px; min-height: 92px; padding: 17px; border: 1px solid rgb(191 219 254 / 58%); border-radius: 19px; background: rgb(255 255 255 / 82%); box-shadow: 0 12px 30px rgb(15 23 42 / 6%); backdrop-filter: blur(16px); }
.stat-icon { display: grid; width: 46px; height: 46px; flex: none; place-items: center; border-radius: 15px; font-size: 21px; }
.stat-icon.blue { color: #2563eb; background: #dbeafe; }.stat-icon.cyan { color: #0891b2; background: #cffafe; }.stat-icon.green { color: #059669; background: #d1fae5; }.stat-icon.violet { color: #7c3aed; background: #ede9fe; }
.stats-grid strong, .stats-grid small { display: block; }.stats-grid strong { color: #0f172a; font-size: 25px; line-height: 1; }.stats-grid small { margin-top: 7px; color: #64748b; font-size: 12px; }
.workspace-grid { display: grid; grid-template-columns: minmax(270px, .72fr) minmax(0, 1.5fr); gap: 18px; align-items: start; }
.glass-card { border: 1px solid rgb(191 219 254 / 58%); border-radius: 22px; background: rgb(255 255 255 / 82%); box-shadow: 0 18px 42px rgb(15 23 42 / 7%); backdrop-filter: blur(18px); }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.section-head strong,.section-head small { display: block; }.section-head strong { color: #172033; font-size: 16px; }.section-head small { margin-top: 4px; color: #64748b; font-size: 11px; }
.account-list,.item-list { display: grid; gap: 9px; max-height: 480px; overflow: auto; }
.account-row,.item-row { display: flex; align-items: center; gap: 10px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 15px; background: #f8fafc; cursor: pointer; transition: .2s ease; }
.account-row:hover,.item-row:hover,.account-row.active,.item-row.active { border-color: #93c5fd; background: #eff6ff; transform: translateY(-1px); }
.avatar,.mode-icon { display: grid; width: 39px; height: 39px; flex: none; place-items: center; color: #fff; border-radius: 13px; background: linear-gradient(135deg,#2563eb,#0ea5e9); font-weight: 800; }
.account-main,.item-row>div { min-width: 0; flex: 1; }.account-main strong,.account-main small,.item-row strong,.item-row small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.account-main strong,.item-row strong { color:#1e293b;font-size:13px; }.account-main small,.item-row small { margin-top:4px;color:#64748b;font-size:11px; }
.mode-icon.gps { background:linear-gradient(135deg,#0ea5e9,#06b6d4) }.mode-icon.gps_photo { background:linear-gradient(135deg,#7c3aed,#a855f7) }.mode-icon.password { background:linear-gradient(135deg,#f59e0b,#f97316) }
.selector-row { display:flex;align-items:center;gap:12px;margin-bottom:14px }.selector-row .el-select { flex:1 }.course-code,.option-code { color:#64748b;font-size:11px }.option-code { float:right;margin-left:20px }
.manual-form { margin-top:18px;padding:18px;border:1px solid #bfdbfe;border-radius:18px;background:linear-gradient(145deg,#f8fbff,#eff6ff) }
.manual-form__head { display:flex;justify-content:space-between;gap:12px;margin-bottom:16px }.manual-form__head>div { display:flex;align-items:center;gap:9px }.manual-form__head small { color:#64748b;font-size:11px }.mode-chip { padding:5px 9px;color:#1d4ed8;border-radius:9px;background:#dbeafe;font-size:11px;font-weight:700 }
.location-grid { display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px }.location-grid .el-input-number { width:100% }.field-tip { margin:7px 0 0;color:#64748b;font-size:11px }
.result-content { display:grid;justify-items:center;padding:16px 10px;text-align:center }.result-icon { display:grid;width:70px;height:70px;place-items:center;color:#fff;border-radius:24px;background:linear-gradient(135deg,#2563eb,#0ea5e9);font-size:38px;box-shadow:0 18px 35px rgb(37 99 235 / 24%) }.result-content.is-success .result-icon,.result-content.is-already_signed .result-icon { background:linear-gradient(135deg,#059669,#10b981) }.result-content.is-failed .result-icon { background:linear-gradient(135deg,#dc2626,#f87171) }.result-content small { margin-top:17px;color:#64748b;font-size:10px;font-weight:800;letter-spacing:.14em }.result-content h2 { margin:6px 0;color:#172033 }.result-content p { max-width:390px;margin:0 0 14px;color:#64748b;line-height:1.7 }
@media(max-width:1024px){.workspace-grid{grid-template-columns:1fr}.stats-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:640px){.stats-grid{grid-template-columns:1fr 1fr;gap:8px}.stats-grid article{min-height:76px;padding:12px}.section-head,.manual-form__head,.selector-row{align-items:stretch;flex-direction:column}.location-grid{grid-template-columns:1fr}.section-head .el-button{width:100%}}
</style>
