<template>
  <el-card class="task-panel" shadow="never">
    <template #header>
      <div class="panel-head">
        <div><strong>自动监控任务</strong><small>每 30 秒扫描指定课程，最多两个任务并发执行</small></div>
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
        <template #default="{ row }"><div class="task-name"><strong>{{ row.name }}</strong><small>每 {{ row.poll_interval_seconds || 30 }} 秒扫描</small></div></template>
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
          <el-button link type="success" @click="runNow(row)">立即执行</el-button>
          <el-button link type="danger" @click="removeOne(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无自动任务" :image-size="90" /></template>
    </el-table>

    <el-dialog v-model="editorVisible" :title="editingId ? '编辑自动任务' : '新增自动任务'" width="620px" align-center append-to-body>
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="任务名称" class="wide"><el-input v-model="draft.name" maxlength="255" placeholder="例如：高等数学签到" /></el-form-item>
          <el-form-item v-if="isAdmin" label="所属用户 ID"><el-input-number v-model="draft.owner_user_id" :min="1" :controls="false" /></el-form-item>
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
          <el-form-item label="纬度"><el-input-number v-model="draft.latitude" :precision="6" :controls="false" /></el-form-item>
          <el-form-item label="经度"><el-input-number v-model="draft.longitude" :precision="6" :controls="false" /></el-form-item>
          <el-form-item label="定位精度（米）"><el-input-number v-model="draft.accuracy" :min="0" :precision="1" :controls="false" /></el-form-item>
          <el-form-item label="预设密码">
            <el-input v-model="draft.password" type="password" show-password autocomplete="new-password" :placeholder="editingId && draft.has_password ? '已保存，留空保持不变' : '密码签到使用'" />
            <el-checkbox v-if="editingId && draft.has_password" v-model="draft.clear_password">清除已保存密码</el-checkbox>
          </el-form-item>
          <el-form-item label="默认签到照片" class="wide">
            <TaskImageUpload :file-list="photoFiles" :limit="1" :http-request="uploadPhoto" :on-remove="removePhoto" />
          </el-form-item>
          <el-form-item class="wide"><el-checkbox v-model="draft.enabled">创建后立即启用</el-checkbox></el-form-item>
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
const photoFiles = ref([])
const emptyDraft = () => ({ owner_user_id: null, account_id: null, course_id: null, name: '', enabled: true, latitude: null, longitude: null, accuracy: 20, photo_path: '', password: '', has_password: false, clear_password: false })
const draft = reactive(emptyDraft())

function accountName(id) { const row = props.accounts.find(item => item.id === id); return row?.name || row?.remote_user_name || `账号 ${id}` }
function courseName(id) { return props.courses.find(item => item.id === id)?.name || `课程 ${id}` }
function formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚未扫描' }
function selectionChanged(rows) { emit('update:selected-task-ids', new Set(rows.map(row => row.id))) }
function resetDraft(values = {}) { Object.assign(draft, emptyDraft(), values); photoFiles.value = draft.photo_path ? [{ uid: `saved-${values.id}`, name: String(draft.photo_path).split('/').pop(), path: draft.photo_path, url: `/uploads/${draft.photo_path}`, status: 'success' }] : [] }
function openCreate() { editingId.value = null; resetDraft(); editorVisible.value = true }
function openEdit(row) { editingId.value = row.id; resetDraft(row); emit('select-account', row.account_id); editorVisible.value = true }
function accountChanged(id) { draft.course_id = null; emit('select-account', id) }

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
  try { const data = await props.runTaskAction(row.id); ElMessage.success(data.accepted ? '任务已加入执行队列' : '任务正在运行，请稍后查看记录'); emit('refresh') } catch (error) { ElMessage.error(error.message || '执行失败') }
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
.panel-head { display:flex;align-items:center;justify-content:space-between;gap:14px }.panel-head strong,.panel-head small,.task-name strong,.task-name small { display:block }.panel-head strong{font-size:16px}.panel-head small,.task-name small,.muted{margin-top:4px;color:#64748b;font-size:11px}.task-name strong{color:#172033}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}.form-grid .wide{grid-column:1/-1}.el-select,.el-input-number{width:100%}
@media(max-width:760px){.panel-head{align-items:stretch;flex-direction:column}.panel-head :deep(.el-space),.panel-head :deep(.el-space__item),.panel-head .el-button{width:100%}.form-grid{grid-template-columns:1fr}.form-grid .wide{grid-column:auto}}
</style>
