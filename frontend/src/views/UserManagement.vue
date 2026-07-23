<template>
  <div class="users-page">
    <div class="page-heading">
      <div><h2>用户管理</h2><p>管理后台登录用户、角色和启用状态</p></div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="users" v-loading="loading">
        <el-table-column prop="username" label="用户名" min-width="150" />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
              {{ row.role === 'admin' ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '已启用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login" label="最后登录" min-width="180">
          <template #default="{ row }">{{ formatTime(row.last_login) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="warning" @click="openReset(row)">重置密码</el-button>
            <el-button link type="danger" @click="removeUser(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="userDialog" :title="editingId ? '编辑用户' : '新增用户'" width="460px">
      <el-form ref="userFormRef" :model="userForm" :rules="userRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" />
        </el-form-item>
        <el-form-item v-if="!editingId" label="初始密码" prop="password">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="userForm.role" style="width: 100%">
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="userForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetDialog" title="重置密码" width="420px">
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-position="top">
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="resetForm.new_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="resetPassword">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createUserApi, deleteUserApi, getUsersApi,
  resetUserPasswordApi, updateUserApi
} from '../api'

const users = ref([])
const loading = ref(false)
const saving = ref(false)
const userDialog = ref(false)
const resetDialog = ref(false)
const editingId = ref(null)
const resetUserId = ref(null)
const userFormRef = ref()
const resetFormRef = ref()
const userForm = reactive({ username: '', password: '', role: 'user', is_active: true })
const resetForm = reactive({ new_password: '' })
const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }, { min: 3, message: '至少 3 个字符', trigger: 'blur' }],
  password: [{ required: true, message: '请输入初始密码', trigger: 'blur' }, { min: 6, message: '密码至少 6 位', trigger: 'blur' }]
}
const resetRules = { new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }, { min: 6, message: '密码至少 6 位', trigger: 'blur' }] }

function formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN') : '从未登录' }
async function loadUsers() {
  loading.value = true
  try { users.value = (await getUsersApi()).data } catch (error) { ElMessage.error(error.message) }
  finally { loading.value = false }
}
function openCreate() {
  editingId.value = null
  Object.assign(userForm, { username: '', password: '', role: 'user', is_active: true })
  userDialog.value = true
}
function openEdit(row) {
  editingId.value = row.id
  Object.assign(userForm, { username: row.username, password: '', role: row.role, is_active: row.is_active })
  userDialog.value = true
}
async function saveUser() {
  await userFormRef.value.validate()
  saving.value = true
  try {
    if (editingId.value) {
      await updateUserApi(editingId.value, {
        username: userForm.username, role: userForm.role, is_active: userForm.is_active
      })
    } else {
      await createUserApi({ ...userForm })
    }
    ElMessage.success('保存成功')
    userDialog.value = false
    await loadUsers()
  } catch (error) { ElMessage.error(error.message) } finally { saving.value = false }
}
function openReset(row) {
  resetUserId.value = row.id
  resetForm.new_password = ''
  resetDialog.value = true
}
async function resetPassword() {
  await resetFormRef.value.validate()
  saving.value = true
  try {
    await resetUserPasswordApi(resetUserId.value, { new_password: resetForm.new_password })
    ElMessage.success('密码已重置')
    resetDialog.value = false
    await loadUsers()
  } catch (error) { ElMessage.error(error.message) } finally { saving.value = false }
}
async function removeUser(row) {
  try {
    await ElMessageBox.confirm(`确认删除用户“${row.username}”？`, '删除用户', { type: 'warning' })
    await deleteUserApi(row.id)
    ElMessage.success('用户已删除')
    await loadUsers()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.message)
  }
}
onMounted(loadUsers)
</script>

<style scoped>
.users-page { display: grid; gap: 20px; }
.page-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.page-heading h2 { margin: 0 0 6px; color: #0f172a; }
.page-heading p { margin: 0; color: #64748b; }
.table-card { border-radius: 18px; }
@media (max-width: 640px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
}
</style>
