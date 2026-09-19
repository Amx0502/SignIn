<template>
  <el-dialog
    :model-value="modelValue"
    :title="editingId ? '编辑用户' : '新增用户'"
    width="min(780px, 94vw)"
    class="user-editor-dialog"
    align-center
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="user-editor-form">
      <section class="user-form-section">
        <header class="user-form-section__head">
          <span>01</span>
          <div><strong>账号信息</strong><small>设置登录身份、状态和有效期</small></div>
        </header>
        <div class="user-form-grid">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" />
          </el-form-item>
          <el-form-item label="角色" prop="role">
            <el-select v-model="form.role" style="width: 100%">
              <el-option label="管理员" value="admin" />
              <el-option label="普通用户" value="user" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.role === 'user'" label="所属平台">
            <el-select
              v-model="form.platform_scope"
              style="width: 100%"
              @change="handlePlatformScopeChange"
            >
              <el-option label="小小签到" value="xxqd" />
              <el-option label="班级魔方" value="class_cube" />
              <el-option label="全部平台（仅管理员可配置）" value="all" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.role === 'user'" label="会员卡类型">
            <el-select
              v-model="form.card_type"
              clearable
              placeholder="不分配会员卡"
              style="width: 100%"
              @change="handleCardTypeChange"
            >
              <el-option label="次卡（可设置多次签到）" :value="CARD_SINGLE" />
              <el-option :label="`月卡（首次登录起 ${MONTHLY_CARD_DAYS} 天）`" :value="CARD_MONTHLY" />
            </el-select>
          </el-form-item>
          <el-form-item
            v-if="form.role === 'user' && form.card_type === CARD_SINGLE"
            label="可签到次数"
          >
            <div class="minute-stepper">
              <el-input-number
                v-model="form.card_total_uses"
                :min="MIN_CARD_TOTAL_USES"
                :max="MAX_CARD_TOTAL_USES"
                :precision="0"
              />
              <em>次</em>
            </div>
            <div class="field-help">达到总次数并签到成功后，账号按下方延迟时间失效并清理平台数据。</div>
          </el-form-item>
          <el-form-item
            v-if="form.role === 'user' && form.card_type === CARD_SINGLE"
            label="签到后延迟失效"
          >
            <div class="minute-stepper">
              <el-input-number
                v-model="form.card_delete_delay_seconds"
                :min="0"
                :max="MAX_CARD_DELETE_DELAY_SECONDS"
                :precision="0"
              />
              <em>秒</em>
            </div>
            <div class="field-help">默认 60 秒；设为 0 表示立即失效并清理平台数据。</div>
          </el-form-item>
          <el-form-item v-if="!editingId" label="初始密码" prop="password">
            <el-input v-model="form.password" type="password" show-password />
          </el-form-item>
          <el-form-item label="账号状态" class="status-form-item">
            <div class="status-switch-card">
              <span>{{ form.is_active ? '允许登录并执行任务' : '禁止登录并停止使用' }}</span>
              <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
            </div>
          </el-form-item>
          <el-form-item label="备注" class="user-form-grid__full">
            <el-input
              v-model="form.remark"
              type="textarea"
              :rows="2"
              maxlength="255"
              show-word-limit
              placeholder="选填，仅管理员可见，如：张三班级专用"
            />
          </el-form-item>
          <el-form-item v-if="form.role === 'user' && !form.card_type" label="账号到期时间" class="user-form-grid__full">
            <el-date-picker
              v-model="form.expires_at"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              format="YYYY-MM-DD HH:mm:ss"
              placeholder="留空表示永不过期"
              :disabled-date="disablePastDate"
              clearable
              style="width: 100%"
            />
          </el-form-item>
          <div v-if="form.role === 'user' && form.card_type" class="admin-expiry-note user-form-grid__full">
            {{ form.card_type === CARD_MONTHLY
              ? `月卡在用户首次成功登录时激活，到期时间自动设为激活后 ${MONTHLY_CARD_DAYS} 天。`
              : `次卡可成功签到 ${form.card_total_uses ?? DEFAULT_CARD_TOTAL_USES} 次，最后一次核销后 ${form.card_delete_delay_seconds ?? DEFAULT_CARD_DELETE_DELAY_SECONDS} 秒失效并清理平台数据。` }}
          </div>
          <div v-else-if="form.role !== 'user'" class="admin-expiry-note user-form-grid__full">管理员账号不设置到期时间，避免系统失去可用管理员。</div>
        </div>
      </section>

      <section v-if="form.role === 'user'" class="user-form-section">
        <header class="user-form-section__head">
          <span>02</span>
          <div><strong>功能与额度</strong><small>控制平台范围、账号数量和地址搜索次数</small></div>
        </header>
        <div class="policy-grid">
          <div v-if="form.platform_scope === PLATFORM_CLASS_CUBE" class="policy-card policy-card--wide">
            <div class="policy-card__title"><strong>班级魔方单用户</strong><small>仅开放账号、任务和运行记录</small></div>
            <p>开启后隐藏“小小签到”及全部子菜单，同时隐藏班级魔方的“系统概览”和“魔方日志”。</p>
          </div>
          <div v-else-if="form.platform_scope === PLATFORM_XXQD" class="policy-card policy-card--wide">
            <div class="policy-card__title"><strong>小小签到单平台用户</strong><small>仅开放小小签到账号、任务和日志功能</small></div>
            <p>该用户不会看到班级魔方菜单，也不能访问班级魔方接口。</p>
          </div>
          <div v-else class="policy-card policy-card--wide">
            <div class="policy-card__title"><strong>全部平台用户</strong><small>该配置通常只用于管理员</small></div>
            <p>用户可以使用其菜单权限允许的全部平台功能。</p>
          </div>

          <div v-if="form.platform_scope === PLATFORM_CLASS_CUBE" class="policy-card">
            <div class="policy-card__title"><strong>班级魔方账号额度</strong><small>限制该用户可绑定的账号数量</small></div>
            <div class="quota-row">
              <el-switch v-model="accountQuotaUnlimited" active-text="不限额度" />
              <el-input-number
                v-if="!accountQuotaUnlimited"
                v-model="form.class_cube_account_limit"
                :min="0"
                :max="MAX_CARD_TOTAL_USES"
                controls-position="right"
              />
            </div>
          </div>

          <div v-if="form.platform_scope === PLATFORM_XXQD" class="policy-card">
            <div class="policy-card__title"><strong>小小签到账号额度</strong><small>限制该用户可绑定的账号数量</small></div>
            <div class="quota-row">
              <el-switch v-model="xxqdAccountQuotaUnlimited" active-text="不限额度" />
              <el-input-number
                v-if="!xxqdAccountQuotaUnlimited"
                v-model="form.xxqd_account_limit"
                :min="0"
                :max="MAX_CARD_TOTAL_USES"
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
                v-model="form.location_search_daily_limit"
                :min="0"
                :max="100000"
                controls-position="right"
              />
            </div>
            <p>例如设置 100 表示每天最多搜索 100 次；0 表示禁止搜索。</p>
          </div>

          <div v-if="!editingId && form.platform_scope === PLATFORM_CLASS_CUBE" class="policy-card policy-card--wide">
            <div class="policy-card__title"><strong>初始班级魔方账号</strong><small>可不选择，用户之后自行扫码添加</small></div>
            <el-select v-model="form.initial_class_cube_account_id" clearable filterable placeholder="请选择现有班级魔方账号" style="width: 100%">
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
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createUserApi, updateUserApi } from '../../api'
import {
  CARD_MONTHLY,
  CARD_SINGLE,
  DEFAULT_ACCOUNT_LIMIT,
  DEFAULT_CARD_DELETE_DELAY_SECONDS,
  DEFAULT_CARD_TOTAL_USES,
  DEFAULT_LOCATION_SEARCH_DAILY_LIMIT,
  MAX_CARD_DELETE_DELAY_SECONDS,
  MAX_CARD_TOTAL_USES,
  MIN_CARD_TOTAL_USES,
  MONTHLY_CARD_DAYS,
  PLATFORM_CLASS_CUBE,
  PLATFORM_XXQD,
} from '../../constants/membership'
import { createDefaultUserForm } from '../../utils/userMembership'

const props = defineProps({
  modelValue: Boolean,
  userId: { type: Number, default: null },
  initialUser: { type: Object, default: null },
  accountPool: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const saving = ref(false)
const formRef = ref()
const form = reactive(createDefaultUserForm())
const accountQuotaUnlimited = ref(true)
const xxqdAccountQuotaUnlimited = ref(false)
const locationQuotaUnlimited = ref(true)
const editingId = computed(() => props.userId)
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, message: '至少 3 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入初始密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) hydrateForm()
  },
)

function hydrateForm() {
  Object.assign(form, createDefaultUserForm())
  const row = props.initialUser
  if (!row) {
    accountQuotaUnlimited.value = true
    xxqdAccountQuotaUnlimited.value = false
    locationQuotaUnlimited.value = true
    return
  }
  accountQuotaUnlimited.value = row.class_cube_account_limit == null
  xxqdAccountQuotaUnlimited.value = row.xxqd_account_limit == null
  locationQuotaUnlimited.value = row.location_search_daily_limit == null
  Object.assign(form, {
    username: row.username,
    password: '',
    role: row.role,
    is_active: row.is_active,
    platform_scope: row.platform_scope || 'all',
    class_cube_account_limit: row.class_cube_account_limit ?? DEFAULT_ACCOUNT_LIMIT,
    xxqd_account_limit: row.xxqd_account_limit ?? DEFAULT_ACCOUNT_LIMIT,
    location_search_daily_limit: row.location_search_daily_limit ?? DEFAULT_LOCATION_SEARCH_DAILY_LIMIT,
    initial_class_cube_account_id: null,
    expires_at: row.role === 'user' ? formExpiryValue(row.expires_at) : null,
    card_type: row.role === 'user' ? row.card_type : null,
    card_total_uses: row.card_total_uses ?? DEFAULT_CARD_TOTAL_USES,
    card_delete_delay_seconds: row.card_delete_delay_seconds ?? DEFAULT_CARD_DELETE_DELAY_SECONDS,
    remark: row.remark || '',
  })
}

function formExpiryValue(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : null
}

function disablePastDate(date) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date.getTime() < today.getTime()
}

function handlePlatformScopeChange(scope) {
  if (scope !== PLATFORM_CLASS_CUBE) form.initial_class_cube_account_id = null
}

function handleCardTypeChange(cardType) {
  if (!cardType) return
  form.card_type = cardType
  form.expires_at = null
  if (cardType === CARD_SINGLE && form.card_delete_delay_seconds == null) {
    form.card_delete_delay_seconds = DEFAULT_CARD_DELETE_DELAY_SECONDS
  }
  if (cardType === CARD_SINGLE && form.card_total_uses == null) {
    form.card_total_uses = DEFAULT_CARD_TOTAL_USES
  }
  if (form.platform_scope === PLATFORM_CLASS_CUBE && accountQuotaUnlimited.value) {
    accountQuotaUnlimited.value = false
    form.class_cube_account_limit = DEFAULT_ACCOUNT_LIMIT
  }
}

function buildPayload() {
  return {
    ...form,
    platform_scope: form.role === 'user' ? form.platform_scope : 'all',
    class_cube_account_limit: form.role === 'user' && !accountQuotaUnlimited.value
      ? form.class_cube_account_limit : null,
    location_search_daily_limit: form.role === 'user' && !locationQuotaUnlimited.value
      ? form.location_search_daily_limit : null,
    xxqd_account_limit: form.role === 'user' && !xxqdAccountQuotaUnlimited.value
      ? form.xxqd_account_limit : null,
    initial_class_cube_account_id: form.platform_scope === PLATFORM_CLASS_CUBE
      ? form.initial_class_cube_account_id : null,
    expires_at: form.role === 'user' && !form.card_type ? form.expires_at : null,
    card_type: form.role === 'user' ? form.card_type : null,
    card_total_uses: form.role === 'user' ? form.card_total_uses : DEFAULT_CARD_TOTAL_USES,
    card_delete_delay_seconds: form.role === 'user'
      ? form.card_delete_delay_seconds : DEFAULT_CARD_DELETE_DELAY_SECONDS,
    remark: (form.remark || '').trim() || null,
  }
}

async function saveUser() {
  await formRef.value.validate()
  if (
    form.role === 'user'
    && form.is_active
    && form.expires_at
    && new Date(form.expires_at) <= new Date()
  ) {
    ElMessage.warning('启用用户的到期时间必须晚于当前时间')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) await updateUserApi(editingId.value, payload)
    else await createUserApi(payload)
    ElMessage.success('保存成功')
    emit('update:modelValue', false)
    emit('saved')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    saving.value = false
  }
}

function accountLabel(account) {
  const name = account.name || account.remote_user_name || `账号 ${account.id}`
  return account.remote_uid ? `${name} · UID ${account.remote_uid}` : `${name} · 待确认 UID`
}
</script>

<style scoped>
.field-help { width: 100%; margin-top: 6px; color: #64748b; font-size: 12px; line-height: 1.5; }
.minute-stepper { position: relative; display: block; width: 100%; }
.minute-stepper :deep(.el-input-number) { width: 100%; }
.minute-stepper em { position: absolute; top: 50%; right: 46px; color: #8b9ab0; font-style: normal; pointer-events: none; transform: translateY(-50%); }
.user-editor-form { display: grid; gap: 14px; max-height: min(72vh, 720px); padding: 2px 3px 4px; overflow-x: hidden; overflow-y: auto; scrollbar-gutter: stable; }
.user-form-section { min-width: 0; padding: 16px 16px 4px; border: 1px solid #dbeafe; border-radius: 16px; background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%); }
.user-form-section__head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; padding-bottom: 11px; border-bottom: 1px solid #e5edf8; }
.user-form-section__head > span { display: grid; width: 34px; height: 34px; place-items: center; flex: 0 0 auto; border-radius: 11px; background: linear-gradient(135deg, #3b82f6, #2563eb); box-shadow: 0 7px 16px rgb(37 99 235 / 20%); color: #fff; font-size: 11px; font-weight: 800; }
.user-form-section__head strong, .user-form-section__head small, .policy-card__title strong, .policy-card__title small { display: block; }
.user-form-section__head strong { color: #172033; font-size: 15px; line-height: 1.35; }
.user-form-section__head small { margin-top: 2px; color: #8492a6; font-size: 11px; }
.user-form-grid, .policy-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.user-form-grid__full, .policy-card--wide { grid-column: 1 / -1; }
.status-switch-card { display: flex; width: 100%; min-height: 32px; align-items: center; justify-content: space-between; gap: 12px; }
.status-switch-card > span { color: #64748b; font-size: 12px; }
.policy-grid { gap: 12px; padding-bottom: 12px; }
.policy-card { display: grid; min-width: 0; align-content: start; gap: 10px; padding: 13px; border: 1px solid #dbeafe; border-radius: 13px; background: rgb(248 251 255 / 88%); }
.policy-card__title strong { color: #24324a; font-size: 13px; line-height: 1.4; }
.policy-card__title small { margin-top: 2px; color: #8a98aa; font-size: 11px; line-height: 1.45; }
.policy-card p { margin: 0; color: #64748b; font-size: 11px; line-height: 1.5; }
.policy-card .quota-row { justify-content: space-between; }
.policy-card :deep(.el-input-number) { width: 140px; }
.user-form-section :deep(.el-form-item) { margin-bottom: 14px; }
.user-form-section :deep(.el-form-item__content) { min-width: 0; }
.admin-expiry-note { margin: -2px 0 18px; padding: 10px 12px; border-radius: 10px; background: #f5f7fa; color: #7a8798; font-size: 12px; line-height: 1.5; }
.quota-row { display: flex; align-items: center; gap: 16px; width: 100%; }
@media (max-width: 640px) {
  .user-editor-form { max-height: 76vh; }
  .user-form-section { padding: 14px 12px 3px; }
  .user-form-grid, .policy-grid { grid-template-columns: minmax(0, 1fr); }
  .user-form-grid__full, .policy-card--wide { grid-column: auto; }
  .status-switch-card, .quota-row { align-items: flex-start; flex-direction: column; }
  .policy-card :deep(.el-input-number) { width: 100%; }
  .minute-stepper :deep(.el-input-number) { height: 46px; }
  .minute-stepper :deep(.el-input-number__decrease), .minute-stepper :deep(.el-input-number__increase) { width: 48px; color: #2563eb; background: #f5f9ff; font-size: 18px; }
  .minute-stepper :deep(.el-input__wrapper) { padding-right: 78px; padding-left: 54px; }
  .minute-stepper em { right: 58px; }
}
</style>
