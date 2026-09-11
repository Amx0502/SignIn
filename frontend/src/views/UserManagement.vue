<template>
  <div class="users-page">
    <div class="page-heading">
      <div><h2>用户管理</h2><p>管理后台登录用户、角色、启用状态和账号有效期</p></div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table class="desktop-user-table" :data="users" v-loading="loading">
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
            <el-tag :type="isExpired(row) ? 'warning' : row.is_active ? 'success' : 'info'">
              {{ isExpired(row) ? '已到期' : row.is_active ? '已启用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="功能范围" min-width="150">
          <template #default="{ row }">
            <el-tag v-if="row.role === 'admin'" type="danger">全部功能</el-tag>
            <el-tag v-else-if="row.class_cube_only" type="primary">仅班级魔方</el-tag>
            <el-tag v-else type="info">普通用户</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="魔方账号额度" width="130">
          <template #default="{ row }">
            {{ row.role === 'admin' || row.class_cube_account_limit == null ? '不限' : row.class_cube_account_limit }}
          </template>
        </el-table-column>
        <el-table-column label="今日地址搜索" width="160">
          <template #default="{ row }">
            <span v-if="row.role === 'admin' || row.location_search_daily_limit == null">不限</span>
            <span v-else>
              已用 {{ row.location_search_used || 0 }} / {{ row.location_search_daily_limit }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="到期时间" min-width="180">
          <template #default="{ row }">
            <span :class="{ 'expired-time': isExpired(row) }">{{ formatExpiry(row) }}</span>
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
      <div class="mobile-user-list" v-loading="loading">
        <el-empty v-if="!users.length && !loading" description="暂无用户" />
        <article v-for="row in users" :key="row.id" class="mobile-user-card">
          <header>
            <div>
              <strong>{{ row.username }}</strong>
              <span>{{ row.role === 'admin' ? '管理员' : row.class_cube_only ? '仅班级魔方' : '普通用户' }}</span>
            </div>
            <el-tag :type="isExpired(row) ? 'warning' : row.is_active ? 'success' : 'info'" size="small">
              {{ isExpired(row) ? '已到期' : row.is_active ? '已启用' : '已禁用' }}
            </el-tag>
          </header>
          <dl>
            <div><dt>账号额度</dt><dd>{{ row.role === 'admin' || row.class_cube_account_limit == null ? '不限' : row.class_cube_account_limit }}</dd></div>
            <div><dt>地址搜索</dt><dd>{{ row.role === 'admin' || row.location_search_daily_limit == null ? '不限' : `${row.location_search_used || 0} / ${row.location_search_daily_limit}` }}</dd></div>
            <div class="mobile-user-card__wide"><dt>有效期</dt><dd :class="{ 'expired-time': isExpired(row) }">{{ formatExpiry(row) }}</dd></div>
            <div class="mobile-user-card__wide"><dt>最后登录</dt><dd>{{ formatTime(row.last_login) }}</dd></div>
          </dl>
          <footer>
            <el-button type="primary" plain @click="openEdit(row)">编辑</el-button>
            <el-button type="warning" plain @click="openReset(row)">重置密码</el-button>
            <el-button type="danger" plain @click="removeUser(row)">删除</el-button>
          </footer>
        </article>
      </div>
    </el-card>

    <el-dialog
      v-model="userDialog"
      :title="editingId ? '编辑用户' : '新增用户'"
      width="min(780px, 94vw)"
      class="user-editor-dialog"
      align-center
    >
      <el-form ref="userFormRef" :model="userForm" :rules="userRules" label-position="top" class="user-editor-form">
        <section class="user-form-section">
          <header class="user-form-section__head">
            <span>01</span>
            <div><strong>账号信息</strong><small>设置登录身份、状态和有效期</small></div>
          </header>
          <div class="user-form-grid">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="userForm.username" />
            </el-form-item>
            <el-form-item label="角色" prop="role">
              <el-select v-model="userForm.role" style="width: 100%">
                <el-option label="管理员" value="admin" />
                <el-option label="普通用户" value="user" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="!editingId" label="初始密码" prop="password">
              <el-input v-model="userForm.password" type="password" show-password />
            </el-form-item>
            <el-form-item label="账号状态" class="status-form-item">
              <div class="status-switch-card">
                <span>{{ userForm.is_active ? '允许登录并执行任务' : '禁止登录并停止使用' }}</span>
                <el-switch v-model="userForm.is_active" active-text="启用" inactive-text="禁用" />
              </div>
            </el-form-item>
            <el-form-item v-if="userForm.role === 'user'" label="账号到期时间" class="user-form-grid__full">
              <el-date-picker
                v-model="userForm.expires_at"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                format="YYYY-MM-DD HH:mm:ss"
                placeholder="留空表示永不过期"
                :disabled-date="disablePastDate"
                clearable
                style="width: 100%"
              />
              <div class="field-help">到期后账号会自动变为禁用，已登录会话也会失效；清空表示永不过期。</div>
            </el-form-item>
            <div v-else class="admin-expiry-note user-form-grid__full">管理员账号不设置到期时间，避免系统失去可用管理员。</div>
          </div>
        </section>

        <section v-if="userForm.role === 'user'" class="user-form-section">
          <header class="user-form-section__head">
            <span>02</span>
            <div><strong>功能与额度</strong><small>控制菜单范围、账号数量和地址搜索次数</small></div>
          </header>
          <div class="policy-grid">
            <div class="policy-card policy-card--wide">
              <div class="policy-card__title"><strong>班级魔方单用户</strong><small>仅开放账号、任务和运行记录</small></div>
              <el-switch
                v-model="userForm.class_cube_only"
                active-text="仅显示核心菜单"
                inactive-text="使用自定义菜单权限"
                @change="handleClassCubeOnlyChange"
              />
              <p>开启后隐藏“小小签到”及全部子菜单，同时隐藏班级魔方的“系统概览”和“魔方日志”。</p>
            </div>

            <div class="policy-card">
              <div class="policy-card__title"><strong>班级魔方账号额度</strong><small>限制该用户可绑定的账号数量</small></div>
              <div class="quota-row">
                <el-switch v-model="accountQuotaUnlimited" active-text="不限额度" />
                <el-input-number
                  v-if="!accountQuotaUnlimited"
                  v-model="userForm.class_cube_account_limit"
                  :min="0"
                  :max="999"
                  controls-position="right"
                />
              </div>
            </div>

            <div class="policy-card">
              <div class="policy-card__title"><strong>每日地址搜索额度</strong><small>按服务器自然日自动重新计数</small></div>
              <div class="quota-row">
                <el-switch v-model="locationQuotaUnlimited" active-text="不限次数" />
                <el-input-number
                  v-if="!locationQuotaUnlimited"
                  v-model="userForm.location_search_daily_limit"
                  :min="0"
                  :max="100000"
                  controls-position="right"
                />
              </div>
              <p>例如设置 100 表示每天最多搜索 100 次；0 表示禁止搜索。</p>
            </div>

            <div v-if="!editingId && userForm.class_cube_only" class="policy-card policy-card--wide">
              <div class="policy-card__title"><strong>初始班级魔方账号</strong><small>可不选择，用户之后自行扫码添加</small></div>
              <el-select
                v-model="userForm.initial_class_cube_account_id"
                clearable
                filterable
                placeholder="请选择现有班级魔方账号"
                style="width: 100%"
              >
                <el-option
                  v-for="account in accountPool"
                  :key="account.id"
                  :label="accountLabel(account)"
                  :value="account.id"
                />
              </el-select>
              <p>选择后绑定现有账号作为该用户的第一个默认账号，不会复制 Cookie。</p>
            </div>
          </div>
        </section>
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
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createUserApi, deleteUserApi, getUsersApi,
  resetUserPasswordApi, updateUserApi
} from '../api'
import classCubeApi from '../api/classCube.js'

const users = ref([])
const accountPool = ref([])
const loading = ref(false)
const saving = ref(false)
const userDialog = ref(false)
const resetDialog = ref(false)
const editingId = ref(null)
const resetUserId = ref(null)
const accountQuotaUnlimited = ref(true)
const locationQuotaUnlimited = ref(true)
const userFormRef = ref()
const resetFormRef = ref()
const userForm = reactive({
  username: '', password: '', role: 'user', is_active: true,
  class_cube_only: false, class_cube_account_limit: 1,
  location_search_daily_limit: 100,
  initial_class_cube_account_id: null,
  expires_at: null,
})
const resetForm = reactive({ new_password: '' })
const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }, { min: 3, message: '至少 3 个字符', trigger: 'blur' }],
  password: [{ required: true, message: '请输入初始密码', trigger: 'blur' }, { min: 6, message: '密码至少 6 位', trigger: 'blur' }]
}
const resetRules = { new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }, { min: 6, message: '密码至少 6 位', trigger: 'blur' }] }

function formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN') : '从未登录' }
function isExpired(row) {
  return Boolean(row.is_expired || (row.expires_at && new Date(row.expires_at) <= new Date()))
}
function formatExpiry(row) {
  if (!row.expires_at) return '永不过期'
  return new Date(row.expires_at).toLocaleString('zh-CN')
}
function formExpiryValue(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : null
}
function disablePastDate(date) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date.getTime() < today.getTime()
}
async function loadUsers() {
  loading.value = true
  try { users.value = (await getUsersApi()).data } catch (error) { ElMessage.error(error.message) }
  finally { loading.value = false }
}
async function loadAccountPool() {
  try { accountPool.value = (await classCubeApi.listAccounts()).data || [] }
  catch { accountPool.value = [] }
}
function accountLabel(account) {
  const name = account.name || account.remote_user_name || `账号 ${account.id}`
  return account.remote_uid ? `${name} · UID ${account.remote_uid}` : `${name} · 待确认 UID`
}
function openCreate() {
  editingId.value = null
  accountQuotaUnlimited.value = true
  locationQuotaUnlimited.value = true
  Object.assign(userForm, {
    username: '', password: '', role: 'user', is_active: true,
    class_cube_only: false, class_cube_account_limit: 1,
    location_search_daily_limit: 100,
    initial_class_cube_account_id: null,
    expires_at: null,
  })
  userDialog.value = true
}
function openEdit(row) {
  editingId.value = row.id
  accountQuotaUnlimited.value = row.class_cube_account_limit == null
  locationQuotaUnlimited.value = row.location_search_daily_limit == null
  Object.assign(userForm, {
    username: row.username, password: '', role: row.role, is_active: row.is_active,
    class_cube_only: Boolean(row.class_cube_only),
    class_cube_account_limit: row.class_cube_account_limit ?? 1,
    location_search_daily_limit: row.location_search_daily_limit ?? 100,
    initial_class_cube_account_id: null,
    expires_at: row.role === 'user' ? formExpiryValue(row.expires_at) : null,
  })
  userDialog.value = true
}
function handleClassCubeOnlyChange(enabled) {
  if (enabled && accountQuotaUnlimited.value) {
    accountQuotaUnlimited.value = false
    userForm.class_cube_account_limit = 1
  }
  if (!enabled) userForm.initial_class_cube_account_id = null
}
async function saveUser() {
  await userFormRef.value.validate()
  if (
    userForm.role === 'user'
    && userForm.is_active
    && userForm.expires_at
    && new Date(userForm.expires_at) <= new Date()
  ) {
    ElMessage.warning('启用用户的到期时间必须晚于当前时间')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateUserApi(editingId.value, {
        username: userForm.username, role: userForm.role, is_active: userForm.is_active,
        class_cube_only: userForm.role === 'user' && userForm.class_cube_only,
        class_cube_account_limit: userForm.role === 'user' && !accountQuotaUnlimited.value
          ? userForm.class_cube_account_limit : null,
        location_search_daily_limit: userForm.role === 'user' && !locationQuotaUnlimited.value
          ? userForm.location_search_daily_limit : null,
        expires_at: userForm.role === 'user' ? userForm.expires_at : null,
      })
    } else {
      await createUserApi({
        ...userForm,
        class_cube_only: userForm.role === 'user' && userForm.class_cube_only,
        class_cube_account_limit: userForm.role === 'user' && !accountQuotaUnlimited.value
          ? userForm.class_cube_account_limit : null,
        location_search_daily_limit: userForm.role === 'user' && !locationQuotaUnlimited.value
          ? userForm.location_search_daily_limit : null,
        initial_class_cube_account_id: userForm.class_cube_only
          ? userForm.initial_class_cube_account_id : null,
        expires_at: userForm.role === 'user' ? userForm.expires_at : null,
      })
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
let userRefreshTimer = null
onMounted(() => {
  Promise.all([loadUsers(), loadAccountPool()])
  userRefreshTimer = window.setInterval(loadUsers, 30_000)
})
onBeforeUnmount(() => {
  if (userRefreshTimer) window.clearInterval(userRefreshTimer)
})
</script>

<style scoped>
.users-page { display: grid; gap: 20px; }
.page-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.page-heading h2 { margin: 0 0 6px; color: #0f172a; }
.page-heading p { margin: 0; color: #64748b; }
.table-card { border-radius: 18px; }
.mobile-user-list { display: none; }
.field-help { width: 100%; margin-top: 6px; color: #64748b; font-size: 12px; line-height: 1.5; }
.quota-row { display: flex; align-items: center; gap: 16px; width: 100%; }
.user-editor-form {
  display: grid;
  gap: 14px;
  max-height: min(72vh, 720px);
  padding: 2px 3px 4px;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-gutter: stable;
}
.user-form-section {
  min-width: 0;
  padding: 16px 16px 4px;
  border: 1px solid #dbeafe;
  border-radius: 16px;
  background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
}
.user-form-section__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 11px;
  border-bottom: 1px solid #e5edf8;
}
.user-form-section__head > span {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 11px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  box-shadow: 0 7px 16px rgb(37 99 235 / 20%);
  color: #fff;
  font-size: 11px;
  font-weight: 800;
}
.user-form-section__head strong,
.user-form-section__head small,
.policy-card__title strong,
.policy-card__title small {
  display: block;
}
.user-form-section__head strong { color: #172033; font-size: 15px; line-height: 1.35; }
.user-form-section__head small { margin-top: 2px; color: #8492a6; font-size: 11px; }
.user-form-grid,
.policy-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}
.user-form-grid__full,
.policy-card--wide { grid-column: 1 / -1; }
.status-switch-card {
  display: flex;
  width: 100%;
  min-height: 32px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.status-switch-card > span { color: #64748b; font-size: 12px; }
.policy-grid { gap: 12px; padding-bottom: 12px; }
.policy-card {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 10px;
  padding: 13px;
  border: 1px solid #dbeafe;
  border-radius: 13px;
  background: rgb(248 251 255 / 88%);
}
.policy-card__title strong { color: #24324a; font-size: 13px; line-height: 1.4; }
.policy-card__title small { margin-top: 2px; color: #8a98aa; font-size: 11px; line-height: 1.45; }
.policy-card p { margin: 0; color: #64748b; font-size: 11px; line-height: 1.5; }
.policy-card .quota-row { justify-content: space-between; }
.policy-card :deep(.el-input-number) { width: 140px; }
.user-form-section :deep(.el-form-item) { margin-bottom: 14px; }
.user-form-section :deep(.el-form-item__content) { min-width: 0; }
.expired-time { color: #d97706; }
.admin-expiry-note {
  margin: -2px 0 18px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f5f7fa;
  color: #7a8798;
  font-size: 12px;
  line-height: 1.5;
}
@media (max-width: 640px) {
  .desktop-user-table { display: none; }
  .mobile-user-list { display: grid; gap: 12px; }
  .mobile-user-card { overflow: hidden; border: 1px solid #e1e9f4; border-radius: 14px; background: #fff; }
  .mobile-user-card header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 14px; background: #f8fbff; }
  .mobile-user-card header strong, .mobile-user-card header span { display: block; }
  .mobile-user-card header strong { color: #172033; font-size: 15px; }
  .mobile-user-card header span { margin-top: 3px; color: #718096; font-size: 12px; }
  .mobile-user-card dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; padding: 14px; }
  .mobile-user-card dl div { min-width: 0; }
  .mobile-user-card dt { color: #8a98aa; font-size: 11px; }
  .mobile-user-card dd { margin: 3px 0 0; overflow-wrap: anywhere; color: #334155; font-size: 13px; }
  .mobile-user-card__wide { grid-column: 1 / -1; }
  .mobile-user-card footer { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; padding: 0 14px 14px; }
  .mobile-user-card footer .el-button { width: 100%; margin: 0; padding-inline: 6px; }
  .page-heading { align-items: flex-start; flex-direction: column; }
  .page-heading .el-button { width: 100%; }
  .user-editor-form { max-height: 76vh; }
  .user-form-section { padding: 14px 12px 3px; }
  .user-form-grid,
  .policy-grid { grid-template-columns: minmax(0, 1fr); }
  .user-form-grid__full,
  .policy-card--wide { grid-column: auto; }
  .status-switch-card,
  .quota-row {
    align-items: flex-start;
    flex-direction: column;
  }
  .policy-card :deep(.el-input-number) { width: 100%; }
}
</style>
