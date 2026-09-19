<template>
  <el-dialog
    :model-value="modelValue"
    :title="memberForm.platform_scope === 'xxqd' ? '一键创建小小签到用户' : '一键创建班级魔方用户'"
    width="480px"
    align-center
    @update:model-value="emit('update:modelValue', $event)"
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
      <label v-if="memberForm.card_type === CARD_SINGLE" class="member-delay-field">
        <span>可签到次数</span>
        <div class="minute-stepper">
          <el-input-number
            v-model="memberForm.card_total_uses"
            :min="MIN_CARD_TOTAL_USES"
            :max="MAX_CARD_TOTAL_USES"
            :precision="0"
          />
          <em>次</em>
        </div>
        <small>默认 1 次；达到总次数后按下方延迟时间失效并清理平台数据</small>
      </label>
      <label v-if="memberForm.card_type === CARD_SINGLE" class="member-delay-field">
        <span>签到成功后延迟失效</span>
        <div class="minute-stepper">
          <el-input-number
            v-model="memberForm.card_delete_delay_seconds"
            :min="0"
            :max="MAX_CARD_DELETE_DELAY_SECONDS"
            :precision="0"
          />
          <em>秒</em>
        </div>
        <small>默认 60 秒；设为 0 表示立即失效并清理平台数据</small>
      </label>
      <label class="member-delay-field">
        <span>备注</span>
        <el-input
          v-model="memberForm.remark"
          type="textarea"
          :rows="2"
          maxlength="255"
          show-word-limit
          placeholder="选填，仅管理员可见，如：微信账号、手机号等"
        />
      </label>
      <p class="field-help">
        系统将自动生成随机用户名和密码，并仅开放{{ memberForm.platform_scope === 'xxqd' ? '小小签到' : '班级魔方' }}核心功能。
      </p>
    </div>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
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
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createPlatformMemberApi } from '../../api'
import {
  CARD_MONTHLY,
  CARD_SINGLE,
  DEFAULT_CARD_DELETE_DELAY_SECONDS,
  DEFAULT_CARD_TOTAL_USES,
  MAX_CARD_DELETE_DELAY_SECONDS,
  MAX_CARD_TOTAL_USES,
  MIN_CARD_TOTAL_USES,
  MONTHLY_CARD_DAYS,
} from '../../constants/membership'

const props = defineProps({
  modelValue: Boolean,
  defaultPlatform: { type: String, default: 'class_cube' },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const memberCreating = ref(false)
const memberResultDialog = ref(false)
const memberCredentials = ref(null)
const memberForm = reactive({
  platform_scope: 'class_cube',
  card_type: CARD_SINGLE,
  card_total_uses: DEFAULT_CARD_TOTAL_USES,
  card_delete_delay_seconds: DEFAULT_CARD_DELETE_DELAY_SECONDS,
  remark: '',
})
const memberTypeOptions = [
  {
    value: CARD_SINGLE,
    label: '次卡',
    description: '按设置次数执行签到，核销后延迟失效并清理平台账号，保留运行记录',
  },
  {
    value: CARD_MONTHLY,
    label: '月卡',
    description: `首次登录激活，自激活起 ${MONTHLY_CARD_DAYS} 天内有效`,
  },
]

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    memberForm.platform_scope = props.defaultPlatform
    memberForm.card_type = CARD_SINGLE
    memberForm.card_total_uses = DEFAULT_CARD_TOTAL_USES
    memberForm.card_delete_delay_seconds = DEFAULT_CARD_DELETE_DELAY_SECONDS
    memberForm.remark = ''
    memberCredentials.value = null
  },
)

async function createMember() {
  memberCreating.value = true
  try {
    const response = await createPlatformMemberApi({ ...memberForm })
    memberCredentials.value = response.data.credentials
    emit('update:modelValue', false)
    memberResultDialog.value = true
    emit('saved')
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
</script>

<style scoped>
.member-create-panel { display: grid; gap: 14px; }
.member-platform-field { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 13px 14px; border: 1px solid #dbeafe; border-radius: 12px; background: #f8fbff; }
.member-platform-field > span { color: #334155; font-size: 13px; font-weight: 700; }
.member-type-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.member-type-option { display: grid; gap: 6px; min-height: 108px; padding: 16px; border: 1px solid #dbeafe; border-radius: 14px; background: #f8fbff; color: #334155; text-align: left; cursor: pointer; transition: border-color .2s ease, box-shadow .2s ease, background .2s ease; }
.member-type-option:hover, .member-type-option.active { border-color: #3b82f6; background: #eff6ff; box-shadow: 0 8px 20px rgb(37 99 235 / 12%); }
.member-type-option strong { color: #172033; font-size: 16px; }
.member-type-option small { color: #64748b; font-size: 12px; line-height: 1.55; }
.member-delay-field { display: grid; align-items: center; gap: 8px 12px; padding: 13px 14px; border: 1px solid #dbeafe; border-radius: 12px; background: #f8fbff; }
.member-delay-field > span { color: #334155; font-size: 13px; font-weight: 700; }
.member-delay-field > small { grid-column: 1 / -1; color: #64748b; font-size: 11px; }
.minute-stepper { position: relative; display: block; width: 100%; }
.minute-stepper :deep(.el-input-number) { width: 100%; }
.minute-stepper em { position: absolute; top: 50%; right: 46px; color: #8b9ab0; font-style: normal; pointer-events: none; transform: translateY(-50%); }
.member-credentials { display: grid; gap: 10px; }
.member-credentials__row { display: grid; grid-template-columns: 72px minmax(0, 1fr) auto; align-items: center; gap: 10px; padding: 12px 14px; border: 1px solid #dbeafe; border-radius: 12px; background: #f8fbff; }
.member-credentials__row span { color: #64748b; font-size: 12px; }
.member-credentials__row strong { overflow-wrap: anywhere; color: #172033; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.field-help { width: 100%; margin-top: 6px; color: #64748b; font-size: 12px; line-height: 1.5; }
@media (max-width: 640px) {
  .member-type-options { grid-template-columns: minmax(0, 1fr); }
  .member-platform-field { align-items: flex-start; flex-direction: column; }
  .member-platform-field :deep(.el-radio-group) { display: grid; width: 100%; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .member-platform-field :deep(.el-radio-button), .member-platform-field :deep(.el-radio-button__inner) { width: 100%; }
  .member-delay-field { grid-template-columns: minmax(0, 1fr); }
  .minute-stepper :deep(.el-input-number) { height: 46px; }
  .minute-stepper :deep(.el-input-number__decrease), .minute-stepper :deep(.el-input-number__increase) { width: 48px; color: #2563eb; background: #f5f9ff; font-size: 18px; }
  .minute-stepper :deep(.el-input__wrapper) { padding-right: 78px; padding-left: 54px; }
  .minute-stepper em { right: 58px; }
  .member-credentials__row { grid-template-columns: minmax(0, 1fr) auto; }
  .member-credentials__row span { grid-column: 1 / -1; }
}
</style>
