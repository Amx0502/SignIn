<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover" class="task-list-card">
          <template #header>
            <div class="card-header">
              <span>任务列表</span>
              <el-space>
                <el-select
                  v-model="selectedAccountIndex"
                  placeholder="请选择用户"
                  clearable
                  style="width: 220px"
                  @change="onAccountChange"
                >
                  <el-option
                    v-for="(acc, idx) in state.accounts"
                    :key="idx"
                    :label="`${acc.name} (${acc.mobile})`"
                    :value="idx"
                  />
                </el-select>
                <el-tag v-if="currentAccount && currentAccount.projects && currentAccount.projects.length > 0" type="info" size="small">
                  任务上限 {{ (currentAccount.tasks || []).length }}/{{ currentAccount.projects.length }}
                </el-tag>
              </el-space>
            </div>
          </template>

          <el-table
            :data="accountTasks"
            highlight-current-row
            @current-change="onSelectTask"
            style="width: 100%"
            max-height="360"
            empty-text="当前账号下暂无任务"
          >
            <el-table-column prop="task.title" label="标题" min-width="80" />
            <el-table-column prop="task.index" label="序号" width="80" />
            <el-table-column label="文本" min-width="80" show-overflow-tooltip>
              <template #default="scope">{{ scope.row.task.text || '-' }}</template>
            </el-table-column>
            <el-table-column label="位置" width="80">
              <template #default="scope">
                <el-tag :type="locationTagType(scope.row.task)" size="small">
                  {{ locationTagText(scope.row.task) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="图片" width="80">
              <template #default="scope">
                <el-tag :type="(scope.row.task.pic_path || []).length ? 'warning' : 'info'" size="small">
                  {{ (scope.row.task.pic_path || []).length }}张
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时间" min-width="80">
              <template #default="scope">{{ (scope.row.task.times || []).join(', ') }}</template>
            </el-table-column>
            <el-table-column label="启用" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.task.enable ? 'success' : 'info'" size="small">
                  {{ scope.row.task.enable ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="周末跳过" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.task.skip_weekends ? 'warning' : 'info'" size="small">
                  {{ scope.row.task.skip_weekends ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="企微通知" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.task.notify_wechat !== false ? 'success' : 'info'" size="small">
                  {{ scope.row.task.notify_wechat !== false ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <div class="form-section project-section">
            <div class="section-header">
              <span>签到项目列表</span>
              <el-button :icon="Search" size="small" @click="fetchProjects" :disabled="selectedAccountIndex < 0">
                获取项目列表
              </el-button>
            </div>
            <el-empty v-if="!projects.length" description="先选择账号，再点击“获取签到项目列表”" :image-size="80" />
            <el-scrollbar v-else max-height="220">
              <div
                v-for="(item, idx) in projects"
                :key="idx"
                class="project-item"
                @click="applyProject(idx, item)"
              >
                <span class="project-index">{{ idx + 1 }}</span>
                <span class="project-title">{{ item.title || '未命名项目' }}</span>
              </div>
            </el-scrollbar>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="hover" class="task-form-card">
          <template #header>
            <div class="card-header">
              <span>任务设置</span>
              <el-tag :type="(form.pic_path && form.pic_path.length) ? 'warning' : 'primary'">
                {{ (form.pic_path && form.pic_path.length) ? '图片签到' : '普通签到' }}
              </el-tag>
            </div>
          </template>
          <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
            <el-form-item label="任务标题" prop="title">
              <el-input v-model="form.title" placeholder="请输入任务标题" />
            </el-form-item>
            <el-form-item label="项目序号" prop="index">
              <el-input-number v-model="form.index" :min="1" style="width: 100%" />
            </el-form-item>
            <el-form-item label="执行时间" prop="times">
              <el-input v-model="timesText" placeholder="08:00:00 18:00:00（支持空格、逗号、竖线等分隔符）" />
            </el-form-item>
            <el-form-item label="签到文本" prop="text">
              <el-input v-model="form.text" type="textarea" :rows="3" placeholder="请输入签到时需要提交的文本内容" />
            </el-form-item>
            <el-form-item label="签到位置">
              <el-radio-group v-model="locationMode">
                <el-radio value="none">不使用位置</el-radio>
                <el-radio value="auto">自动获取位置</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="签到图片">
              <el-upload
                :file-list="fileList"
                :http-request="customUpload"
                :on-remove="onImageRemove"
                :on-preview="onPreview"
                accept="image/*"
                :limit="3"
                multiple
              >
                <el-button type="primary" :icon="Upload">点击上传图片</el-button>
              </el-upload>
              <div class="upload-tip">最多可上传 3 张图片，留空表示不使用图片签到</div>
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="form.enable">启用任务</el-checkbox>
              <el-checkbox v-model="form.skip_weekends">周末跳过</el-checkbox>
              <el-checkbox v-model="form.notify_wechat">发送企业微信通知</el-checkbox>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveTask">保存任务</el-button>
              <el-button @click="createNew">重置</el-button>
            </el-form-item>
            <el-form-item v-if="selectedActualIndex >= 0">
              <el-space wrap>
                <el-button type="success" :icon="VideoPlay" @click="runTask">执行选中任务</el-button>
                <el-button type="danger" :icon="Delete" @click="deleteTask">删除任务</el-button>
              </el-space>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="previewVisible" title="图片预览" width="fit-content" align-center>
      <img :src="previewUrl" style="max-width: 100%; max-height: 70vh; border-radius: 8px;" />
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import { Search, VideoPlay, Delete, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppState } from '../composables/useAppState'
import api from '../api'

const { state, refreshState, refreshLogs, selectedAccountIndex } = useAppState()

const selectedActualIndex = ref(-1)
const projects = ref([])
const formRef = ref(null)
const fileList = ref([])
const previewVisible = ref(false)
const previewUrl = ref('')
const locationMode = ref('none')

const form = reactive({
  title: '',
  index: 1,
  times: [],
  text: '',
  pic_path: [],
  enable: true,
  use_location: false,
  skip_weekends: false,
  mode: 'normal',
  notify_wechat: true
})

const timesText = computed({
  get: () => (form.times || []).join(', '),
  set: val => { form.times = val.split(/[\s,|;，；、]+/).map(s => s.trim()).filter(Boolean) }
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

const currentAccount = computed(() => state.value.accounts[selectedAccountIndex.value] || null)

watch(locationMode, (val) => {
  if (val === 'none') {
    form.use_location = false
  } else if (val === 'auto') {
    form.use_location = true
  }
})

function syncLocationMode() {
  locationMode.value = form.use_location ? 'auto' : 'none'
}

function locationTagType(task) {
  return task.use_location ? 'success' : 'info'
}

function locationTagText(task) {
  return task.use_location ? '自动' : '无'
}

const accountTasks = computed(() => {
  if (!currentAccount.value) return []
  return (currentAccount.value.tasks || []).map((task, actualIndex) => ({ task, actualIndex }))
})



onMounted(async () => {
  if (selectedAccountIndex.value != null) {
    await fetchProjects()
  }
})

async function onAccountChange() {
  selectedActualIndex.value = -1
  projects.value = []
  createNew()
  if (selectedAccountIndex.value != null) {
    await fetchProjects()
  }
}

function syncFileList() {
  const paths = Array.isArray(form.pic_path) ? form.pic_path : (form.pic_path ? [form.pic_path] : [])
  fileList.value = paths.map((path, idx) => {
    const name = String(path).replace(/\\/g, '/').split('/').pop() || 'image.jpg'
    const url = path.startsWith('http') ? path : `/uploads/${name}`
    return { uid: `${idx}`, name, url, path, status: 'success' }
  })
}

function createNew() {
  selectedActualIndex.value = -1
  form.title = ''
  form.index = 1
  form.times = []
  form.text = ''
  form.pic_path = []
  form.enable = true
  form.use_location = false
  form.skip_weekends = false
  form.mode = 'normal'
  form.notify_wechat = true
  locationMode.value = 'none'
  fileList.value = []
}

function onSelectTask(row) {
  if (!row) return
  selectedActualIndex.value = row.actualIndex
  const task = row.task
  form.title = task.title
  form.index = task.index
  form.times = [...(task.times || [])]
  form.text = task.text
  const taskPicPaths = Array.isArray(task.pic_path) ? task.pic_path : (task.pic_path ? [task.pic_path] : [])
  form.pic_path = taskPicPaths
  form.enable = task.enable
  form.use_location = task.use_location
  form.skip_weekends = task.skip_weekends
  form.mode = task.mode || (taskPicPaths.length ? 'image' : 'normal')
  form.notify_wechat = task.notify_wechat !== false
  syncLocationMode()
  syncFileList()
}

async function customUpload(options) {
  try {
    const res = await api.uploadImage(options.file)
    if (res.data && res.data.path) {
      if (!Array.isArray(form.pic_path)) form.pic_path = []
      form.pic_path.push(res.data.path)
      syncFileList()
    }
    options.onSuccess(res)
    ElMessage.success('图片上传成功')
  } catch (err) {
    options.onError(err)
    ElMessage.error(err.message || '图片上传失败')
  }
}

function onImageRemove(file, fileList) {
  const removedPath = file.path || file.url
  form.pic_path = form.pic_path.filter(p => {
    const pName = String(p).replace(/\\/g, '/').split('/').pop()
    const rName = String(removedPath).replace(/\\/g, '/').split('/').pop()
    return pName !== rName
  })
}

function onPreview(file) {
  let url = ''
  if (file.url) {
    url = file.url
  } else if (file.path) {
    const name = String(file.path).replace(/\\/g, '/').split('/').pop()
    url = `/uploads/${name}`
  }
  previewUrl.value = url
  previewVisible.value = true
}

async function fetchProjects() {
  if (selectedAccountIndex.value == null) return
  try {
    const res = await api.fetchProjects(selectedAccountIndex.value)
    projects.value = res.data || []
  } catch (err) {
    ElMessage.error(err.message)
  }
}

function applyProject(idx, item) {
  form.index = idx + 1
  if (!form.title) form.title = item.title || `任务${idx + 1}`
}

async function saveTask() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  if (selectedAccountIndex.value == null) {
    ElMessage.warning('请先选择账号')
    return
  }
  form.mode = (form.pic_path && form.pic_path.length) ? 'image' : 'normal'
  try {
    const account = state.value.accounts[selectedAccountIndex.value]
    const tasks = account?.tasks || []
    const existingTaskIndex = tasks.findIndex(t => t.index === form.index)
    
    if (existingTaskIndex >= 0) {
      await api.updateTask(selectedAccountIndex.value, existingTaskIndex, { ...form })
      ElMessage.success('任务已更新')
    } else {
      const projectCount = account?.projects?.length || 0
      if (projectCount > 0 && tasks.length >= projectCount) {
        ElMessage.warning(`任务数量已达上限，最多可添加 ${projectCount} 个任务`)
        return
      }
      await api.addTask(selectedAccountIndex.value, { ...form })
      ElMessage.success('任务已新增')
      createNew()
    }
    await refreshState()
    await refreshLogs()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function runTask() {
  try {
    const res = await api.runTask(selectedAccountIndex.value, selectedActualIndex.value)
    const data = res.data || {}
    
    let imageHtml = ''
    if (data.image_urls && data.image_urls.length) {
      imageHtml = `
        <div style="padding: 0 24px 20px;">
          <p style="font-size: 14px; color: #6b7280; font-weight: 500; margin-bottom: 12px;">📷 图片 (${data.image_urls.length}张)</p>
          <div style="display: flex; flex-wrap: wrap; gap: 8px; max-height: 200px; overflow: hidden;">
            ${data.image_urls.map(url => `<img src="${url}" style="width: calc(50% - 4px); height: auto; max-width: 140px; max-height: 100px; object-fit: contain; border-radius: 8px; background: #fff; box-sizing: border-box;" />`).join('')}
          </div>
        </div>
      `
    }
    
    let message = `
      <div style="background: linear-gradient(135deg, #f0fdf4, #ecfdf5); border-radius: 16px; overflow: hidden;">
        <div style="display: flex; align-items: center; gap: 12px; padding: 20px 24px; background: linear-gradient(135deg, #10b981, #059669);">
          <div style="width: 36px; height: 36px; background: rgba(255, 255, 255, 0.2); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 20px; color: #fff; font-weight: 700;">✓</div>
          <div style="font-size: 20px; font-weight: 700; color: #fff;">签到成功！</div>
        </div>
        <div style="padding: 20px 24px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 12px 0; border-bottom: 1px solid #d1fae5;">
            <span style="font-size: 14px; color: #6b7280; font-weight: 500;">📝 任务标题</span>
            <span style="font-size: 14px; color: #1f2937; font-weight: 600; text-align: right; max-width: 60%; word-break: break-all;">${data.title || '-'}</span>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 12px 0; border-bottom: 1px solid #d1fae5;">
            <span style="font-size: 14px; color: #6b7280; font-weight: 500;">🏢 实际项目</span>
            <span style="font-size: 14px; color: #1f2937; font-weight: 600; text-align: right; max-width: 60%; word-break: break-all;">${data.real_title || '-'}</span>
          </div>
          ${data.text ? `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 12px 0; border-bottom: 1px solid #d1fae5;">
              <span style="font-size: 14px; color: #6b7280; font-weight: 500;">💬 文本内容</span>
              <span style="font-size: 14px; color: #1f2937; font-weight: 600; text-align: right; max-width: 60%; word-break: break-all;">${data.text}</span>
            </div>
          ` : ''}
          ${data.location ? `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 12px 0;">
              <span style="font-size: 14px; color: #6b7280; font-weight: 500;">📍 位置</span>
              <span style="font-size: 14px; color: #1f2937; font-weight: 600; text-align: right; max-width: 60%; word-break: break-all;">${data.location.address || '-'}</span>
            </div>
          ` : ''}
        </div>
        ${imageHtml}
      </div>
    `
    
    ElMessageBox.alert(message, '签到结果', { 
      dangerouslyUseHTMLString: true,
      customClass: 'result-dialog',
      confirmButtonText: '关闭',
      confirmButtonClass: 'result-confirm-btn'
    })
    await refreshLogs()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function deleteTask() {
  try {
    await ElMessageBox.confirm('确认删除当前任务吗？', '提示', { type: 'warning' })
    await api.deleteTask(selectedAccountIndex.value, selectedActualIndex.value)
    createNew()
    await refreshState()
    await refreshLogs()
    ElMessage.success('任务已删除')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}


</script>

<style scoped>
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 500;
}
.project-section {
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px;
  margin-top: 16px;
}
.project-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  margin-bottom: 6px;
  background: #fff;
  transition: all 0.2s ease;
}
.project-item:hover {
  background: #eef4ff;
  border-color: #dbeafe;
  transform: translateX(4px);
}
.project-index {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e0e7ff;
  color: #4338ca;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.project-title {
  font-size: 14px;
  color: #334155;
}
.upload-tip {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
}

.result-dialog :deep(.el-message-box) {
  width: 480px;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  border: none;
}

.result-dialog :deep(.el-message-box__header) {
  border-bottom: none;
  padding: 24px 24px 0;
}

.result-dialog :deep(.el-message-box__title) {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

.result-dialog :deep(.el-message-box__content) {
  padding: 16px 24px;
  overflow: auto;
  max-height: 60vh;
}

.result-dialog :deep(.el-message-box__btns) {
  border-top: none;
  padding: 0 24px 24px;
  justify-content: center;
}

.result-dialog :deep(.result-confirm-btn) {
  width: 100%;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #10b981, #059669);
  border: none;
  font-size: 15px;
  font-weight: 600;
}

.result-card {
  background: linear-gradient(135deg, #f0fdf4, #ecfdf5);
  border-radius: 16px;
  overflow: hidden;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 24px;
  background: linear-gradient(135deg, #10b981, #059669);
}

.result-icon {
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #fff;
  font-weight: 700;
}

.result-title {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
}

.result-body {
  padding: 20px 24px;
}

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 12px 0;
  border-bottom: 1px solid #d1fae5;
}

.result-item:last-child {
  border-bottom: none;
}

.item-label {
  font-size: 14px;
  color: #6b7280;
  font-weight: 500;
}

.item-value {
  font-size: 14px;
  color: #1f2937;
  font-weight: 600;
  text-align: right;
  max-width: 60%;
  word-break: break-all;
}

.result-images {
  padding: 0 24px 20px;
}

.result-label {
  font-size: 14px;
  color: #6b7280;
  font-weight: 500;
  margin-bottom: 12px;
}

.image-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 200px;
  overflow: hidden;
}

.result-img {
  width: calc(50% - 4px);
  height: auto;
  max-width: 140px;
  max-height: 100px;
  object-fit: contain;
  border-radius: 8px;
  background: #fff;
  box-sizing: border-box;
}

@media (max-width: 768px) {
  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .project-item {
    padding: 10px;
  }
  
  .project-title {
    font-size: 13px;
  }
  
  .result-dialog :deep(.el-message-box) {
    width: 90vw;
    max-width: 360px;
  }
  
  .el-form-item__label {
    width: 80px !important;
    font-size: 12px;
  }
  
  .el-form-item__content {
    margin-left: 80px !important;
  }
}

@media (max-width: 480px) {
  .project-section {
    padding: 12px;
  }
  
  .project-item {
    padding: 8px;
    gap: 8px;
  }
  
  .project-index {
    width: 22px;
    height: 22px;
    font-size: 11px;
  }
  
  .project-title {
    font-size: 12px;
  }
  
  .el-form-item__label {
    width: 70px !important;
    font-size: 11px;
  }
  
  .el-form-item__content {
    margin-left: 70px !important;
  }
  
  .el-button {
    width: 100%;
    margin-bottom: 4px;
  }
}
</style>
