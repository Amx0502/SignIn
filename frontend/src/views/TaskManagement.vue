<template>
  <div class="page-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>任务管理</span>
          <el-tag type="info" size="small">{{ allTasks.length }} 个任务</el-tag>
        </div>
      </template>
      
      <div v-if="allTasks.length === 0" class="empty-state">
        <el-empty description="系统中暂无任务" :image-size="80" />
      </div>
      
      <div v-else class="task-list">
        <div
          v-for="task in allTasks"
          :key="`${task.accountIndex}-${task.taskIndex}`"
          class="task-wrapper"
        >
          <div class="task-card">
            <div class="task-main">
              <div class="task-title-row">
                <el-tag :type="task.enable ? 'success' : 'info'" size="small">{{ task.enable ? '启用' : '禁用' }}</el-tag>
                <span class="task-title">{{ task.title }}</span>
                <el-tag :type="task.mode === 'image' ? 'warning' : 'primary'" size="small">
                  {{ task.mode === 'image' ? '图片签到' : '普通签到' }}
                </el-tag>
              </div>
              <div class="task-info">
                <span><el-icon><User /></el-icon>{{ task.accountName }}</span>
                <span><el-icon><List /></el-icon>项目{{ task.index }}</span>
                <span><el-icon><Clock /></el-icon>{{ (task.times || []).join(', ') }}</span>
                <span v-if="task.use_location"><el-icon><MapLocation /></el-icon>位置</span>
                <span v-if="task.pic_path && task.pic_path.length"><el-icon><Picture /></el-icon>{{ task.pic_path.length }}张图</span>
                <span v-if="task.skip_weekends"><el-icon><Calendar /></el-icon>周末跳过</span>
              </div>
            </div>
            <div class="task-actions">
              <el-button 
                :type="isEditing(task) ? 'info' : 'primary'" 
                size="small" 
                :icon="Edit" 
                @click="toggleInlineEdit(task)"
              >{{ isEditing(task) ? '关闭' : '编辑' }}</el-button>
              <el-button type="success" size="small" :icon="VideoPlay" @click="runTask(task)">执行</el-button>
              <el-button type="danger" size="small" :icon="Delete" @click="deleteTask(task)">删除</el-button>
            </div>
          </div>

          <div v-if="isEditing(task)" class="inline-edit-panel">
            <el-card shadow="always" class="edit-card">
              <template #header>
                <div class="edit-header">
                  <span>编辑任务 - {{ task.title }}</span>
                </div>
              </template>
              <el-form :model="getEditForm(task)" label-width="100px" :rules="rules" :ref="`formRef-${task.accountIndex}-${task.taskIndex}`">
                <el-form-item label="任务标题" prop="title">
                  <el-input v-model="getEditForm(task).title" placeholder="请输入任务标题" />
                </el-form-item>
                <el-form-item label="项目序号" prop="index">
                  <el-input-number v-model="getEditForm(task).index" :min="1" style="width: 100%" />
                </el-form-item>
                <el-form-item label="执行时间" prop="times">
                  <el-input v-model="editTimesInputs[getTaskKey(task)]" placeholder="08:00:00,18:00:00" />
                </el-form-item>
                <el-form-item label="签到文本" prop="text">
                  <el-input v-model="getEditForm(task).text" type="textarea" :rows="3" placeholder="请输入签到时需要提交的文本内容" />
                </el-form-item>
                <el-form-item label="签到位置">
                  <el-radio-group v-model="editLocationModes[getTaskKey(task)]">
                    <el-radio label="none">不使用位置</el-radio>
                    <el-radio label="auto">自动获取位置</el-radio>
                  </el-radio-group>
                </el-form-item>
                <el-form-item label="签到图片">
                  <el-upload
                    :ref="`uploadRef-${task.accountIndex}-${task.taskIndex}`"
                    :file-list="getEditFileList(task)"
                    :http-request="(options) => customUpload(task, options)"
                    :on-remove="(file) => onImageRemove(task, file)"
                    :on-preview="(file) => onPreview(file)"
                    accept="image/*"
                    :limit="3"
                    multiple
                  >
                    <el-button type="primary" :icon="Upload">点击上传图片</el-button>
                  </el-upload>
                  <div class="upload-tip">最多可上传 3 张图片，留空表示不使用图片签到</div>
                </el-form-item>
                <el-form-item>
                  <el-checkbox v-model="getEditForm(task).enable">启用任务</el-checkbox>
                  <el-checkbox v-model="getEditForm(task).skip_weekends">周末跳过</el-checkbox>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="saveInlineEdit(task)">保存任务</el-button>
                  <el-button @click="toggleInlineEdit(task)">取消</el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="previewVisible" title="图片预览" width="fit-content" align-center>
      <img :src="previewUrl" style="max-width: 100%; max-height: 70vh; border-radius: 8px;" />
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { Edit, VideoPlay, Delete, Upload, User, List, Clock, MapLocation, Picture, Calendar } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppState } from '../composables/useAppState'
import api from '../api'

const { state: appState, refreshState, refreshLogs } = useAppState()
const previewVisible = ref(false)
const previewUrl = ref('')
const editingKey = ref(null)
const editForms = reactive({})
const editFileLists = reactive({})
const editTimesInputs = reactive({})
const editLocationModes = reactive({})

const allTasks = computed(() => {
  const tasks = []
  appState.value.accounts.forEach((account, accountIdx) => {
    (account.tasks || []).forEach((task, taskIdx) => {
      tasks.push({
        ...task,
        accountName: account.name,
        accountIndex: accountIdx,
        taskIndex: taskIdx
      })
    })
  })
  return tasks
})

const rules = {
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  index: [{ required: true, message: '请输入项目序号', trigger: 'blur' }],
  times: [{
    validator: (rule, value, callback) => {
      if (!value || value.length === 0) {
        callback(new Error('请至少设置一个执行时间'))
      } else {
        callback()
      }
    },
    trigger: 'blur'
  }]
}

function getTaskKey(task) {
  return `${task.accountIndex}-${task.taskIndex}`
}

function isEditing(task) {
  return editingKey.value === getTaskKey(task)
}

function getEditForm(task) {
  const key = getTaskKey(task)
  if (!editForms[key]) {
    editForms[key] = reactive({
      title: task.title || '',
      index: task.index || 1,
      times: [...(task.times || [])],
      text: task.text || '',
      pic_path: [...(task.pic_path || [])],
      enable: task.enable !== false,
      use_location: task.use_location || false,
      skip_weekends: task.skip_weekends || false,
      mode: task.mode || 'normal'
    })
  }
  return editForms[key]
}

function getEditFileList(task) {
  const key = getTaskKey(task)
  if (!editFileLists[key]) {
    const paths = Array.isArray(task.pic_path) ? task.pic_path : (task.pic_path ? [task.pic_path] : [])
    editFileLists[key] = paths.map((path, idx) => ({
      uid: `${idx}`,
      name: String(path).replace(/\\/g, '/').split('/').pop() || 'image.jpg',
      url: path.startsWith('http') ? path : `http://127.0.0.1:8765/uploads/${String(path).replace(/\\/g, '/').split('/').pop()}`,
      path
    }))
  }
  return editFileLists[key]
}

function getEditTimesInput(task) {
  const key = getTaskKey(task)
  if (editTimesInputs[key] === undefined) {
    editTimesInputs[key] = (task.times || []).join(', ')
  }
  return editTimesInputs[key]
}

function getEditLocationMode(task) {
  const key = getTaskKey(task)
  if (editLocationModes[key] === undefined) {
    editLocationModes[key] = task.use_location ? 'auto' : 'none'
  }
  return editLocationModes[key]
}

function toggleInlineEdit(task) {
  const key = getTaskKey(task)
  if (editingKey.value === key) {
    editingKey.value = null
    delete editForms[key]
    delete editFileLists[key]
    delete editTimesInputs[key]
    delete editLocationModes[key]
  } else {
    editingKey.value = key
    
    editForms[key] = reactive({
      title: task.title || '',
      index: task.index || 1,
      times: [...(task.times || [])],
      text: task.text || '',
      pic_path: [...(task.pic_path || [])],
      enable: task.enable !== false,
      use_location: task.use_location || false,
      skip_weekends: task.skip_weekends || false,
      mode: task.mode || 'normal'
    })
    
    const paths = Array.isArray(task.pic_path) ? task.pic_path : (task.pic_path ? [task.pic_path] : [])
    editFileLists[key] = paths.map((path, idx) => ({
      uid: `${idx}`,
      name: String(path).replace(/\\/g, '/').split('/').pop() || 'image.jpg',
      url: path.startsWith('http') ? path : `http://127.0.0.1:8765/uploads/${String(path).replace(/\\/g, '/').split('/').pop()}`,
      path
    }))
    
    editTimesInputs[key] = (task.times || []).join(', ')
    editLocationModes[key] = task.use_location ? 'auto' : 'none'
    
    watch(() => editTimesInputs[key], (val) => {
      editForms[key].times = val.split(',').map(t => t.trim()).filter(Boolean)
    })
    
    watch(() => editLocationModes[key], (val) => {
      editForms[key].use_location = val === 'auto'
    })
  }
}

async function saveInlineEdit(task) {
  const key = getTaskKey(task)
  editForms[key].times = editTimesInputs[key].split(',').map(t => t.trim()).filter(Boolean)
  editForms[key].mode = (editForms[key].pic_path && editForms[key].pic_path.length) ? 'image' : 'normal'
  
  try {
    await api.updateTask(task.accountIndex, task.taskIndex, { ...editForms[key] })
    ElMessage.success('任务已更新')
    await refreshState()
    await refreshLogs()
    toggleInlineEdit(task)
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function customUpload(task, options) {
  const key = getTaskKey(task)
  try {
    const res = await api.uploadImage(options.file)
    if (res.data && res.data.path) {
      if (!Array.isArray(editForms[key].pic_path)) editForms[key].pic_path = []
      editForms[key].pic_path.push(res.data.path)
      const paths = editForms[key].pic_path
      editFileLists[key] = paths.map((path, idx) => ({
        uid: `${idx}`,
        name: String(path).replace(/\\/g, '/').split('/').pop() || 'image.jpg',
        url: path.startsWith('http') ? path : `http://127.0.0.1:8765/uploads/${String(path).replace(/\\/g, '/').split('/').pop()}`,
        path
      }))
    }
    options.onSuccess(res)
    ElMessage.success('图片上传成功')
  } catch (err) {
    options.onError(err)
    ElMessage.error(err.message || '图片上传失败')
  }
}

function onImageRemove(task, file) {
  const key = getTaskKey(task)
  const removedPath = file.path || file.url
  editForms[key].pic_path = editForms[key].pic_path.filter(p => {
    const pName = String(p).replace(/\\/g, '/').split('/').pop()
    const rName = String(removedPath).replace(/\\/g, '/').split('/').pop()
    return pName !== rName
  })
  const paths = editForms[key].pic_path
  editFileLists[key] = paths.map((path, idx) => ({
    uid: `${idx}`,
    name: String(path).replace(/\\/g, '/').split('/').pop() || 'image.jpg',
    url: path.startsWith('http') ? path : `http://127.0.0.1:8765/uploads/${String(path).replace(/\\/g, '/').split('/').pop()}`,
    path
  }))
}

function onPreview(file) {
  previewUrl.value = file.url || ''
  previewVisible.value = true
}

async function runTask(row) {
  try {
    const res = await api.runTask(row.accountIndex, row.taskIndex)
    const data = res.data || {}
    let message = `<div style="line-height: 1.8;">`
    message += `<p><strong>签到成功！</strong></p>`
    message += `<p>任务标题：${data.title}</p>`
    message += `<p>实际项目：${data.real_title}</p>`
    if (data.text) message += `<p>文本内容：${data.text}</p>`
    if (data.image_urls && data.image_urls.length) message += `<p>图片数量：${data.image_urls.length}</p>`
    if (data.location) message += `<p>位置：${data.location.address}</p>`
    message += `</div>`
    ElMessageBox.alert(message, '签到结果', { dangerouslyUseHTMLString: true })
    await refreshLogs()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function deleteTask(row) {
  try {
    await ElMessageBox.confirm(`确认删除任务「${row.title}」吗？`, '提示', { type: 'warning' })
    await api.deleteTask(row.accountIndex, row.taskIndex)
    await refreshState()
    await refreshLogs()
    ElMessage.success('任务已删除')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}
</script>

<style scoped>
.page-container { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #fafafa;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  transition: all 0.2s ease;
}

.task-card:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.task-main {
  flex: 1;
  min-width: 0;
}

.task-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.task-title {
  font-weight: 700;
  color: #1f2937;
  font-size: 15px;
}

.task-info {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: #6b7280;
}

.task-info span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.task-actions {
  display: flex;
  gap: 8px;
  margin-left: 20px;
}

.inline-edit-panel {
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.edit-card {
  margin: 0;
  border-radius: 12px;
}

.edit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-state {
  padding: 40px 0;
}

.upload-tip {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
}
</style>