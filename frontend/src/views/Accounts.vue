<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>账号列表</span>
              <el-button type="primary" :icon="Plus" size="small" @click="createNew">新增账号</el-button>
            </div>
          </template>
          <el-table
            :data="state.accounts"
            highlight-current-row
            @current-change="onSelectAccount"
            style="width: 100%"
            max-height="560"
          >
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="mobile" label="手机号" min-width="120" />
            <el-table-column label="任务数" width="90">
              <template #default="scope">{{ (scope.row.tasks || []).length }}</template>
            </el-table-column>
            <el-table-column label="Token" min-width="180">
              <template #default="scope">
                <el-tooltip :content="scope.row.token || '无'" placement="top">
                  <span>{{ scope.row.token ? scope.row.token.slice(0, 24) + '...' : '-' }}</span>
                </el-tooltip>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ selectedIndex >= 0 ? '编辑账号' : '新增账号' }}</span>
            </div>
          </template>
          <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
            <el-form-item label="账号名称" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
            <el-form-item label="手机号" prop="mobile">
              <el-input v-model="form.mobile" />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="form.password" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveAccount">{{ selectedIndex >= 0 ? '保存账号' : '新增账号' }}</el-button>
              <el-button @click="createNew">重置</el-button>
            </el-form-item>
            <el-form-item v-if="selectedIndex >= 0">
              <el-space wrap>
                <el-button type="success" :icon="Key" @click="loginAccount">登录获取 Token</el-button>
                <el-button type="warning" :icon="Refresh" @click="refreshToken">刷新 Token</el-button>
                <el-button :icon="VideoPlay" @click="runAccountTasks">执行当前账号任务</el-button>
                <el-button type="danger" :icon="Delete" @click="deleteAccount">删除账号</el-button>
              </el-space>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { Plus, Key, Refresh, VideoPlay, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppState } from '../composables/useAppState'
import api from '../api'

const { state, refreshState, refreshLogs } = useAppState()

const formRef = ref(null)
const selectedIndex = ref(-1)
const form = reactive({
  name: '',
  mobile: '',
  password: '',
  token: ''
})

const rules = {
  name: [{ required: true, message: '请输入账号名称', trigger: 'blur' }],
  mobile: [{ required: true, message: '请输入手机号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

function createNew() {
  selectedIndex.value = -1
  form.name = ''
  form.mobile = ''
  form.password = ''
  form.token = ''
}

function onSelectAccount(row) {
  if (!row) return
  const idx = state.value.accounts.indexOf(row)
  selectedIndex.value = idx
  form.name = row.name
  form.mobile = row.mobile
  form.password = row.password
  form.token = row.token || ''
}

async function saveAccount() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    if (selectedIndex.value >= 0) {
      await api.updateAccount(selectedIndex.value, { ...form })
      ElMessage.success('账号已更新')
    } else {
      await api.addAccount({ name: form.name, mobile: form.mobile, password: form.password, token: '' })
      await refreshState()
      const newIndex = state.value.accounts.length - 1
      if (newIndex >= 0) {
        await api.loginAccount(newIndex)
        ElMessage.success('账号已新增并自动登录获取 Token')
      } else {
        ElMessage.success('账号已新增')
      }
      createNew()
    }
    await refreshState()
    await refreshLogs()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function loginAccount() {
  try {
    const res = await api.loginAccount(selectedIndex.value)
    form.token = res.data.token
    ElMessage.success('登录成功')
    await refreshState()
    await refreshLogs()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function refreshToken() {
  try {
    const res = await api.refreshAccountToken(selectedIndex.value)
    form.token = res.data.token
    ElMessage.success('Token 已刷新')
    await refreshState()
    await refreshLogs()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function runAccountTasks() {
  try {
    await api.runAccountTasks(selectedIndex.value)
    ElMessage.success('已加入执行队列')
    await refreshLogs()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function deleteAccount() {
  try {
    await ElMessageBox.confirm('确认删除当前账号吗？', '提示', { type: 'warning' })
    await api.deleteAccount(selectedIndex.value)
    createNew()
    await refreshState()
    await refreshLogs()
    ElMessage.success('账号已删除')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message)
  }
}
</script>
