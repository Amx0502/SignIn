<template>
  <div class="account-checkin">
    <div class="workspace-grid">
      <el-card class="glass-card account-card" shadow="never">
        <template #header>
          <div class="section-head">
            <div><strong>班级魔方账号</strong><small>扫码登录并管理课程凭据</small></div>
            <div class="account-head-actions">
              <el-button
                type="danger"
                plain
                :icon="Delete"
                :disabled="!selectedAccountIds.size || batchDeleting"
                :loading="batchDeleting"
                @click="batchDeleteSelected"
              >
                批量删除<span v-if="selectedAccountIds.size">（{{ selectedAccountIds.size }}）</span>
              </el-button>
              <el-tooltip
                :disabled="canAddAccount"
                :content="`当前账号额度已满（${accountAccess.account_count}/${accountAccess.account_limit}）`"
              >
                <span>
                  <el-button type="primary" :icon="Plus" :disabled="!canAddAccount" @click="emit('qr-login', null)">扫码添加</el-button>
                </span>
              </el-tooltip>
            </div>
          </div>
        </template>
        <div v-if="accounts.length" class="account-search-bar">
          <el-input
            v-model="accountKeyword"
            clearable
            :prefix-icon="Search"
            placeholder="搜索姓名、备注或 UID"
            aria-label="搜索班级魔方账号"
          />
          <span>显示 {{ filteredAccounts.length }}/{{ accounts.length }}</span>
        </div>
        <el-empty v-if="!accounts.length" description="暂无账号，请先扫码登录" :image-size="78" />
        <el-empty v-else-if="!filteredAccounts.length" description="没有找到匹配账号" :image-size="68" />
        <div v-else class="account-list">
          <article
            v-for="account in filteredAccounts"
            :key="account.id"
            class="account-row"
            :class="{ active: account.id === selectedAccountId }"
            @click="emit('select-account', account.id)"
          >
            <el-checkbox
              :model-value="selectedAccountIds.has(account.id)"
              :aria-label="`选择账号 ${account.name || account.remote_user_name || account.id}`"
              @click.stop
              @change="checked => toggleAccountSelection(account.id, checked)"
            />
            <span class="avatar">{{ (account.remote_user_name || account.name || '班').slice(0, 1) }}</span>
            <div class="account-main">
              <strong>{{ account.name || account.remote_user_name || `账号 ${account.id}` }}</strong>
              <small>
                {{ account.remote_user_name || '未获取平台姓名' }}
                <template v-if="account.remote_uid"> · UID {{ account.remote_uid }}</template>
              </small>
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
            <div class="sync-actions">
              <el-button
                type="primary"
                plain
                :icon="Refresh"
                :disabled="!selectedCourseId || coursesLoading || itemsLoading || itemsSyncing"
                :loading="itemsSyncing || itemsLoading"
                @click="emit('sync-items', selectedCourseId)"
              >同步签到项</el-button>
              <el-button
                v-if="isAdmin"
                type="success"
                plain
                :icon="Refresh"
                :loading="classAccountsSyncing"
                :disabled="!selectedCourseId || classAccountsSyncing || coursesLoading || itemsLoading || itemsSyncing"
                @click="syncClassAccounts"
              >同步同班账号</el-button>
              <el-button
                v-if="isAdmin"
                type="warning"
                plain
                :icon="Refresh"
                :loading="allAccountsSyncing"
                :disabled="allAccountsSyncing || itemsSyncing || coursesLoading || itemsLoading"
                @click="syncAllAccounts"
              >同步所有账号</el-button>
            </div>
          </div>
        </template>
        <div class="selector-row">
          <el-select
            :model-value="selectedCourseId"
            placeholder="请选择课程"
            :disabled="!selectedAccountId || coursesLoading"
            :loading="coursesLoading"
            @change="value => emit('select-course', value)"
          >
            <el-option v-for="course in courses" :key="course.id" :value="course.id" :label="course.name">
              <span>{{ course.name }}</span><small class="option-code">{{ course.class_code || course.remote_course_id }}</small>
            </el-option>
          </el-select>
          <span v-if="selectedCourse" class="course-code">班级码 {{ selectedCourse.class_code || '—' }}</span>
        </div>

        <el-skeleton v-if="itemsLoading && !items.length" :rows="3" animated />
        <el-empty v-else-if="!selectedCourseId" description="先选择账号与课程" :image-size="88" />
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

        <div v-if="shouldShowManualCheckinForm(selectedItem)" class="manual-form">
          <div class="manual-form__head">
            <div><span class="mode-chip">{{ modeMeta(selectedItem.mode).label }}</span><strong>{{ selectedItem.title }}</strong></div>
            <small>只提交页面要求的字段，结果由服务端严格判断</small>
          </div>
          <el-form label-position="top">
            <div v-if="['gps', 'gps_photo'].includes(selectedItem.mode)" class="location-grid">
              <el-form-item class="location-search-item" label="签到位置">
                <LocationSearchPanel
                  v-model="form.coordinateInput"
                />
              </el-form-item>
            </div>
            <el-alert v-if="selectedItem.mode === 'gps_photo'" title="照片将在提交签到时上传，实际 res 会记录在运行记录中。" type="info" :closable="false" show-icon />
            <el-form-item v-if="selectedItem.mode === 'gps_photo'" label="签到照片">
              <TaskImageUpload
                :file-list="photoFiles"
                :limit="1"
                :http-request="uploadPhoto"
                :on-remove="removePhoto"
              />
            </el-form-item>
            <el-form-item v-if="selectedItem.mode === 'gps_photo'" label="手动 res（可选）">
              <el-input
                v-model="form.photoRes"
                type="text"
                clearable
                maxlength="2048"
                placeholder='例如 ["p/260803/1118536714c14979bd46fd.png"]'
              />
              <p class="field-tip">填写后优先使用该资源值，不再上传照片；支持 JSON 数组或单个资源路径。</p>
            </el-form-item>
            <el-form-item v-if="selectedItem.mode === 'password'" label="签到密码">
              <el-input v-model="form.password" type="text" maxlength="128" autocomplete="off" placeholder="请输入本次签到密码" />
            </el-form-item>
            <el-form-item v-if="selectedItem.mode === 'qr'" label="二维码签到图片">
              <div class="qr-upload-zone" @paste.prevent="handleQrPaste" @dragover.prevent @drop.prevent="handleQrDrop">
              <input ref="qrFileInput" class="qr-file-input" type="file" accept="image/*" @change="decodeQrFile" />
              <el-button type="primary" plain :loading="qrDecoding" :icon="Upload" @click="qrFileInput?.click()">上传二维码图片并解析</el-button>
              <span>可直接 Ctrl+V 粘贴，或将二维码图片拖到此处</span>
              </div>
              <p class="field-tip">图片仅在浏览器本地解析，不会上传；解析后会自动填入签到地址。</p>
            </el-form-item>
            <el-form-item v-if="selectedItem.mode === 'qr'" label="二维码签到地址">
              <el-input v-model="form.qrUrl" type="text" clearable maxlength="2048" placeholder="粘贴或从图片解析 k8n.cn/student/punchw/course/... 地址" />
              <p class="field-tip">地址必须包含 tm 和 sign 参数，并与当前签到项匹配。</p>
            </el-form-item>
            <el-alert v-if="selectedItem.mode === 'unknown'" title="暂时无法识别签到类型，请重新同步签到项后再试。" type="warning" :closable="false" show-icon />
            <div class="manual-actions">
              <el-checkbox v-model="form.notify_wecom">发送企业微信通知</el-checkbox>
              <div class="manual-action-buttons" :class="{ 'has-batch-action': canBatchCheckin }">
                <el-button type="primary" size="large" :loading="checkingIn" :disabled="selectedItem.mode === 'unknown' || batchCheckingIn" @click="submitManual">
                  <el-icon><Position /></el-icon>执行{{ modeMeta(selectedItem.mode).label }}
                </el-button>
                <el-popover v-if="canBatchCheckin" placement="top-start" trigger="click" :width="300">
                  <template #reference>
                    <el-button type="warning" size="large" :loading="batchCheckingIn" :disabled="checkingIn || !selectedBatchAccountIds.length">
                      <el-icon><User /></el-icon>并发签到（{{ selectedBatchAccountIds.length }}）
                    </el-button>
                  </template>
                  <div class="batch-target-picker">
                    <strong>选择同班账号</strong>
                    <el-checkbox-group v-model="selectedBatchAccountIds">
                      <el-checkbox v-for="target in batchTargets" :key="target.id" :value="target.id">
                        {{ target.name || target.remote_user_name || `账号 ${target.id}` }}
                      </el-checkbox>
                    </el-checkbox-group>
                    <small v-if="!batchTargets.length">当前没有符合条件的账号</small>
                    <el-button type="primary" size="small" :disabled="!selectedBatchAccountIds.length" @click="submitBatchCheckin">确认并发签到</el-button>
                  </div>
                </el-popover>
              </div>
            </div>
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
      <div v-if="batchDetails.length" class="batch-result-list">
        <div v-for="detail in batchDetails" :key="detail.account_id" class="batch-result-row">
          <div>
            <strong>{{ detail.account_name || `账号 ${detail.account_id}` }}</strong>
            <small>{{ detail.message || '无详细信息' }}</small>
          </div>
          <el-tag :type="batchStatusType(detail.status)" size="small">
            {{ detail.status }}
          </el-tag>
        </div>
      </div>
      <template #footer><el-button type="primary" @click="resultVisible = false">完成</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, reactive, ref, watch } from 'vue'
import {
  Aim, Camera, Cellphone, CircleCheckFilled, CircleCloseFilled,
  Delete, Key, Lock, MoreFilled, Plus, Position, Refresh, Search, Upload, User, WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { buildManualCheckinPayload, shouldShowManualCheckinForm } from '../../utils/classCubeCheckin.js'
import { decodeQrImage } from '../../utils/qrImageDecode.js'
import LocationPanelLoading from './LocationPanelLoading.vue'
import TaskImageUpload from '../TaskImageUpload.vue'

const LocationSearchPanel = defineAsyncComponent({
  loader: () => import('./LocationSearchPanel.vue'),
  loadingComponent: LocationPanelLoading,
  delay: 80,
  timeout: 20_000,
})

const props = defineProps({
  accounts: { type: Array, default: () => [] },
  accountAccess: { type: Object, default: () => ({ account_limit: null, account_count: 0 }) },
  canAddAccount: { type: Boolean, default: true },
  courses: { type: Array, default: () => [] },
  items: { type: Array, default: () => [] },
  batchTargets: { type: Array, default: () => [] },
  selectedAccountId: { type: Number, default: null },
  selectedCourseId: { type: Number, default: null },
  selectedItemId: { type: Number, default: null },
  selectedCourse: { type: Object, default: null },
  selectedItem: { type: Object, default: null },
  coursesLoading: { type: Boolean, default: false },
  itemsLoading: { type: Boolean, default: false },
  itemsSyncing: { type: Boolean, default: false },
  isAdmin: { type: Boolean, default: false },
  manualCheckinAction: { type: Function, required: true },
  batchCheckinAction: { type: Function, required: true },
  syncClassItemsAction: { type: Function, required: true },
  syncAllAccountsAction: { type: Function, required: true },
  uploadPhotoAction: { type: Function, required: true },
  batchDeleteAccountsAction: { type: Function, required: true },
})
const emit = defineEmits(['qr-login', 'select-account', 'select-course', 'select-item', 'sync-courses', 'sync-items', 'rename-account', 'delete-account'])
const checkingIn = ref(false)
const batchCheckingIn = ref(false)
const allAccountsSyncing = ref(false)
const classAccountsSyncing = ref(false)
const qrDecoding = ref(false)
const qrFileInput = ref(null)
const photoUploading = ref(false)
const photoFiles = ref([])
const batchDeleting = ref(false)
const selectedAccountIds = ref(new Set())
const accountKeyword = ref('')
const selectedBatchAccountIds = ref([])
const resultVisible = ref(false)
const result = ref(null)
const batchDetails = ref([])
const form = reactive({ coordinateInput: '', accuracy: 20, password: '', photoPath: '', photoRes: '', qrUrl: '', notify_wecom: false })

function resetManualState() {
  Object.assign(form, {
    coordinateInput: '',
    accuracy: 20,
    password: '',
    photoPath: '',
    photoRes: '',
    qrUrl: '',
    notify_wecom: false,
  })
  photoFiles.value = []
  result.value = null
  batchDetails.value = []
  resultVisible.value = false
}

watch(
  () => [
    props.selectedAccountId,
    props.selectedCourseId,
    props.selectedItemId,
    props.selectedItem?.mode,
  ],
  resetManualState,
)

watch(
  () => props.accounts.map(account => account.id),
  accountIds => {
    const available = new Set(accountIds)
    selectedAccountIds.value = new Set(
      [...selectedAccountIds.value].filter(id => available.has(id)),
    )
  },
)

watch(
  () => props.batchTargets,
  targets => { selectedBatchAccountIds.value = targets.map(target => target.id) },
  { immediate: true },
)

const filteredAccounts = computed(() => {
  const keyword = accountKeyword.value.trim().toLowerCase()
  if (!keyword) return props.accounts
  return props.accounts.filter(account => (
    [account.name, account.remote_user_name, account.remote_uid, account.id]
      .some(value => String(value ?? '').toLowerCase().includes(keyword))
  ))
})
const canBatchCheckin = computed(() => (
  props.isAdmin
  && ['qr', 'password', 'gps'].includes(props.selectedItem?.mode)
  && (props.selectedItem?.mode !== 'qr' || Boolean(form.qrUrl))
))
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
  waiting_parameter: { label: '等待补充参数', eyebrow: 'ACTION REQUIRED', tip: '请补充签到需要的位置或密码', icon: WarningFilled, type: 'warning' },
  unknown_result: { label: '结果未知', eyebrow: 'RESULT UNKNOWN', tip: '提交结果无法确认，为避免重复签到不会自动重试', icon: WarningFilled, type: 'warning' },
  failed: { label: '签到失败', eyebrow: 'CHECK-IN FAILED', tip: '远程平台未确认签到成功', icon: CircleCloseFilled, type: 'danger' },
  skipped: { label: '已跳过', eyebrow: 'CHECK-IN SKIPPED', tip: '本次签到未发起提交', icon: Lock, type: 'info' },
}
const resultMeta = computed(() => results[result.value?.status] || results.failed)
function modeMeta(mode) { return modes[mode] || modes.unknown }
function batchStatusType(status) {
  if (['success', 'already_signed'].includes(status)) return 'success'
  if (status === 'unknown_result') return 'warning'
  return 'danger'
}

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

function toggleAccountSelection(accountId, selected) {
  const next = new Set(selectedAccountIds.value)
  if (selected) next.add(accountId)
  else next.delete(accountId)
  selectedAccountIds.value = next
}

async function batchDeleteSelected() {
  const ids = [...selectedAccountIds.value]
  if (!ids.length || batchDeleting.value) return
  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${ids.length} 个账号吗？关联课程、签到项和任务将一并删除。`,
      '批量删除账号',
      { type: 'warning' },
    )
  } catch {
    return
  }

  batchDeleting.value = true
  try {
    const deleted = await props.batchDeleteAccountsAction(ids)
    if (deleted) selectedAccountIds.value = new Set()
  } finally {
    batchDeleting.value = false
  }
}

async function submitManual() {
  if (batchCheckingIn.value) return
  batchDetails.value = []
  checkingIn.value = true
  try {
    const payload = buildManualCheckinPayload({
      mode: props.selectedItem.mode,
      coordinateInput: form.coordinateInput,
      accuracy: form.accuracy,
      password: form.password,
      photoPath: form.photoPath,
      photoRes: form.photoRes,
      qrUrl: form.qrUrl,
      notifyWecom: form.notify_wecom,
    })
    result.value = await props.manualCheckinAction(props.selectedItem.id, payload)
    resultVisible.value = true
  } catch (error) {
    result.value = { status: 'failed', message: error.message || '签到请求失败' }
    resultVisible.value = true
  } finally {
    checkingIn.value = false
  }
}

async function submitBatchCheckin() {
  if (!canBatchCheckin.value || checkingIn.value || !selectedBatchAccountIds.value.length) return
  let payload
  try {
    payload = buildManualCheckinPayload({
      mode: props.selectedItem.mode,
      coordinateInput: form.coordinateInput,
      accuracy: form.accuracy,
      password: form.password,
      qrUrl: form.qrUrl,
      notifyWecom: form.notify_wecom,
    })
  } catch (error) {
    ElMessage.error(error.message || '签到参数无效')
    return
  }
  try {
    await ElMessageBox.confirm(
      `系统将为选中的 ${selectedBatchAccountIds.value.length} 个同班账号执行${modeMeta(props.selectedItem.mode).label}，是否继续？`,
      '确认并发签到',
      { type: 'warning' },
    )
  } catch {
    return
  }
  batchCheckingIn.value = true
  try {
    const summary = await props.batchCheckinAction(
      props.selectedItem.id,
      payload,
      selectedBatchAccountIds.value,
    )
    result.value = {
      status: summary.failed || summary.unknown ? 'failed' : 'success',
      message: `并发签到完成：共 ${summary.total} 个账号，成功 ${summary.success} 个，已签到 ${summary.already_signed} 个，失败 ${summary.failed} 个，未知 ${summary.unknown} 个`,
    }
    batchDetails.value = Array.isArray(summary.details) ? summary.details : []
    resultVisible.value = true
  } catch (error) {
    batchDetails.value = []
    result.value = { status: 'failed', message: error.message || '并发签到请求失败' }
    resultVisible.value = true
  } finally {
    batchCheckingIn.value = false
  }
}

async function syncClassAccounts() {
  if (!props.isAdmin || !props.selectedCourseId || classAccountsSyncing.value) return
  classAccountsSyncing.value = true
  try {
    const summary = await props.syncClassItemsAction(props.selectedCourseId)
    ElMessage.success(`同班账号同步完成：成功 ${summary.success} 个，失败 ${summary.failed} 个`)
  } catch (error) {
    ElMessage.error(error.message || '同步同班账号失败')
  } finally {
    classAccountsSyncing.value = false
  }
}

async function syncAllAccounts() {
  try {
    await ElMessageBox.confirm(
      '系统将同步所有有效账号的课程和签到项，是否继续？',
      '确认同步所有账号',
      { type: 'warning' },
    )
  } catch {
    return
  }
  allAccountsSyncing.value = true
  try {
    await props.syncAllAccountsAction()
  } catch (error) {
    ElMessage.error(error.message || '同步所有账号失败')
  } finally {
    allAccountsSyncing.value = false
  }
}

async function decodeQrFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  await decodeQrImageFile(file)
}

async function decodeQrImageFile(file) {
  qrDecoding.value = true
  try {
    form.qrUrl = await decodeQrImage(file)
    ElMessage.success('二维码解析成功')
  } catch (error) {
    ElMessage.error(error.message || '二维码解析失败')
  } finally {
    qrDecoding.value = false
  }
}

function handleQrPaste(event) {
  const file = Array.from(event.clipboardData?.items || [])
    .find(item => item.kind === 'file' && item.type.startsWith('image/'))
    ?.getAsFile()
  if (file) decodeQrImageFile(file)
}

function handleQrDrop(event) {
  const file = Array.from(event.dataTransfer?.files || [])
    .find(item => item.type?.startsWith('image/'))
  if (file) decodeQrImageFile(file)
}

async function uploadPhoto(options) {
  const file = options?.file
  if (!file || !props.selectedAccountId) return
  photoUploading.value = true
  try {
    const response = await props.uploadPhotoAction(file, props.selectedAccountId)
    form.photoPath = response?.path || ''
    if (!form.photoPath) throw new Error('照片上传结果无效')
    photoFiles.value = [{
      uid: `${Date.now()}`,
      name: file.name,
      path: form.photoPath,
      status: 'success',
    }]
    options?.onSuccess?.(response)
    ElMessage.success('签到照片上传成功')
  } catch (error) {
    options?.onError?.(error)
    ElMessage.error(error.message || '照片上传失败')
  } finally {
    photoUploading.value = false
  }
}

function removePhoto() {
  form.photoPath = ''
  photoFiles.value = []
}
</script>

<style scoped>
.batch-result-list { display: grid; gap: 8px; max-height: 260px; margin-top: 16px; overflow: auto; }
.batch-result-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc; }
.batch-result-row div { min-width: 0; }.batch-result-row strong,.batch-result-row small { display: block; }.batch-result-row strong { color: #172033; }.batch-result-row small { margin-top: 3px; overflow: hidden; color: #64748b; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.batch-target-picker { display:grid; gap:10px; }.batch-target-picker strong { color:#172033; }.batch-target-picker .el-checkbox-group { display:grid; max-height:220px; overflow:auto; gap:4px; }.batch-target-picker small { color:#64748b; }.qr-file-input { position: absolute; width: 1px; height: 1px; overflow: hidden; opacity: 0; pointer-events: none; }
.qr-upload-zone { display: inline-flex; align-items: center; gap: 10px; padding: 10px; border: 1px dashed #93c5fd; border-radius: 12px; background: #f8fbff; }
.qr-upload-zone span { color: #64748b; font-size: 12px; }
.account-checkin { display: grid; gap: 18px; }
.workspace-grid { display: grid; grid-template-columns: minmax(330px, .85fr) minmax(0, 1.5fr); gap: 18px; align-items: start; }
.glass-card { border: 1px solid rgb(191 219 254 / 58%); border-radius: 22px; background: rgb(255 255 255 / 82%); box-shadow: 0 18px 42px rgb(15 23 42 / 7%); backdrop-filter: blur(18px); }
.checkin-card { container-type:inline-size }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.section-head strong,.section-head small { display: block; }.section-head strong { color: #172033; font-size: 16px; }.section-head small { margin-top: 4px; color: #64748b; font-size: 11px; }
.checkin-card .section-head > div:first-child { min-width: 9em; flex: none; }
.account-head-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.account-search-bar { display:flex;align-items:center;gap:10px;margin-bottom:12px }.account-search-bar .el-input { min-width:0;flex:1 }.account-search-bar span { flex:none;color:#64748b;font-size:11px;white-space:nowrap }
.sync-actions { display: grid; grid-template-columns: repeat(3, max-content); align-items: center; justify-content: end; gap: 8px; }
.sync-actions .el-button { min-width: 0; margin-left: 0; white-space: nowrap; }
.account-list,.item-list { display: grid; gap: 9px; overflow-y: auto; overflow-x: hidden; }
.account-list {
  max-height: 480px;
  padding-right: 4px;
  overscroll-behavior: contain;
  scrollbar-color: #60a5fa #eff6ff;
  scrollbar-gutter: stable;
  scrollbar-width: auto;
  -webkit-overflow-scrolling: touch;
}
.account-list::-webkit-scrollbar { width: 10px; }
.account-list::-webkit-scrollbar-track { border-radius: 999px; background: #eff6ff; }
.account-list::-webkit-scrollbar-thumb { border: 2px solid #eff6ff; border-radius: 999px; background: #60a5fa; }
.account-list::-webkit-scrollbar-thumb:hover { background: #3b82f6; }
.item-list {
  max-height: 150px;
  padding-right: 4px;
  overscroll-behavior: contain;
  scrollbar-color: #93c5fd #eff6ff;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  -webkit-overflow-scrolling: touch;
}
.item-list::-webkit-scrollbar { width: 7px; }
.item-list::-webkit-scrollbar-track { border-radius: 999px; background: #eff6ff; }
.item-list::-webkit-scrollbar-thumb { border: 2px solid #eff6ff; border-radius: 999px; background: #93c5fd; }
.item-list::-webkit-scrollbar-thumb:hover { background: #60a5fa; }
.account-row,.item-row { align-items: center; padding: 12px; margin-top: 5px; border: 1px solid #e2e8f0; border-radius: 15px; background: #f8fafc; cursor: pointer; transition: .2s ease; }
.account-row { display: grid; grid-template-columns: auto 39px minmax(0, 1fr) auto auto; gap: 8px; }
.item-row { display: flex; gap: 10px; }
.account-row > .el-checkbox,.account-row > .el-tag,.account-row > .el-dropdown { min-width: 0; flex: none; }
.account-row > .el-tag { justify-self: end; }
.account-row:hover,.item-row:hover,.account-row.active,.item-row.active { border-color: #93c5fd; background: #eff6ff; transform: translateY(-1px); }
.avatar,.mode-icon { display: grid; width: 39px; height: 39px; flex: none; place-items: center; color: #fff; border-radius: 13px; background: linear-gradient(135deg,#2563eb,#0ea5e9); font-weight: 800; }
.account-main,.item-row>div { min-width: 0; flex: 1; }.account-main strong,.account-main small,.item-row strong,.item-row small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.account-main strong,.item-row strong { color:#1e293b;font-size:13px; }.account-main small,.item-row small { margin-top:4px;color:#64748b;font-size:11px; }
.mode-icon.gps { background:linear-gradient(135deg,#0ea5e9,#06b6d4) }.mode-icon.gps_photo { background:linear-gradient(135deg,#7c3aed,#a855f7) }.mode-icon.password { background:linear-gradient(135deg,#f59e0b,#f97316) }
.selector-row { display:flex;align-items:center;gap:12px;margin-bottom:14px }.selector-row .el-select { flex:1 }.course-code,.option-code { color:#64748b;font-size:11px }.option-code { float:right;margin-left:20px }
.manual-form { margin-top:18px;padding:18px;border:1px solid #bfdbfe;border-radius:18px;background:linear-gradient(145deg,#f8fbff,#eff6ff) }
.manual-form__head { display:flex;justify-content:space-between;gap:12px;margin-bottom:16px }.manual-form__head>div { display:flex;align-items:center;gap:9px }.manual-form__head small { color:#64748b;font-size:11px }.mode-chip { padding:5px 9px;color:#1d4ed8;border-radius:9px;background:#dbeafe;font-size:11px;font-weight:700 }
.location-grid { display:grid;grid-template-columns:minmax(0,2fr) minmax(180px,1fr);gap:12px }.location-grid .el-input-number,.location-grid .el-input { width:100% }.location-search-item{grid-column:1/-1}.field-tip { margin:7px 0 0;color:#64748b;font-size:11px }
.manual-actions { display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:4px }
.manual-action-buttons{display:flex;align-items:center;justify-content:flex-end;gap:10px;min-width:0}.manual-action-buttons .el-button{margin-left:0}
.result-content { display:grid;justify-items:center;padding:16px 10px;text-align:center }.result-icon { display:grid;width:70px;height:70px;place-items:center;color:#fff;border-radius:24px;background:linear-gradient(135deg,#2563eb,#0ea5e9);font-size:38px;box-shadow:0 18px 35px rgb(37 99 235 / 24%) }.result-content.is-success .result-icon,.result-content.is-already_signed .result-icon { background:linear-gradient(135deg,#059669,#10b981) }.result-content.is-failed .result-icon { background:linear-gradient(135deg,#dc2626,#f87171) }.result-content small { margin-top:17px;color:#64748b;font-size:10px;font-weight:800;letter-spacing:.14em }.result-content h2 { margin:6px 0;color:#172033 }.result-content p { max-width:390px;margin:0 0 14px;color:#64748b;line-height:1.7 }
@container(max-width:720px){
  .checkin-card .section-head{align-items:stretch;flex-direction:column}
  .sync-actions{grid-template-columns:repeat(3,minmax(0,1fr));width:100%}
  .sync-actions .el-button{width:100%;padding-inline:10px}
}
@container(max-width:480px){
  .sync-actions{gap:6px}
  .sync-actions .el-button{padding-inline:6px;font-size:12px}
  .manual-form{margin-top:14px;padding:12px}
  .manual-form__head,.manual-actions{align-items:stretch;flex-direction:column}
  .manual-form__head>div{align-items:center;flex-flow:row wrap}
  .manual-form__head>div,.location-grid .el-form-item{min-width:0}
  .manual-form__head strong,.manual-form__head small,.field-tip{overflow-wrap:anywhere}
  .mode-chip{align-self:flex-start}
  .location-grid{grid-template-columns:minmax(0,1fr)}
  .manual-action-buttons{display:grid;grid-template-columns:minmax(0,1fr);width:100%}
  .manual-action-buttons.has-batch-action{grid-template-columns:repeat(2,minmax(0,1fr))}
  .manual-action-buttons .el-button{width:100%;max-width:100%;margin-left:0;padding-inline:8px}
  .manual-actions :deep(.el-checkbox){min-width:0;height:auto;white-space:normal}
}
@media(max-width:1024px){.workspace-grid{grid-template-columns:1fr}}@media(max-width:640px){.section-head,.selector-row,.manual-actions{align-items:stretch;flex-direction:column}.account-head-actions{display:grid;grid-template-columns:1fr}.account-search-bar{align-items:stretch;flex-direction:column}.account-search-bar span{align-self:flex-end}.location-grid{grid-template-columns:1fr}.section-head .el-button{width:100%}.manual-form{border-radius:14px;background:#f8fbff}.manual-form__head{display:grid;gap:6px;margin-bottom:12px}.manual-form__head>div{display:flex;align-items:center;flex-flow:row wrap}.manual-form__head small{line-height:1.45}.location-search-item{margin-bottom:14px}.location-search-item :deep(.el-form-item__label){height:auto;padding-bottom:7px;color:#334155;font-weight:600}.manual-actions{gap:10px}.manual-action-buttons{display:grid;grid-template-columns:minmax(0,1fr);width:100%}.manual-action-buttons.has-batch-action{grid-template-columns:repeat(2,minmax(0,1fr))}.manual-action-buttons .el-button{width:100%;max-width:100%;margin-left:0;padding-inline:8px}}
@media(max-width:360px){.manual-action-buttons.has-batch-action{grid-template-columns:minmax(0,1fr)}}
</style>
