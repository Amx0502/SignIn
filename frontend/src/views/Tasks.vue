<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>任务管理</span>
              <el-select v-model="selectedAccountIndex" placeholder="请选择账号" style="width: 220px" @change="onAccountChange">
                <el-option
                  v-for="(acc, idx) in state.accounts"
                  :key="idx"
                  :label="`${acc.name} (${acc.mobile})`"
                  :value="idx"
                />
              </el-select>
            </div>
          </template>

          <el-tabs v-model="activeMode" @tab-change="onModeChange">
            <el-tab-pane label="普通签到" name="normal" />
            <el-tab-pane label="图片签到" name="image" />
          </el-tabs>

          <el-table
            :data="filteredTasks"
            highlight-current-row
            @current-change="onSelectTask"
            style="width: 100%"
            max-height="360"
            empty-text="当前分类下暂无任务"
          >
            <el-table-column prop="task.title" label="标题" min-width="140" />
            <el-table-column label="类型" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.task.mode === 'image' ? 'warning' : 'primary'" size="small">
                  {{ scope.row.task.mode === 'image' ? '图片' : '普通' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="task.index" label="序号" width="70" />
            <el-table-column label="时间" min-width="140">
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

          <div class="form-section">
            <div class="card-header" style="margin-bottom: 12px;">
              <span>签到项目列表</span>
              <el-button :icon="Search" size="small" @click="fetchProjects" :disabled="selectedAccountIndex < 0">获取项目列表</el-button>
            </div>
            <el-empty v-if="!projects.length" description="先选择账号，再点击“获取签到项目列表”" :image-size="80" />
            <el-scrollbar v-else max-height="220">
              <div
                v-for="(item, idx) in projects"
                :key="idx"
                class="project-item"
                @click="applyProject(idx, item)"
              >
                <strong>{{ idx + 1 }}</strong> - {{ item.title || '未命名项目' }}
              </div>
            </el-scrollbar>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>任务设置</span>
              <el-tag>{{ activeMode === 'image' ? '图片签到' : '普通签到' }}</el-tag>
            </div>
          </template>
          <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
            <el-form-item label="任务标题" prop="title">
              <el-input v-model="form.title" />
            </el-form-item>
            <el-form-item label="项目序号" prop="index">
              <el-input-number v-model="form.index" :min="1" style="width: 100%" />
            </el-form-item>
            <el-form-item label="执行时间" prop="times">
              <el-input v-model="timesText" placeholder="08:00:00,18:00:00" />
            </el-form-item>
            <el-form-item label="签到文本">
              <el-input v-model="form.text" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="图片路径" v-if="activeMode === 'image'" prop="pic_path">
              <el-input v-model="form.pic_path" placeholder="例如 1.jpg 或 D:\\images\\1.jpg" />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="form.enable">启用任务</el-checkbox>
              <el-checkbox v-model="form.use_location">需要位置</el-checkbox>
              <el-checkbox v-model="form.skip_weekends">周末跳过</el-checkbox>
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
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { Search, VideoPlay, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppState } from '../composables/useAppState'
import api from '../api'

const { state, refreshState, refreshLogs } = useAppState()

const selectedAccountIndex = ref(-1)
const activeMode = ref('normal')
const selectedActualIndex = ref(-1)
const projects = ref([])
const formRef = ref(null)

const form = reactive({
  title: '',
  index: 1,
  times: [],
  text: '',
  pic_path: '',
  enable: true,
  use_location: false,
  skip_weekends: false,
  mode: 'normal'
})

const timesText = computed({
  get: () => (form.times || []).join(', '),
  set: val => { form.times = val.split(',').map(s => s.trim()).filter(Boolean) }
})

const rules = computed(() => ({
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  index: [{ required: true, message: '请输入项目序号', trigger: 'blur' }],
  pic_path: [{ required: activeMode.value === 'image', message: '图片签到请填写图片路径', trigger: 'blur' }]
}))

const currentAccount = computed(() => state.value.accounts[selectedAccountIndex.value] || null)

const filteredTasks = computed(() => {
  if (!currentAccount.value) return []
  return (currentAccount.value.tasks || [])
    .map((task, actualIndex) => ({ task, actualIndex }))
    .filter(item => (item.task.mode || (item.task.pic_path ? 'image' : 'normal')) === activeMode.value)
})

function onAccountChange() {
  selectedActualIndex.value = -1
  projects.value = []
  createNew()
}

function onModeChange() {
  selectedActualIndex.value = -1
  createNew()
}

function createNew() {
  selectedActualIndex.value = -1
  form.title = ''
  form.index = 1
  form.times = []
  form.text = ''
  form.pic_path = ''
  form.enable = true
  form.use_location = false
  form.skip_weekends = false
  form.mode = activeMode.value
}

function onSelectTask(row) {
  if (!row) return
  selectedActualIndex.value = row.actualIndex
  const task = row.task
  activeMode.value = task.mode || (task.pic_path ? 'image' : 'normal')
  form.title = task.title
  form.index = task.index
  form.times = [...(task.times || [])]
  form.text = task.text
  form.pic_path = task.pic_path || ''
  form.enable = task.enable
  form.use_location = task.use_location
  form.skip_weekends = task.skip_weekends
  form.mode = activeMode.value
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
  form.mode = activeMode.value
  try {
    const account = state.value.accounts[selectedAccountIndex.value]
    const tasks = account?.tasks || []
    const existingTaskIndex = tasks.findIndex(t => t.index === form.index)
    
    if (existingTaskIndex >= 0) {
      await api.updateTask(selectedAccountIndex.value, existingTaskIndex, { ...form })
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
    const res = await api.runTask(selectedAccountIndex.value, selectedActualIndex.value)
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
.project-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  margin-bottom: 6px;
}
.project-item:hover {
  background: #eef4ff;
  border-color: #dbeafe;
}
</style>
