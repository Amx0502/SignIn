<template>
  <div class="users-page">
    <div class="page-heading">
      <div><h2>用户管理</h2><p>管理后台登录用户、角色、启用状态和账号有效期</p></div>
      <div class="page-heading__actions">
        <el-button plain @click="openMemberCreate()">一键创建用户</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <div class="user-filters">
        <el-input
          v-model="userKeyword"
          clearable
          :prefix-icon="Search"
          placeholder="搜索用户名"
          aria-label="搜索用户名"
        />
        <el-select v-model="roleFilter" clearable placeholder="全部角色">
          <el-option label="管理员" value="admin" />
          <el-option label="普通用户" value="user" />
        </el-select>
        <el-select v-model="cardFilter" clearable placeholder="全部会员卡">
          <el-option label="无会员卡" value="none" />
          <el-option label="次卡" value="single" />
          <el-option label="月卡" value="monthly" />
        </el-select>
        <el-select v-model="statusFilter" clearable placeholder="全部状态">
          <el-option label="已启用" value="active" />
          <el-option label="已禁用" value="disabled" />
          <el-option label="已过期" value="expired" />
        </el-select>
        <el-select v-model="scopeFilter" clearable placeholder="全部功能范围">
          <el-option label="仅小小签到" value="xxqd" />
          <el-option label="仅班级魔方" value="class_cube" />
          <el-option label="全部平台" value="all" />
        </el-select>
        <el-button @click="resetUserFilters">重置</el-button>
      </div>
      <div class="user-filter-summary">
        显示 {{ filteredUsers.length }} / {{ users.length }} 个用户
      </div>

      <el-table class="desktop-user-table" :data="filteredUsers" v-loading="loading">
        <el-table-column prop="username" label="用户名" min-width="150" />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
              {{ row.role === 'admin' ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="会员卡" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.card_type" :type="cardTagType(row)" size="small">
              {{ cardTypeLabel(row.card_type) }}
            </el-tag>
            <span v-else class="muted-text">无</span>
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
            <el-tag v-else-if="row.platform_scope === 'xxqd'" type="success">仅小小签到</el-tag>
            <el-tag v-else-if="row.platform_scope === 'class_cube'" type="primary">仅班级魔方</el-tag>
            <el-tag v-else type="info">普通用户</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="平台账号额度" width="130">
          <template #default="{ row }">
            {{ row.role === 'admin'
              ? '不限'
              : row.platform_scope === 'xxqd'
                ? (row.xxqd_account_limit == null ? '不限' : row.xxqd_account_limit)
                : (row.class_cube_account_limit == null ? '不限' : row.class_cube_account_limit) }}
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
            <template v-if="!isExpired(row)">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="warning" @click="openReset(row)">重置密码</el-button>
              <el-button link type="danger" @click="removeUser(row)">删除</el-button>
            </template>
            <span v-else class="muted-text">已过期，只读</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="mobile-user-list" v-loading="loading">
        <el-empty v-if="!users.length && !loading" description="暂无用户" />
        <el-empty v-else-if="!filteredUsers.length && !loading" description="没有符合条件的用户" />
        <article v-for="row in filteredUsers" :key="row.id" class="mobile-user-card">
          <header>
            <div>
              <strong>{{ row.username }}</strong>
              <span>{{ row.role === 'admin' ? '管理员' : row.platform_scope === 'xxqd' ? '仅小小签到' : row.platform_scope === 'class_cube' ? '仅班级魔方' : '普通用户' }}</span>
            </div>
            <el-tag :type="isExpired(row) ? 'warning' : row.is_active ? 'success' : 'info'" size="small">
              {{ isExpired(row) ? '已到期' : row.is_active ? '已启用' : '已禁用' }}
            </el-tag>
          </header>
          <dl>
            <div><dt>账号额度</dt><dd>{{ row.role === 'admin' ? '不限' : row.platform_scope === 'xxqd' ? (row.xxqd_account_limit == null ? '不限' : row.xxqd_account_limit) : (row.class_cube_account_limit == null ? '不限' : row.class_cube_account_limit) }}</dd></div>
            <div><dt>地址搜索</dt><dd>{{ row.role === 'admin' || row.location_search_daily_limit == null ? '不限' : `${row.location_search_used || 0} / ${row.location_search_daily_limit}` }}</dd></div>
            <div><dt>会员卡</dt><dd>{{ row.card_type ? cardTypeLabel(row.card_type) : '无' }}</dd></div>
            <div class="mobile-user-card__wide"><dt>有效期</dt><dd :class="{ 'expired-time': isExpired(row) }">{{ formatExpiry(row) }}</dd></div>
            <div class="mobile-user-card__wide"><dt>最后登录</dt><dd>{{ formatTime(row.last_login) }}</dd></div>
          </dl>
          <footer>
            <template v-if="!isExpired(row)">
              <el-button type="primary" plain @click="openEdit(row)">编辑</el-button>
              <el-button type="warning" plain @click="openReset(row)">重置密码</el-button>
              <el-button type="danger" plain @click="removeUser(row)">删除</el-button>
            </template>
            <span v-else class="muted-text">已过期，只读</span>
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
            <el-form-item v-if="userForm.role === 'user'" label="所属平台">
              <el-select
                v-model="userForm.platform_scope"
                style="width: 100%"
                @change="handlePlatformScopeChange"
              >
                <el-option label="小小签到" value="xxqd" />
                <el-option label="班级魔方" value="class_cube" />
                <el-option label="全部平台（仅管理员可配置）" value="all" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="userForm.role === 'user'" label="会员卡类型">
              <el-select
                v-model="userForm.card_type"
                clearable
                placeholder="不分配会员卡"
                style="width: 100%"
                @change="handleCardTypeChange"
              >
                <el-option label="次卡（可设置多次签到）" value="single" />
                <el-option label="月卡（首次登录起 30 天）" value="monthly" />
              </el-select>
            </el-form-item>
            <el-form-item
              v-if="userForm.role === 'user' && userForm.card_type === 'single'"
              label="可签到次数"
            >
              <div class="minute-stepper">
                <el-input-number
                  v-model="userForm.card_total_uses"
                  :min="1"
                  :max="999"
                  :precision="0"
                />
                <em>次</em>
              </div>
              <div class="field-help">达到总次数并签到成功后，账号按下方延迟时间删除。</div>
            </el-form-item>
            <el-form-item
              v-if="userForm.role === 'user' && userForm.card_type === 'single'"
              label="签到后删除延迟"
            >
              <div class="minute-stepper">
                <el-input-number
                  v-model="userForm.card_delete_delay_seconds"
                  :min="0"
                  :max="86400"
                  :precision="0"
                />
                <em>秒</em>
              </div>
              <div class="field-help">默认 30 秒；设为 0 表示立即删除。</div>
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
            <el-form-item v-if="userForm.role === 'user' && !userForm.card_type" label="账号到期时间" class="user-form-grid__full">
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
            <div v-if="userForm.role === 'user' && userForm.card_type" class="admin-expiry-note user-form-grid__full">
              {{ userForm.card_type === 'monthly'
                ? '月卡在用户首次成功登录时激活，到期时间自动设为激活后 30 天。'
                : `次卡可成功签到 ${userForm.card_total_uses ?? 1} 次，最后一次核销后 ${userForm.card_delete_delay_seconds ?? 30} 秒删除账号。` }}
            </div>
            <div v-else-if="userForm.role !== 'user'" class="admin-expiry-note user-form-grid__full">管理员账号不设置到期时间，避免系统失去可用管理员。</div>
          </div>
        </section>

        <section v-if="userForm.role === 'user'" class="user-form-section">
          <header class="user-form-section__head">
            <span>02</span>
            <div><strong>功能与额度</strong><small>控制菜单范围、账号数量和地址搜索次数</small></div>
          </header>
          <div class="policy-grid">
            <div v-if="userForm.platform_scope === 'class_cube'" class="policy-card policy-card--wide">
              <div class="policy-card__title"><strong>班级魔方单用户</strong><small>仅开放账号、任务和运行记录</small></div>
              <el-switch
                v-model="userForm.class_cube_only"
                active-text="仅显示核心菜单"
                inactive-text="使用自定义菜单权限"
                @change="handleClassCubeOnlyChange"
              />
              <p>开启后隐藏“小小签到”及全部子菜单，同时隐藏班级魔方的“系统概览”和“魔方日志”。</p>
            </div>

            <div v-else-if="userForm.platform_scope === 'xxqd'" class="policy-card policy-card--wide">
              <div class="policy-card__title"><strong>小小签到单平台用户</strong><small>仅开放小小签到账号、任务和日志功能</small></div>
              <p>该用户不会看到班级魔方菜单，也不能访问班级魔方接口。</p>
            </div>

            <div v-else class="policy-card policy-card--wide">
              <div class="policy-card__title"><strong>全部平台用户</strong><small>该配置通常只用于管理员</small></div>
              <p>用户可以使用其菜单权限允许的全部平台功能。</p>
            </div>

            <div v-if="userForm.platform_scope === 'class_cube'" class="policy-card">
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

            <div v-if="userForm.platform_scope === 'xxqd'" class="policy-card">
              <div class="policy-card__title"><strong>小小签到账号额度</strong><small>限制该用户可绑定的账号数量</small></div>
              <div class="quota-row">
                <el-switch v-model="xxqdAccountQuotaUnlimited" active-text="不限额度" />
                <el-input-number
                  v-if="!xxqdAccountQuotaUnlimited"
                  v-model="userForm.xxqd_account_limit"
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

    <el-dialog
      v-model="memberDialog"
      :title="memberForm.platform_scope === 'xxqd' ? '一键创建小小签到用户' : '一键创建班级魔方用户'"
      width="480px"
      align-center
    >
      <div class="member-create-panel">
        <div class="member-platform-field">
          <span>所属平台</span>
          <el-radio-group v-model="memberForm.platform_scope">
            <el-radio-button value="xxqd">小小签到</el-radio-button>
            <el-radio-button value="class_cube">班级魔方</el-radio-button>
          </el-radio-group>
        </div>
        <div class="member-type-options">
          <button
            v-for="option in memberTypeOptions"
            :key="option.value"
            type="button"
            class="member-type-option"
            :class="{ active: memberForm.card_type === option.value }"
            @click="memberForm.card_type = option.value"
          >
            <strong>{{ option.label }}</strong>
            <small>{{ option.description }}</small>
          </button>
        </div>
        <label v-if="memberForm.card_type === 'single'" class="member-delay-field">
          <span>可签到次数</span>
          <div class="minute-stepper">
            <el-input-number
              v-model="memberForm.card_total_uses"
              :min="1"
              :max="999"
              :precision="0"
            />
            <em>次</em>
          </div>
          <small>默认 1 次；达到总次数后按下方延迟时间删除</small>
        </label>
        <label v-if="memberForm.card_type === 'single'" class="member-delay-field">
          <span>签到成功后延迟删除</span>
          <div class="minute-stepper">
            <el-input-number
              v-model="memberForm.card_delete_delay_seconds"
              :min="0"
              :max="86400"
              :precision="0"
            />
            <em>秒</em>
          </div>
          <small>默认 30 秒；设为 0 表示立即删除</small>
        </label>
        <p class="field-help">系统将自动生成随机用户名和密码，并仅开放{{ memberForm.platform_scope === 'xxqd' ? '小小签到' : '班级魔方' }}核心功能。</p>
      </div>
      <template #footer>
        <el-button @click="memberDialog = false">取消</el-button>
        <el-button type="primary" :loading="memberCreating" @click="createMember">创建并生成凭据</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="memberResultDialog" title="创建成功" width="460px" align-center>
      <div v-if="memberCredentials" class="member-credentials">
        <div class="member-credentials__row">
          <span>用户名</span>
          <strong>{{ memberCredentials.username }}</strong>
          <el-button link type="primary" @click="copyCredential(memberCredentials.username)">复制</el-button>
        </div>
        <div class="member-credentials__row">
          <span>初始密码</span>
          <strong>{{ memberCredentials.password }}</strong>
          <el-button link type="primary" @click="copyCredential(memberCredentials.password)">复制</el-button>
        </div>
        <p class="field-help">密码仅在本次创建后展示，请立即交付给用户。</p>
      </div>
      <template #footer>
        <el-button type="primary" @click="memberResultDialog = false">完成</el-button>
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createClassCubeMemberApi, createUserApi, createXxqdMemberApi,
  deleteUserApi, getUsersApi,
  resetUserPasswordApi, updateUserApi
} from '../api'
import classCubeApi from '../api/classCube.js'

const users = ref([])
const userKeyword = ref('')
const roleFilter = ref('')
const cardFilter = ref('')
const statusFilter = ref('')
const scopeFilter = ref('')
const accountPool = ref([])
const loading = ref(false)
const saving = ref(false)
const userDialog = ref(false)
const memberDialog = ref(false)
const memberResultDialog = ref(false)
const memberCreating = ref(false)
const memberCredentials = ref(null)
const resetDialog = ref(false)
const editingId = ref(null)
const resetUserId = ref(null)
const accountQuotaUnlimited = ref(true)
const xxqdAccountQuotaUnlimited = ref(false)
const locationQuotaUnlimited = ref(true)
const userFormRef = ref()
const resetFormRef = ref()
const userForm = reactive({
  username: '', password: '', role: 'user', is_active: true,
  platform_scope: 'all',
  class_cube_only: false, class_cube_account_limit: 1,
  xxqd_account_limit: 1,
  location_search_daily_limit: 100,
  initial_class_cube_account_id: null,
  expires_at: null,
  card_type: null,
  card_total_uses: 1,
  card_delete_delay_seconds: 30,
})
const memberForm = reactive({
  platform_scope: 'class_cube',
  card_type: 'single',
  card_total_uses: 1,
  card_delete_delay_seconds: 30,
})
const memberTypeOptions = [
  { value: 'single', label: '次卡', description: '成功签到一次后核销，账号自动失效并删除' },
  { value: 'monthly', label: '月卡', description: '首次登录激活，自激活起 30 天内有效' },
]

const filteredUsers = computed(() => {
  const keyword = userKeyword.value.trim().toLowerCase()
  return users.value.filter((row) => {
    if (keyword && !String(row.username || '').toLowerCase().includes(keyword)) {
      return false
    }
    if (roleFilter.value && row.role !== roleFilter.value) return false
    if (cardFilter.value === 'none' && row.card_type) return false
    if (
      cardFilter.value
      && cardFilter.value !== 'none'
      && row.card_type !== cardFilter.value
    ) return false
    const expired = isExpired(row)
    const currentStatus = expired
      ? 'expired'
      : row.is_active ? 'active' : 'disabled'
    if (statusFilter.value && currentStatus !== statusFilter.value) return false
    const scope = row.platform_scope || (row.class_cube_only ? 'class_cube' : 'all')
    if (scopeFilter.value && scope !== scopeFilter.value) return false
    return true
  })
})
const resetForm = reactive({ new_password: '' })
const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }, { min: 3, message: '至少 3 个字符', trigger: 'blur' }],
  password: [{ required: true, message: '请输入初始密码', trigger: 'blur' }, { min: 6, message: '密码至少 6 位', trigger: 'blur' }]
}
const resetRules = { new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }, { min: 6, message: '密码至少 6 位', trigger: 'blur' }] }

function formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN') : '从未登录' }
function resetUserFilters() {
  userKeyword.value = ''
  roleFilter.value = ''
  cardFilter.value = ''
  statusFilter.value = ''
  scopeFilter.value = ''
}
function cardTypeLabel(value) {
  return { single: '次卡', monthly: '月卡' }[value] || '无'
}
function cardTagType(row) {
  if (row.card_status === 'expired' || row.card_status === 'used') return 'warning'
  if (row.card_status === 'pending') return 'info'
  return row.card_type === 'monthly' ? 'success' : 'primary'
}
function isExpired(row) {
  return Boolean(row.is_expired || (row.expires_at && new Date(row.expires_at) <= new Date()))
}
function formatExpiry(row) {
  if (row.card_type === 'monthly' && !row.card_activated_at) return '首次登录后激活'
  if (row.card_type === 'single') {
    if (row.card_delete_due_at) {
      return `${formatTime(row.card_delete_due_at)} 删除`
    }
    return `已签到 ${row.card_used_count ?? 0}/${row.card_total_uses ?? 1} 次，剩余 ${row.card_remaining_uses ?? 1} 次`
  }
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
function openMemberCreate(platformScope = 'class_cube') {
  memberForm.platform_scope = platformScope
  memberForm.card_type = 'single'
  memberForm.card_total_uses = 1
  memberForm.card_delete_delay_seconds = 30
  memberCredentials.value = null
  memberDialog.value = true
}
async function createMember() {
  memberCreating.value = true
  try {
    const api = memberForm.platform_scope === 'xxqd'
      ? createXxqdMemberApi : createClassCubeMemberApi
    const response = await api({
      card_type: memberForm.card_type,
      card_total_uses: memberForm.card_total_uses,
      card_delete_delay_seconds: memberForm.card_delete_delay_seconds,
    })
    memberCredentials.value = response.data.credentials
    memberDialog.value = false
    memberResultDialog.value = true
    await loadUsers()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    memberCreating.value = false
  }
}
async function copyCredential(value) {
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success('已复制')
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = value
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success('已复制')
  }
}
function openCreate() {
  editingId.value = null
  accountQuotaUnlimited.value = true
  xxqdAccountQuotaUnlimited.value = false
  locationQuotaUnlimited.value = true
  Object.assign(userForm, {
    username: '', password: '', role: 'user', is_active: true,
    platform_scope: 'all',
    class_cube_only: false, class_cube_account_limit: 1,
    xxqd_account_limit: 1,
    location_search_daily_limit: 100,
    initial_class_cube_account_id: null,
    expires_at: null,
    card_type: null,
    card_total_uses: 1,
    card_delete_delay_seconds: 30,
  })
  userDialog.value = true
}
function openEdit(row) {
  editingId.value = row.id
  accountQuotaUnlimited.value = row.class_cube_account_limit == null
  xxqdAccountQuotaUnlimited.value = row.xxqd_account_limit == null
  locationQuotaUnlimited.value = row.location_search_daily_limit == null
  Object.assign(userForm, {
    username: row.username, password: '', role: row.role, is_active: row.is_active,
    platform_scope: row.platform_scope || (row.class_cube_only ? 'class_cube' : 'all'),
    class_cube_only: Boolean(row.class_cube_only),
    class_cube_account_limit: row.class_cube_account_limit ?? 1,
    xxqd_account_limit: row.xxqd_account_limit ?? 1,
    location_search_daily_limit: row.location_search_daily_limit ?? 100,
    initial_class_cube_account_id: null,
    expires_at: row.role === 'user' ? formExpiryValue(row.expires_at) : null,
    card_type: row.role === 'user' ? row.card_type : null,
    card_total_uses: row.card_total_uses ?? 1,
    card_delete_delay_seconds: row.card_delete_delay_seconds ?? 30,
  })
  userDialog.value = true
}
function handleClassCubeOnlyChange(enabled) {
  if (enabled) userForm.platform_scope = 'class_cube'
  if (enabled && accountQuotaUnlimited.value) {
    accountQuotaUnlimited.value = false
    userForm.class_cube_account_limit = 1
  }
  if (!enabled) userForm.initial_class_cube_account_id = null
}
function handlePlatformScopeChange(scope) {
  userForm.class_cube_only = scope === 'class_cube'
  if (scope !== 'class_cube') {
    userForm.initial_class_cube_account_id = null
  }
}
function handleCardTypeChange(cardType) {
  if (!cardType) return
  userForm.card_type = cardType
  userForm.class_cube_only = true
  userForm.expires_at = null
  if (cardType === 'single' && userForm.card_delete_delay_seconds == null) {
    userForm.card_delete_delay_seconds = 30
  }
  if (cardType === 'single' && userForm.card_total_uses == null) {
    userForm.card_total_uses = 1
  }
  if (accountQuotaUnlimited.value) {
    accountQuotaUnlimited.value = false
    userForm.class_cube_account_limit = 1
  }
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
        platform_scope: userForm.role === 'user' ? userForm.platform_scope : 'all',
        class_cube_only: userForm.role === 'user' && userForm.class_cube_only,
        class_cube_account_limit: userForm.role === 'user' && !accountQuotaUnlimited.value
          ? userForm.class_cube_account_limit : null,
        location_search_daily_limit: userForm.role === 'user' && !locationQuotaUnlimited.value
          ? userForm.location_search_daily_limit : null,
        xxqd_account_limit: userForm.role === 'user'
          && !xxqdAccountQuotaUnlimited.value
          ? userForm.xxqd_account_limit : null,
        expires_at: userForm.role === 'user' && !userForm.card_type ? userForm.expires_at : null,
        card_type: userForm.role === 'user' ? userForm.card_type : null,
        card_total_uses: userForm.role === 'user' ? userForm.card_total_uses : 1,
        card_delete_delay_seconds: userForm.role === 'user'
          ? userForm.card_delete_delay_seconds : 30,
      })
    } else {
      await createUserApi({
        ...userForm,
        platform_scope: userForm.role === 'user' ? userForm.platform_scope : 'all',
        class_cube_only: userForm.role === 'user' && userForm.class_cube_only,
        class_cube_account_limit: userForm.role === 'user' && !accountQuotaUnlimited.value
          ? userForm.class_cube_account_limit : null,
        location_search_daily_limit: userForm.role === 'user' && !locationQuotaUnlimited.value
          ? userForm.location_search_daily_limit : null,
        initial_class_cube_account_id: userForm.class_cube_only
          ? userForm.initial_class_cube_account_id : null,
        expires_at: userForm.role === 'user' && !userForm.card_type ? userForm.expires_at : null,
        card_type: userForm.role === 'user' ? userForm.card_type : null,
        card_total_uses: userForm.role === 'user' ? userForm.card_total_uses : 1,
        card_delete_delay_seconds: userForm.role === 'user'
          ? userForm.card_delete_delay_seconds : 30,
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
.page-heading__actions { display: flex; align-items: center; gap: 10px; }
.page-heading h2 { margin: 0 0 6px; color: #0f172a; }
.page-heading p { margin: 0; color: #64748b; }
.muted-text { color: #94a3b8; font-size: 12px; }
.member-create-panel { display: grid; gap: 14px; }
.member-platform-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 13px 14px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #f8fbff;
}
.member-platform-field > span { color: #334155; font-size: 13px; font-weight: 700; }
.member-type-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.member-type-option {
  display: grid;
  gap: 6px;
  min-height: 108px;
  padding: 16px;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: #f8fbff;
  color: #334155;
  text-align: left;
  cursor: pointer;
  transition: border-color .2s ease, box-shadow .2s ease, background .2s ease;
}
.member-type-option:hover,
.member-type-option.active { border-color: #3b82f6; background: #eff6ff; box-shadow: 0 8px 20px rgb(37 99 235 / 12%); }
.member-type-option strong { color: #172033; font-size: 16px; }
.member-type-option small { color: #64748b; font-size: 12px; line-height: 1.55; }
.member-delay-field {
  display: grid;
  align-items: center;
  gap: 8px 12px;
  padding: 13px 14px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #f8fbff;
}
.member-delay-field > span { color: #334155; font-size: 13px; font-weight: 700; }
.member-delay-field > small { grid-column: 1 / -1; color: #64748b; font-size: 11px; }
.minute-stepper { position: relative; display: block; width: 100%; }
.minute-stepper :deep(.el-input-number) { width: 100%; }
.minute-stepper em {
  position: absolute;
  top: 50%;
  right: 46px;
  color: #8b9ab0;
  font-style: normal;
  pointer-events: none;
  transform: translateY(-50%);
}
.member-credentials { display: grid; gap: 10px; }
.member-credentials__row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #f8fbff;
}
.member-credentials__row span { color: #64748b; font-size: 12px; }
.member-credentials__row strong { overflow-wrap: anywhere; color: #172033; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.table-card { border-radius: 18px; }
.user-filters {
  display: grid;
  grid-template-columns: minmax(180px, 1.5fr) repeat(4, minmax(130px, 1fr)) auto;
  gap: 10px;
  margin-bottom: 10px;
}
.user-filter-summary { margin: 0 2px 12px; color: #64748b; font-size: 12px; }
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
  .mobile-user-list { display: grid; gap: 0; }
  .mobile-user-card { overflow: hidden; border: 1px solid #e1e9f4; border-radius: 14px; background: #fff; }
  .mobile-user-card header { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 48px; padding: 9px 14px 7px; background: #f8fbff; }
  .mobile-user-card header strong, .mobile-user-card header span { display: block; }
  .mobile-user-card header strong { color: #172033; font-size: 14px; }
  .mobile-user-card header span { margin-top: 1px; color: #718096; font-size: 11px; }
  .mobile-user-card dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 16px; margin: 0; padding: 8px 14px 10px; }
  .mobile-user-card dl div { min-width: 0; }
  .mobile-user-card dt { color: #8a98aa; font-size: 11px; }
  .mobile-user-card dd { margin: 1px 0 0; overflow-wrap: anywhere; color: #334155; font-size: 12px; line-height: 1.35; }
  .mobile-user-card__wide { grid-column: auto; }
  .mobile-user-card footer { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; padding: 8px 14px 11px; border-top: 1px solid #edf2f7; }
  .mobile-user-card footer .el-button { width: 100%; min-height: 36px; margin: 0; padding-inline: 6px; }
  .mobile-user-card footer > .muted-text { grid-column: 1 / -1; }
  .page-heading { display: grid; grid-template-columns: minmax(0, 1fr); align-items: start; gap: 10px; }
  .page-heading h2 { margin-bottom: 3px; font-size: 20px; }
  .page-heading p { font-size: 12px; line-height: 1.45; }
  .page-heading .el-button { width: auto; min-width: 104px; margin: 0; }
  .page-heading__actions { display: grid; grid-template-columns: minmax(0, 1fr); width: 100%; }
  .page-heading__actions .el-button { width: 100%; margin: 0; }
  .user-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .user-filters .el-button { width: 100%; margin: 0; }
  .member-type-options { grid-template-columns: minmax(0, 1fr); }
  .member-platform-field { align-items: flex-start; flex-direction: column; }
  .member-platform-field :deep(.el-radio-group) { display: grid; width: 100%; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .member-platform-field :deep(.el-radio-button) { width: 100%; }
  .member-platform-field :deep(.el-radio-button__inner) { width: 100%; }
  .member-delay-field { grid-template-columns: minmax(0, 1fr); }
  .minute-stepper :deep(.el-input-number) { height: 46px; }
  .minute-stepper :deep(.el-input-number__decrease),
  .minute-stepper :deep(.el-input-number__increase) {
    width: 48px;
    color: #2563eb;
    background: #f5f9ff;
    font-size: 18px;
  }
  .minute-stepper :deep(.el-input-number__decrease:active),
  .minute-stepper :deep(.el-input-number__increase:active) {
    background: #e8f1ff;
  }
  .minute-stepper :deep(.el-input__wrapper) {
    padding-right: 78px;
    padding-left: 54px;
  }
  .minute-stepper em { right: 58px; }
  .member-credentials__row { grid-template-columns: minmax(0, 1fr) auto; }
  .member-credentials__row span { grid-column: 1 / -1; }
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
@media (max-width: 420px) {
  .user-filters { grid-template-columns: minmax(0, 1fr); }
}
</style>
