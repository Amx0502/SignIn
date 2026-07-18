<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover" class="task-list-card">
          <template #header>
            <div class="card-header">
              <span>任务列表</span>
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
              <span>{{ selectedActualIndex >= 0 ? '编辑任务' : '新增任务' }}</span>
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
              <el-input v-model="timesText" placeholder="08:00:00,18:00:00" />
            </el-form-item>
            <el-form-item label="签到文本" prop="text">
              <el-input v-model="form.text" type="textarea" :rows="3" placeholder="请输入签到时需要提交的文本内容" />
            </el-form-item>
            <el-form-item label="签到位置">
              <el-radio-group v-model="locationMode">
                <el-radio label="none">不使用位置</el-radio>
                <el-radio label="auto">自动获取位置</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="签到图片">
              <el-upload
                ref="uploadRef"
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
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveTask">
                {{ selectedActualIndex >= 0 ? '保存任务' : '新增任务' }}
              </el-button>
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
const uploadRef = ref(null)
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
  mode: 'normal'
})

const timesText = computed({
  get: () => (form.times || []).join(', '),
  set: val => { form.times = val.split(',').map(s => s.trim()).filter(Boolean) }
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
  fileList.value = paths.map(path => {
    const name = String(path).replace(/\\/g, '/').split('/').pop() || 'image.jpg'
    return { name, url: `/uploads/${name}`, path }
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
  previewUrl.value = file.url || ''
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
    if (selectedActualIndex.value >= 0) {
      await api.updateTask(selectedAccountIndex.value, selectedActualIndex.value, { ...form })
      ElMessage.success('任务已更新')
    } else {
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
    await api.runTask(selectedAccountIndex.value, selectedActualIndex.value)
    ElMessage.success('已加入执行队列')
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
</style>
