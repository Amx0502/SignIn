<template>
  <el-card class="task-panel" shadow="never">
    <template #header>
      <div class="panel-head">
        <div><strong>自动签到任务</strong><small>按指定日期和时间自动获取课程签到项</small></div>
        <el-space wrap>
          <el-button
            type="danger"
            plain
            :disabled="!selectedTaskIds.size"
            @click="removeSelected"
          >批量删除({{ selectedTaskIds.size }})</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">新增任务</el-button>
        </el-space>
      </div>
    </template>

    <el-table
      ref="tableRef"
      :data="tasks"
      row-key="id"
      stripe
      @selection-change="selectionChanged"
    >
      <el-table-column type="selection" width="46" reserve-selection />
      <el-table-column label="任务" min-width="170">
        <template #default="{ row }"><div class="task-name"><strong>{{ row.name }}</strong><small>{{ (row.schedule_times || []).join('、') || '未设置时间' }}</small></div></template>
      </el-table-column>
      <el-table-column label="账号 / 课程" min-width="190">
        <template #default="{ row }"><div class="task-name"><span>{{ accountName(row.account_id) }}</span><small>{{ courseName(row.course_id) }}</small></div></template>
      </el-table-column>
      <el-table-column label="预设参数" min-width="170">
        <template #default="{ row }">
          <el-space wrap>
            <el-tag v-if="row.latitude != null && row.longitude != null" size="small" type="primary">位置</el-tag>
            <el-tag v-if="row.photo_path" size="small" type="warning">照片</el-tag>
            <el-tag v-if="row.has_password" size="small" type="info">密码</el-tag>
            <span v-if="row.latitude == null && !row.photo_path && !row.has_password" class="muted">无</span>
          </el-space>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="92">
        <template #default="{ row }"><el-switch :model-value="row.enabled" inline-prompt active-text="启" inactive-text="停" @change="value => toggleTask(row, value)" /></template>
      </el-table-column>
      <el-table-column label="最近扫描" min-width="150">
        <template #default="{ row }"><span class="muted">{{ formatTime(row.last_scan_at) }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button
            link
            type="success"
            :loading="runningTaskId === row.id"
            :disabled="runningTaskId !== null && runningTaskId !== row.id"
            @click="runNow(row)"
          >立即执行</el-button>
          <el-button link type="danger" @click="removeOne(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无自动任务" :image-size="90" /></template>
    </el-table>

    <el-dialog v-model="editorVisible" :title="editingId ? '编辑自动任务' : '新增自动任务'" width="min(960px, 94vw)" class="task-editor-dialog" align-center append-to-body>
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
              <div class="coordinate-row">
                <el-input v-model="draft.coordinateInput" placeholder="119.21, 26.03" />
                <el-button tag="a" href="https://www.lddgo.net/convert/position" target="_blank" rel="noopener noreferrer">拾取</el-button>
              </div>
              <small class="field-tip">自动识别经纬度顺序及常见分隔符</small>
            </el-form-item>
            <el-form-item label="定位精度（米）"><el-input-number v-model="draft.accuracy" :min="0" :precision="1" :controls="false" /></el-form-item>
            <el-form-item label="预设密码">
              <el-input v-model="draft.password" type="password" show-password autocomplete="new-password" :placeholder="editingId && draft.has_password ? '已保存，留空保持不变' : '密码签到使用'" />
              <el-checkbox v-if="editingId && draft.has_password" v-model="draft.clear_password">清除已保存密码</el-checkbox>
            </el-form-item>
            <el-form-item label="默认签到照片">
              <TaskImageUpload :file-list="photoFiles" :limit="1" :http-request="uploadPhoto" :on-remove="removePhoto" />
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
            <el-form-item label="执行日期范围">
              <div class="date-range">
                <el-date-picker v-model="draft.start_date" value-format="YYYY-MM-DD" type="date" placeholder="开始日期" />
                <el-date-picker v-model="draft.end_date" value-format="YYYY-MM-DD" type="date" placeholder="结束日期" />
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
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存任务</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import TaskImageUpload from '../TaskImageUpload.vue'
import { coordinateText, normalizeScheduleTimes, parseCoordinates } from '../../utils/classCubeTaskForm.js'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  accounts: { type: Array, default: () => [] },
  courses: { type: Array, default: () => [] },
  selectedTaskIds: { type: Set, default: () => new Set() },
  isAdmin: { type: Boolean, default: false },
  coursesLoading: { type: Boolean, default: false },
  saveTaskAction: { type: Function, required: true },
  removeTasksAction: { type: Function, required: true },
  runTaskAction: { type: Function, required: true },
  uploadPhotoAction: { type: Function, required: true },
})
const emit = defineEmits(['update:selected-task-ids', 'select-account', 'refresh'])
const tableRef = ref(null)
const editorVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const runningTaskId = ref(null)
const photoFiles = ref([])
const emptyDraft = () => ({ owner_user_id: null, account_id: null, course_id: null, name: '', enabled: true, coordinateInput: '', latitude: null, longitude: null, accuracy: 20, photo_path: '', password: '', has_password: false, clear_password: false, schedule_times: ['08:00:00'], start_date: null, end_date: null, notify_wecom: true })
const draft = reactive(emptyDraft())

function accountName(id) { const row = props.accounts.find(item => item.id === id); return row?.name || row?.remote_user_name || `账号 ${id}` }
function courseName(id) { return props.courses.find(item => item.id === id)?.name || `课程 ${id}` }
function formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚未扫描' }
function selectionChanged(rows) { emit('update:selected-task-ids', new Set(rows.map(row => row.id))) }
function resetDraft(values = {}) {
  Object.assign(draft, emptyDraft(), values, {
    coordinateInput: coordinateText(values),
    schedule_times: values.schedule_times?.length ? [...values.schedule_times] : ['08:00:00'],
    notify_wecom: values.notify_wecom !== false,
  })
  photoFiles.value = draft.photo_path ? [{ uid: `saved-${values.id}`, name: String(draft.photo_path).split('/').pop(), path: draft.photo_path, url: `/uploads/${draft.photo_path}`, status: 'success' }] : []
}
function openCreate() { editingId.value = null; resetDraft(); editorVisible.value = true }
function openEdit(row) { editingId.value = row.id; resetDraft(row); emit('select-account', row.account_id); editorVisible.value = true }
function accountChanged(id) {
  const account = props.accounts.find(item => item.id === id)
  draft.owner_user_id = account?.owner_user_id ?? null
  draft.course_id = null
  emit('select-account', id)
}

async function uploadPhoto(options) {
  try {
    const uploaded = await props.uploadPhotoAction(options.file, draft.account_id)
    draft.photo_path = uploaded.path || uploaded.photo_path
    photoFiles.value = [{ uid: `${Date.now()}`, name: options.file.name, path: draft.photo_path, url: uploaded.url, status: 'success' }]
    options.onSuccess(uploaded)
  } catch (error) { options.onError(error); ElMessage.error(error.message || '上传失败') }
}
function removePhoto() { photoFiles.value = []; draft.photo_path = '' }
async function save() {
  if (!draft.name.trim() || !draft.account_id || !draft.course_id) return ElMessage.warning('请填写任务名称并选择账号和课程')
  try {
    if (draft.coordinateInput.trim()) Object.assign(draft, parseCoordinates(draft.coordinateInput))
    else { draft.latitude = null; draft.longitude = null }
    draft.schedule_times = normalizeScheduleTimes(draft.schedule_times)
    if (!draft.schedule_times.length) throw new Error('请至少添加一个执行时间')
    if (draft.start_date && draft.end_date && draft.start_date > draft.end_date) throw new Error('开始日期不能晚于结束日期')
  } catch (error) { return ElMessage.warning(error.message) }
  saving.value = true
  try {
    await props.saveTaskAction({ ...draft, name: draft.name.trim() }, editingId.value)
    editorVisible.value = false
    ElMessage.success(editingId.value ? '任务已更新' : '任务已创建')
    emit('refresh')
  } catch (error) { ElMessage.error(error.message || '保存失败') } finally { saving.value = false }
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
  try { await ElMessageBox.confirm(`确认删除选中的 ${ids.length} 个任务？`, '批量删除', { type: 'warning' }); await props.removeTasksAction(ids); tableRef.value?.clearSelection(); ElMessage.success(`已删除 ${ids.length} 个任务`) } catch (error) { if (!['cancel', 'close'].includes(error)) ElMessage.error(error.message || '批量删除失败') }
}
</script>

<style scoped>
.task-panel { border:1px solid rgb(191 219 254 / 58%);border-radius:22px;background:rgb(255 255 255 / 84%);box-shadow:0 18px 42px rgb(15 23 42 / 7%);backdrop-filter:blur(18px) }
.panel-head { display:flex;align-items:center;justify-content:space-between;gap:14px }.panel-head strong,.panel-head small,.task-name strong,.task-name small { display:block }.panel-head strong{font-size:16px}.panel-head small,.task-name small,.muted{margin-top:4px;color:#64748b;font-size:11px}.task-name strong{color:#172033}
.task-editor-form{max-height:min(68vh,680px);overflow-x:hidden;overflow-y:auto;padding:2px 4px 4px}.editor-layout{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.editor-section{min-width:0;overflow:hidden;padding:16px 16px 6px;border:1px solid #dbeafe;border-radius:18px;background:linear-gradient(145deg,#fff 0%,#f8fbff 100%);box-shadow:0 10px 28px rgb(37 99 235 / 6%)}.editor-section :deep(.el-form-item__content){min-width:0}.editor-section header{display:flex;align-items:center;gap:10px;margin-bottom:15px;padding-bottom:12px;border-bottom:1px solid #e8eef8}.editor-section header strong,.editor-section header small{display:block}.editor-section header strong{color:#172033;font-size:15px}.editor-section header small{margin-top:2px;color:#8492a6;font-size:11px}.section-index{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;font-size:11px;font-weight:800;box-shadow:0 7px 16px rgb(37 99 235 / 22%)}.el-select,.el-input-number{width:100%}.coordinate-row{display:flex;align-items:center;gap:8px;width:100%;min-width:0}.coordinate-row .el-input{flex:1;min-width:0}.field-tip{display:block;margin-top:7px;color:#64748b;font-size:11px}.schedule-list{display:grid;grid-template-columns:minmax(0,1fr);gap:8px;width:100%;min-width:0}.date-range{display:grid;grid-template-columns:minmax(0,1fr);gap:8px;width:100%;min-width:0}.schedule-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px;width:100%;min-width:0}.schedule-row :deep(.el-date-editor.el-input){width:100%!important;min-width:0}.date-range :deep(.el-date-editor.el-input){width:100%!important;min-width:0}.switch-options{display:grid;gap:8px;padding:12px;border-radius:12px;background:#eff6ff}.switch-options .el-checkbox{margin-right:0}
@media(max-width:900px){.editor-layout{grid-template-columns:repeat(2,minmax(0,1fr))}.editor-section:last-child{grid-column:1/-1}.task-editor-form{max-height:72vh}}
@media(max-width:760px){.panel-head{align-items:stretch;flex-direction:column}.panel-head :deep(.el-space),.panel-head :deep(.el-space__item),.panel-head .el-button{width:100%}.editor-layout{grid-template-columns:1fr}.editor-section:last-child{grid-column:auto}.date-range{grid-template-columns:1fr}.task-editor-form{max-height:70vh}.editor-section{padding:14px 13px 4px}}
</style>
