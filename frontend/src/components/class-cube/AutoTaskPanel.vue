<template>
  <el-card class="task-panel" shadow="never">
    <template #header>
      <div class="panel-head">
        <div class="panel-title">
          <strong>自动签到任务</strong>
          <small>到达设定时间后，系统会自动查找课程中的签到并执行</small>
        </div>
        <div class="panel-actions">
          <el-input v-model="keyword" clearable placeholder="搜索任务、账号或课程" :prefix-icon="Search" />
          <el-select v-model="statusFilter" aria-label="筛选任务状态">
            <el-option label="全部状态" value="all" />
            <el-option label="仅看已启用" value="enabled" />
            <el-option label="仅看已停用" value="disabled" />
          </el-select>
          <el-button
            type="danger"
            plain
            :icon="Delete"
            :disabled="!selectedTaskIds.size"
            @click="removeSelected"
          >批量删除({{ selectedTaskIds.size }})</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">新增任务</el-button>
        </div>
      </div>
    </template>

    <div class="task-summary" aria-label="任务概况">
      <span>共 <strong>{{ tasks.length }}</strong> 个任务</span>
      <i aria-hidden="true"></i>
      <span><b class="status-dot status-dot--enabled"></b>已启用 {{ enabledCount }}</span>
      <span><b class="status-dot status-dot--disabled"></b>已停用 {{ tasks.length - enabledCount }}</span>
    </div>

    <div v-if="filteredTasks.length" class="task-grid">
      <article
        v-for="row in filteredTasks"
        :key="row.id"
        class="task-card"
        :class="{ 'task-card--selected': isSelected(row.id), 'task-card--disabled': !row.enabled }"
      >
        <header class="task-card__header">
          <el-checkbox
            :model-value="isSelected(row.id)"
            :aria-label="`选择任务 ${row.name}`"
            @change="value => toggleSelection(row.id, value)"
          />
          <div class="task-card__title">
            <strong :title="row.name">{{ row.name }}</strong>
          </div>
          <div class="task-card__state">
            <span>{{ row.enabled ? '已启用' : '已停用' }}</span>
            <el-switch :model-value="row.enabled" :aria-label="`${row.name}启用状态`" @change="value => toggleTask(row, value)" />
          </div>
        </header>

        <div class="task-card__body">
          <section class="task-detail task-detail--identity">
            <span class="task-detail__label">执行账号与课程</span>
            <strong>{{ accountName(row.account_id) }}</strong>
            <small :title="courseName(row.course_id)">{{ courseName(row.course_id) }}</small>
          </section>
          <section class="task-detail">
            <span class="task-detail__label">每日执行时间</span>
            <div class="time-tags">
              <el-tag v-for="time in row.schedule_times || []" :key="time" size="small" effect="plain">{{ time }}</el-tag>
              <span v-if="!(row.schedule_times || []).length" class="muted">未设置时间</span>
            </div>
            <small class="task-plan-summary">{{ schedulePlanSummary(row) }}</small>
          </section>
          <section class="task-detail">
            <span class="task-detail__label">签到预设</span>
            <div class="preset-tags">
              <el-tag v-if="row.latitude != null && row.longitude != null" size="small" type="primary">位置</el-tag>
              <el-tag v-if="row.has_password" size="small" type="warning">密码</el-tag>
              <el-tag v-if="row.photo_path || row.photo_res" size="small" type="success">照片</el-tag>
              <span v-if="!hasPreset(row)" class="muted">无需预设参数</span>
            </div>
          </section>
          <section class="task-detail">
            <span class="task-detail__label">最近扫描</span>
            <strong class="scan-time">{{ formatTime(row.last_scan_at) }}</strong>
          </section>
        </div>

        <footer class="task-card__footer">
          <div class="task-card__actions">
            <el-button @click="openEdit(row)">编辑</el-button>
            <el-button
              type="primary"
              plain
              :loading="runningTaskId === row.id"
              :disabled="runningTaskId !== null && runningTaskId !== row.id"
              @click="runNow(row)"
            >立即执行</el-button>
            <el-dropdown trigger="click" @command="command => handleTaskCommand(command, row)">
              <el-button :icon="MoreFilled" aria-label="更多任务操作" />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="delete" class="danger-menu-item">删除任务</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </footer>
      </article>
    </div>

    <div v-else class="task-empty">
      <el-empty :description="tasks.length ? '没有符合筛选条件的任务' : '暂无自动任务'" :image-size="88">
        <el-button v-if="tasks.length" @click="resetFilters">清除筛选</el-button>
      </el-empty>
    </div>

    <el-dialog v-model="editorVisible" :title="editingId ? '编辑自动任务' : '新增自动任务'" width="min(1180px, 96vw)" class="task-editor-dialog" align-center append-to-body :close-on-click-modal="false" :before-close="beforeEditorClose">
      <el-form label-position="top" class="task-editor-form">
        <div class="editor-layout">
          <section class="editor-section">
            <header><span class="section-index">01</span><div><strong>基本信息</strong><small>选择账号及课程</small></div></header>
            <el-form-item label="任务名称"><el-input v-model="draft.name" maxlength="255" placeholder="例如：高等数学签到" /></el-form-item>
            <el-form-item v-if="isAdmin" label="所属用户 ID"><el-input-number v-model="draft.owner_user_id" :min="1" :controls="false" :disabled="true" /></el-form-item>
            <el-form-item label="班级魔方账号">
              <el-select v-model="draft.account_id" placeholder="请选择账号" @change="accountChanged">
                <el-option v-for="account in accounts" :key="account.id" :value="account.id" :label="account.name || account.remote_user_name" />
              </el-select>
            </el-form-item>
            <el-form-item label="指定课程">
              <el-select v-model="draft.course_id" placeholder="请选择课程" :disabled="!draft.account_id || coursesLoading" :loading="coursesLoading">
                <el-option v-for="course in courses" :key="course.id" :value="course.id" :label="course.name" />
              </el-select>
            </el-form-item>
          </section>

          <section class="editor-section">
            <header><span class="section-index">02</span><div><strong>签到参数</strong><small>配置不同签到方式的预设值</small></div></header>
            <el-form-item label="签到位置">
              <LocationSearchPanel
                :key="locationPanelKey"
                v-model="draft.coordinateInput"
              />
            </el-form-item>
            <el-form-item label="预设密码">
              <el-input v-model="draft.password" type="text" autocomplete="new-password" placeholder="密码签到使用" />
            </el-form-item>
            <el-form-item label="GPS+拍照签到照片">
              <TaskImageUpload
                :file-list="photoFiles"
                :limit="1"
                :http-request="uploadPhoto"
                :on-remove="removePhoto"
              />
            </el-form-item>
            <el-form-item label="手动 res（可选）">
              <el-input
                v-model="draft.photo_res"
                type="text"
                clearable
                maxlength="2048"
                placeholder='例如 ["p/260803/1118536714c14979bd46fd.png"]'
              />
              <small class="field-tip">填写后自动任务优先使用该资源值；留空时才上传上面的签到照片。</small>
            </el-form-item>
          </section>

          <section class="editor-section">
            <header><span class="section-index">03</span><div><strong>执行策略</strong><small>设置时间范围与通知</small></div></header>
            <el-form-item label="每日执行时间">
              <div class="schedule-list">
                <div v-for="(_, index) in draft.schedule_times" :key="index" class="schedule-row">
                  <el-time-picker v-model="draft.schedule_times[index]" value-format="HH:mm:ss" format="HH:mm:ss" placeholder="执行时间" />
                  <el-button type="danger" plain :disabled="draft.schedule_times.length === 1" @click="draft.schedule_times.splice(index, 1)">删除</el-button>
                </div>
                <el-button plain @click="draft.schedule_times.push('08:00:00')">添加执行时间</el-button>
              </div>
            </el-form-item>
            <el-form-item label="执行日期计划">
              <div class="date-plan-card">
                <div class="date-plan-card__content">
                  <div class="date-plan-card__tags">
                    <el-tag size="small" type="primary">{{ draft.date_mode === 'specific' ? '指定日期' : '每天执行' }}</el-tag>
                    <el-tag v-if="draft.skip_weekends" size="small" type="info">周末跳过</el-tag>
                    <el-tag v-if="draft.auto_disable_after_finish && draft.date_mode === 'specific'" size="small" type="success">结束后关闭</el-tag>
                  </div>
                  <strong>{{ schedulePlanSummary(draft) }}</strong>
                  <small>{{ scheduleRangeSummary(draft) }}</small>
                </div>
                <el-button type="primary" plain @click="openScheduleDrawer">设置签到日期</el-button>
              </div>
            </el-form-item>
            <div class="switch-options">
              <el-checkbox v-model="draft.notify_wecom">发送企业微信通知</el-checkbox>
              <el-checkbox v-model="draft.enabled">保存后立即启用</el-checkbox>
            </div>
          </section>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="requestEditorClose">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存任务</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="scheduleDrawerVisible"
      title="设置签到日期计划"
      size="min(760px, 100vw)"
      append-to-body
      class="schedule-drawer"
      :close-on-click-modal="false"
    >
      <div class="schedule-drawer__body">
        <div class="schedule-drawer__intro">
          <strong>控制具体哪天执行或跳过</strong>
          <small>日期范围是可选的有效边界；周末跳过不会删除已经选择的周末日期，关闭后会自动恢复。</small>
        </div>
        <el-form label-position="top">
          <el-form-item label="有效日期范围（可选）">
            <div class="date-range date-range--drawer">
              <el-date-picker v-model="scheduleDraft.start_date" value-format="YYYY-MM-DD" type="date" placeholder="开始日期" />
              <el-date-picker v-model="scheduleDraft.end_date" value-format="YYYY-MM-DD" type="date" placeholder="结束日期" />
            </div>
          </el-form-item>
        </el-form>
        <TaskDateSchedule
          :date-mode="scheduleDraft.date_mode"
          :run-dates="scheduleDraft.run_dates"
          :skip-dates="scheduleDraft.skip_dates"
          :skip-weekends="scheduleDraft.skip_weekends"
          :times="draft.schedule_times"
          :auto-disable-after-finish="scheduleDraft.auto_disable_after_finish"
          :min-date="scheduleDraft.start_date || ''"
          :max-date="scheduleDraft.end_date || ''"
          @update:date-mode="scheduleDraft.date_mode = $event"
          @update:run-dates="scheduleDraft.run_dates = $event"
          @update:skip-dates="scheduleDraft.skip_dates = $event"
          @update:skip-weekends="scheduleDraft.skip_weekends = $event"
          @update:auto-disable-after-finish="scheduleDraft.auto_disable_after_finish = $event"
        />
      </div>
      <template #footer>
        <el-button @click="scheduleDrawerVisible = false">取消</el-button>
        <el-button type="primary" @click="applyScheduleDraft">应用日期计划</el-button>
      </template>
    </el-drawer>
  </el-card>
</template>

<script setup>
import { computed, defineAsyncComponent, reactive, ref } from 'vue'
import { Delete, MoreFilled, Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { coordinateText, normalizeScheduleTimes, parseCoordinates } from '../../utils/classCubeTaskForm.js'
import LocationPanelLoading from './LocationPanelLoading.vue'
import TaskImageUpload from '../TaskImageUpload.vue'
import TaskDateSchedule from '../TaskDateSchedule.vue'
import { useUnsavedChangesGuard } from '../../composables/useUnsavedChangesGuard.js'

const LocationSearchPanel = defineAsyncComponent({
  loader: () => import('./LocationSearchPanel.vue'),
  loadingComponent: LocationPanelLoading,
  delay: 80,
  timeout: 20_000,
})

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  accounts: { type: Array, default: () => [] },
  courses: { type: Array, default: () => [] },
  selectedTaskIds: { type: Set, default: () => new Set() },
  isAdmin: { type: Boolean, default: false },
  coursesLoading: { type: Boolean, default: false },
  saveTaskAction: { type: Function, required: true },
  uploadPhotoAction: { type: Function, required: true },
  removeTasksAction: { type: Function, required: true },
  runTaskAction: { type: Function, required: true },
})
const emit = defineEmits(['update:selected-task-ids', 'select-account', 'refresh'])
const editorVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const photoUploading = ref(false)
const photoFiles = ref([])
const runningTaskId = ref(null)
const locationPanelKey = ref(0)
const scheduleDrawerVisible = ref(false)
const keyword = ref('')
const statusFilter = ref('all')
const emptyDatePlan = () => ({ start_date: null, end_date: null, date_mode: 'daily', run_dates: [], skip_dates: [], skip_weekends: false, auto_disable_after_finish: false })
const emptyDraft = () => ({ owner_user_id: null, account_id: null, course_id: null, name: '', enabled: true, coordinateInput: '', latitude: null, longitude: null, accuracy: 20, photo_path: '', photo_res: '', password: '', has_password: false, schedule_times: ['08:00:00'], ...emptyDatePlan(), notify_wecom: true })
const draft = reactive(emptyDraft())
const scheduleDraft = reactive(emptyDatePlan())
const {markClean:markEditorClean,beforeClose:beforeEditorClose,requestClose:requestEditorClose}=useUnsavedChangesGuard({
  visible:editorVisible,
  snapshot:()=>draft,
})
const enabledCount = computed(() => props.tasks.filter(row => row.enabled).length)
const filteredTasks = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  return props.tasks.filter(row => {
    if (statusFilter.value === 'enabled' && !row.enabled) return false
    if (statusFilter.value === 'disabled' && row.enabled) return false
    if (!search) return true
    return `${row.name} ${accountName(row.account_id)} ${courseName(row.course_id)}`.toLowerCase().includes(search)
  })
})

function accountName(id) { const row = props.accounts.find(item => item.id === id); return row?.name || row?.remote_user_name || `账号 ${id}` }
function courseName(id) { return props.courses.find(item => item.id === id)?.name || `课程 ${id}` }
function formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚未扫描' }
function dateInRange(value, plan) { return (!plan.start_date || value >= plan.start_date) && (!plan.end_date || value <= plan.end_date) }
function effectiveSpecificDates(plan) {
  const skipped = new Set(plan.skip_dates || [])
  return [...new Set(plan.run_dates || [])].filter(value => {
    if (!dateInRange(value, plan) || skipped.has(value)) return false
    if (!plan.skip_weekends) return true
    const weekday = new Date(`${value}T00:00:00`).getDay()
    return weekday !== 0 && weekday !== 6
  }).sort()
}
function schedulePlanSummary(plan) {
  const excluded = (plan.skip_dates || []).length
  if ((plan.date_mode || 'daily') === 'daily') {
    return ['每天执行', plan.skip_weekends ? '周末跳过' : '', excluded ? `排除 ${excluded} 天` : ''].filter(Boolean).join(' · ')
  }
  const selected = (plan.run_dates || []).length
  const effective = effectiveSpecificDates(plan).length
  return [`指定 ${selected} 天`, `实际 ${effective} 天`, plan.auto_disable_after_finish ? '结束后关闭' : ''].filter(Boolean).join(' · ')
}
function scheduleRangeSummary(plan) {
  if (!plan.start_date && !plan.end_date) return '不限制开始和结束日期'
  return `${plan.start_date || '不限'} 至 ${plan.end_date || '不限'}`
}
function hasPreset(row) { return row.latitude != null || row.longitude != null || row.has_password || row.photo_path || row.photo_res }
function isSelected(id) { return props.selectedTaskIds.has(id) }
function toggleSelection(id, selected) {
  const next = new Set(props.selectedTaskIds)
  if (selected) next.add(id)
  else next.delete(id)
  emit('update:selected-task-ids', next)
}
function clearSelection() { emit('update:selected-task-ids', new Set()) }
function resetFilters() { keyword.value = ''; statusFilter.value = 'all' }
function handleTaskCommand(command, row) {
  if (command === 'delete') removeOne(row)
}
function resetDraft(values = {}) {
  Object.assign(draft, emptyDraft(), values, {
    coordinateInput: coordinateText(values),
    schedule_times: values.schedule_times?.length ? [...values.schedule_times] : ['08:00:00'],
    notify_wecom: values.notify_wecom !== false,
  })
  photoFiles.value = draft.photo_path ? [{
    uid: `saved-${draft.photo_path}`,
    name: String(draft.photo_path).split(/[\\/]/).pop() || '签到照片',
    path: draft.photo_path,
    status: 'success',
  }] : []
}
function openCreate() { editingId.value = null; resetDraft(); locationPanelKey.value += 1; markEditorClean(); editorVisible.value = true }
function openEdit(row) { editingId.value = row.id; resetDraft(row); locationPanelKey.value += 1; emit('select-account', row.account_id); markEditorClean(); editorVisible.value = true }
function accountChanged(id) {
  const account = props.accounts.find(item => item.id === id)
  draft.owner_user_id = account?.owner_user_id ?? null
  draft.course_id = null
  emit('select-account', id)
}

function openScheduleDrawer() {
  Object.assign(scheduleDraft, {
    start_date: draft.start_date || null,
    end_date: draft.end_date || null,
    date_mode: draft.date_mode || 'daily',
    run_dates: [...(draft.run_dates || [])],
    skip_dates: [...(draft.skip_dates || [])],
    skip_weekends: draft.skip_weekends === true,
    auto_disable_after_finish: draft.auto_disable_after_finish === true,
  })
  scheduleDrawerVisible.value = true
}

function validateDatePlan(plan) {
  if (plan.start_date && plan.end_date && plan.start_date > plan.end_date) throw new Error('开始日期不能晚于结束日期')
  if (plan.date_mode === 'specific' && !(plan.run_dates || []).length) throw new Error('指定日期模式下请至少选择一个执行日期')
  if (plan.date_mode === 'specific' && !effectiveSpecificDates(plan).length) throw new Error('指定日期计划至少需要保留一个实际执行日期')
}

function applyScheduleDraft() {
  try { validateDatePlan(scheduleDraft) } catch (error) { return ElMessage.warning(error.message) }
  Object.assign(draft, {
    ...scheduleDraft,
    run_dates: [...scheduleDraft.run_dates],
    skip_dates: [...scheduleDraft.skip_dates],
  })
  scheduleDrawerVisible.value = false
}

async function save() {
  if (!draft.name.trim() || !draft.account_id || !draft.course_id) return ElMessage.warning('请填写任务名称并选择账号和课程')
  try {
    if (draft.coordinateInput.trim()) Object.assign(draft, parseCoordinates(draft.coordinateInput))
    else { draft.latitude = null; draft.longitude = null }
    draft.schedule_times = normalizeScheduleTimes(draft.schedule_times)
    if (!draft.schedule_times.length) throw new Error('请至少添加一个执行时间')
    validateDatePlan(draft)
  } catch (error) { return ElMessage.warning(error.message) }
  saving.value = true
  try {
    await props.saveTaskAction({ ...draft, name: draft.name.trim() }, editingId.value)
    markEditorClean()
    editorVisible.value = false
    ElMessage.success(editingId.value ? '任务已更新' : '任务已创建')
    emit('refresh')
  } catch (error) { ElMessage.error(error.message || '保存失败') } finally { saving.value = false }
}
async function uploadPhoto(options) {
  const file = options?.file
  if (!file) return
  if (!draft.account_id) {
    ElMessage.warning('请先选择班级魔方账号')
    return
  }
  photoUploading.value = true
  try {
    const response = await props.uploadPhotoAction(file, draft.account_id)
    draft.photo_path = response?.path || ''
    if (!draft.photo_path) throw new Error('照片上传结果无效')
    photoFiles.value = [{ uid: `${Date.now()}`, name: file.name, path: draft.photo_path, status: 'success' }]
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
  draft.photo_path = ''
  photoFiles.value = []
}
async function toggleTask(row, enabled) {
  try { await props.saveTaskAction({ enabled }, row.id); ElMessage.success(enabled ? '任务已启用' : '任务已停用'); emit('refresh') } catch (error) { ElMessage.error(error.message || '更新失败') }
}
async function runNow(row) {
  if (runningTaskId.value !== null) return
  runningTaskId.value = row.id
  try {
    const data = await props.runTaskAction(row.id)
    const message = data.message || '任务执行完成'
    if (['failed', 'unknown_result'].includes(data.status)) ElMessage.error(message)
    else if (data.status === 'running') ElMessage.warning(message)
    else if (data.status === 'waiting_parameter') ElMessage.warning(message)
    else if (['no_sign_in', 'skipped', 'already_signed'].includes(data.status)) ElMessage.info(message)
    else ElMessage.success(message)
    emit('refresh')
  } catch (error) {
    ElMessage.error(error.message || '执行失败')
  } finally {
    runningTaskId.value = null
  }
}
async function removeOne(row) {
  try { await ElMessageBox.confirm(`确认删除任务「${row.name}」？`, '删除任务', { type: 'warning' }); await props.removeTasksAction([row.id]); ElMessage.success('任务已删除') } catch (error) { if (!['cancel', 'close'].includes(error)) ElMessage.error(error.message || '删除失败') }
}
async function removeSelected() {
  const ids = [...props.selectedTaskIds]
  if (!ids.length) return
  try { await ElMessageBox.confirm(`确认删除选中的 ${ids.length} 个任务？`, '批量删除', { type: 'warning' }); await props.removeTasksAction(ids); clearSelection(); ElMessage.success(`已删除 ${ids.length} 个任务`) } catch (error) { if (!['cancel', 'close'].includes(error)) ElMessage.error(error.message || '批量删除失败') }
}
</script>

<style scoped>
.task-panel{overflow:hidden;border:1px solid rgb(191 219 254 / 64%);border-radius:22px;background:rgb(255 255 255 / 90%);box-shadow:0 18px 42px rgb(15 23 42 / 7%);backdrop-filter:blur(18px)}
.task-panel :deep(.el-card__header){padding:17px 22px;border-bottom:1px solid #e5edf8}
.task-panel :deep(.el-card__body){padding:0 22px 20px}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:20px}
.panel-title strong,.panel-title small{display:block}
.panel-title strong{color:#172033;font-size:17px;line-height:1.35}
.panel-title small{margin-top:5px;color:#64748b;font-size:12px;line-height:1.55}
.panel-actions{display:flex;align-items:center;justify-content:flex-end;gap:10px;flex:none}
.panel-actions .el-input{width:250px}
.panel-actions .el-select{width:142px}
.panel-actions .el-button{margin:0}
.task-summary{display:flex;align-items:center;gap:16px;min-height:44px;color:#64748b;font-size:12px}
.task-summary strong{color:#172033;font-size:14px}
.task-summary i{width:1px;height:16px;background:#dbe5f2}
.status-dot{display:inline-block;width:7px;height:7px;margin-right:6px;border-radius:50%;vertical-align:1px}
.status-dot--enabled{background:#22c55e;box-shadow:0 0 0 3px #dcfce7}
.status-dot--disabled{background:#94a3b8;box-shadow:0 0 0 3px #f1f5f9}
.task-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:12px}
.task-card{overflow:hidden;border:1px solid #dce6f3;border-radius:17px;background:#fff;box-shadow:0 8px 24px rgb(15 23 42 / 4%);transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease}
.task-card:hover{border-color:#bfdbfe;box-shadow:0 12px 28px rgb(37 99 235 / 9%);transform:translateY(-1px)}
.task-card--selected{border-color:#60a5fa;box-shadow:0 0 0 2px rgb(59 130 246 / 12%),0 12px 28px rgb(37 99 235 / 9%)}
.task-card--disabled{background:linear-gradient(145deg,#fff,#f8fafc)}
.task-card__header{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:11px;padding:12px 15px;border-bottom:1px solid #edf2f8}
.task-card__header :deep(.el-checkbox){height:auto}
.task-card__title{display:grid;min-width:0}
.task-card__title strong{overflow:hidden;color:#172033;font-size:15px;line-height:1.35;text-overflow:ellipsis;white-space:nowrap}
.task-card__state{display:flex;align-items:center;gap:9px;color:#64748b;font-size:12px}
.task-card__body{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));padding:13px 2px}
.task-detail{display:grid;align-content:start;min-width:0;gap:5px;padding:0 12px;border-left:1px solid #edf2f8}
.task-detail:first-child{border-left:0}
.task-detail__label{color:#94a3b8;font-size:11px;font-weight:600}
.task-detail strong{overflow:hidden;color:#334155;font-size:13px;line-height:1.5;text-overflow:ellipsis;white-space:nowrap}
.task-detail small{overflow:hidden;color:#64748b;font-size:11px;line-height:1.5;text-overflow:ellipsis;white-space:nowrap}
.task-detail--identity>strong{color:#1e3a5f}
.task-plan-summary{color:#2563eb!important}
.time-tags,.preset-tags{display:flex;align-items:center;flex-wrap:wrap;gap:6px;min-height:24px}
.scan-time{font-variant-numeric:tabular-nums}
.muted{color:#94a3b8;font-size:12px}
.task-card__footer{display:flex;align-items:center;justify-content:flex-end;padding:8px 12px;background:#f8fafc;border-top:1px solid #edf2f8}
.task-card__actions{display:flex;align-items:center;gap:8px}
.task-card__actions .el-button+.el-button{margin-left:0}
.task-empty{display:grid;place-items:center;padding:34px 20px 42px;text-align:center}
.task-empty :deep(.el-empty){padding-bottom:0}
.task-editor-form{max-height:min(80vh,860px);overflow-x:hidden;overflow-y:auto;padding:2px 4px 4px}.editor-layout{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));grid-template-areas:"basic strategy" "location location";align-items:stretch;gap:14px}.editor-section:nth-child(1){grid-area:basic}.editor-section:nth-child(2){grid-area:location}.editor-section:nth-child(3){grid-area:strategy}.editor-section{min-width:0;overflow:hidden;padding:16px 16px 6px;border:1px solid #dbeafe;border-radius:18px;background:linear-gradient(145deg,#fff 0%,#f8fbff 100%);box-shadow:0 10px 28px rgb(37 99 235 / 6%)}.editor-section :deep(.el-form-item__content){min-width:0}.editor-section header{display:flex;align-items:center;gap:10px;margin-bottom:15px;padding-bottom:12px;border-bottom:1px solid #e8eef8}.editor-section header strong,.editor-section header small{display:block}.editor-section header strong{color:#172033;font-size:15px}.editor-section header small{margin-top:2px;color:#8492a6;font-size:11px}.section-index{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;font-size:11px;font-weight:800;box-shadow:0 7px 16px rgb(37 99 235 / 22%)}.el-select,.el-input-number{width:100%}.field-tip{display:block;margin-top:7px;color:#64748b;font-size:11px}.schedule-list{display:grid;grid-template-columns:minmax(0,1fr);gap:8px;width:100%;min-width:0}.date-range{display:grid;grid-template-columns:minmax(0,1fr);gap:8px;width:100%;min-width:0}.schedule-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px;width:100%;min-width:0}.schedule-row :deep(.el-date-editor.el-input){width:100%!important;min-width:0}.date-range :deep(.el-date-editor.el-input){width:100%!important;min-width:0}.switch-options{display:grid;gap:8px;padding:12px;border-radius:12px;background:#eff6ff}.switch-options .el-checkbox{margin-right:0}.task-plan-summary{color:#2563eb!important}.date-plan-card{display:flex;width:100%;min-width:0;align-items:center;justify-content:space-between;gap:12px;padding:12px;border:1px solid #dbeafe;border-radius:13px;background:#f8fbff}.date-plan-card__content{display:grid;min-width:0;gap:5px}.date-plan-card__content strong{overflow:hidden;color:#1e3a5f;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.date-plan-card__content small{color:#64748b;font-size:10px}.date-plan-card__tags{display:flex;flex-wrap:wrap;gap:5px}.date-plan-card>.el-button{flex:none}.schedule-drawer__body{display:grid;gap:16px;padding:0 4px 18px}.schedule-drawer__intro{display:grid;gap:5px;padding:13px 14px;border:1px solid #dbeafe;border-radius:13px;background:#eff6ff}.schedule-drawer__intro strong{color:#1e3a5f;font-size:14px}.schedule-drawer__intro small{color:#64748b;line-height:1.55}.date-range--drawer{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media(min-width:1500px){.task-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.task-card__body{grid-template-columns:repeat(2,minmax(0,1fr));row-gap:14px}.task-detail:nth-child(3){border-left:0}.task-detail:nth-child(n+3){padding-top:2px}}
@media(max-width:1200px){.panel-head{align-items:flex-start;flex-direction:column}.panel-actions{width:100%}.panel-actions .el-input{flex:1;width:auto}.task-editor-form{max-height:76vh}}
@media(max-width:680px){
  .task-panel :deep(.el-card__header){padding:12px}
  .task-panel :deep(.el-card__body){padding:0 12px 14px}
  .panel-actions{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);width:100%;gap:8px}
  .panel-actions .el-input,.panel-actions .el-select,.panel-actions .el-button{width:100%;min-width:0;margin:0}
  .task-summary{min-height:38px;gap:12px;padding:6px 0;flex-wrap:wrap}
  .task-summary i{display:none}
  .task-grid{gap:9px}
  .task-card{border-radius:13px;box-shadow:none}
  .task-card:hover{box-shadow:none;transform:none}
  .task-card__header{grid-template-columns:auto minmax(0,1fr) auto;gap:8px;padding:9px 11px}
  .task-card__title strong{font-size:14px}
  .task-card__state{grid-column:auto;justify-content:flex-end}
  .task-card__state span{display:none}
  .task-card__state :deep(.el-switch){--el-switch-on-color:#3b82f6}
  .task-card__body{grid-template-columns:repeat(2,minmax(0,1fr));padding:0 11px}
  .task-detail,.task-detail:nth-child(3){gap:2px;padding:9px 8px;border-top:0;border-left:0}
  .task-detail:nth-child(even){border-left:1px solid #edf2f8}
  .task-detail:nth-child(n+3){border-top:1px solid #edf2f8}
  .task-detail:nth-child(odd){padding-left:0}
  .task-detail:nth-child(even){padding-right:0}
  .task-detail__label{font-size:10px}
  .task-detail strong{font-size:12px;line-height:1.4}
  .task-detail small{font-size:10px;line-height:1.4}
  .time-tags,.preset-tags{min-height:20px;gap:4px}
  .time-tags :deep(.el-tag),.preset-tags :deep(.el-tag){height:20px;padding-inline:6px}
  .task-card__footer{padding:7px 10px}
  .task-card__actions{display:grid;grid-template-columns:1fr 1fr auto;width:100%;gap:7px}
  .task-card__actions .el-button{width:100%;margin:0}
  .editor-layout{grid-template-columns:1fr;grid-template-areas:"basic" "strategy" "location"}
  .date-range{grid-template-columns:1fr}
  .task-editor-form{max-height:72vh}
  .editor-section{padding:14px 13px 4px}
  .date-plan-card{align-items:stretch;flex-direction:column}
  .date-plan-card>.el-button{width:100%}
  .date-range--drawer{grid-template-columns:1fr}
}
</style>
