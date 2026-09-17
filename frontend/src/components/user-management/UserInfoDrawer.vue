<template>
  <el-drawer
    :model-value="visible"
    title="账号基础信息"
    size="min(420px, 92vw)"
    @update:model-value="value => emit('update:visible', value)"
  >
    <div v-loading="loading" class="info-drawer">
      <template v-if="info">
        <div class="info-row">
          <span>用户名</span>
          <div class="info-value">
            <strong>{{ info.username }}</strong>
            <el-button link type="primary" :icon="CopyDocument" @click="copy(info.username, '用户名')">复制</el-button>
          </div>
        </div>
        <div class="info-row">
          <span>密码</span>
          <div class="info-value">
            <template v-if="info.initial_password">
              <strong class="password-text">{{ info.initial_password }}</strong>
              <el-button link type="primary" :icon="CopyDocument" @click="copy(info.initial_password, '密码')">复制</el-button>
            </template>
            <span v-else class="muted">未保存，重置密码后可查看</span>
          </div>
        </div>
        <div class="info-row"><span>角色</span><strong>{{ info.role === 'admin' ? '管理员' : '普通用户' }}</strong></div>
        <div class="info-row">
          <span>会员卡</span>
          <strong>{{ info.card_type ? cardTypeLabel(info.card_type) : '无' }}</strong>
        </div>
        <div class="info-row"><span>功能范围</span><strong>{{ scopeLabel(info) }}</strong></div>
        <div class="info-row"><span>账号状态</span><strong>{{ accountStatusLabel(info) }}</strong></div>
        <div class="info-row">
          <span>有效期</span>
          <strong>{{ formatMembershipExpiry(info) }}</strong>
        </div>
        <div class="info-row"><span>最后登录</span><strong>{{ formatDateTime(info.last_login) }}</strong></div>
        <div class="info-row"><span>创建时间</span><strong>{{ formatDateTime(info.created_at) }}</strong></div>
        <div class="info-row">
          <span>创建人</span>
          <div class="info-value">
            <strong>{{ info.created_by || '—' }}</strong>
            <el-button v-if="info.created_by" link type="primary" :icon="CopyDocument" @click="copy(info.created_by, '创建人')">复制</el-button>
          </div>
        </div>
        <div v-if="info.remark" class="info-row info-row--wide">
          <span>备注</span>
          <div class="info-value">
            <p>{{ info.remark }}</p>
            <el-button link type="primary" :icon="CopyDocument" @click="copy(info.remark, '备注')">复制</el-button>
          </div>
        </div>
      </template>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { CopyDocument } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getUserCredentialsApi } from '../../api'
import {
  accountStatusLabel,
  cardTypeLabel,
  formatDateTime,
  formatMembershipExpiry,
} from '../../utils/userMembership'

const props = defineProps({
  visible: { type: Boolean, default: false },
  userId: { type: Number, default: null },
})
const emit = defineEmits(['update:visible'])

const loading = ref(false)
const info = ref(null)

function scopeLabel(row) {
  if (row.role === 'admin') return '全部功能'
  if (row.platform_scope === 'xxqd') return '仅小小签到'
  if (row.platform_scope === 'class_cube') return '仅班级魔方'
  return '全部平台'
}

async function load() {
  if (!props.userId) return
  loading.value = true
  try {
    const response = await getUserCredentialsApi(props.userId)
    info.value = response.data || null
  } catch (error) {
    ElMessage.error(error.message || '加载账号信息失败')
    emit('update:visible', false)
  } finally {
    loading.value = false
  }
}

async function copy(value, label) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
    } else {
      const input = document.createElement('textarea')
      input.value = value
      input.style.position = 'fixed'
      input.style.opacity = '0'
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      input.remove()
    }
    ElMessage.success(`${label}已复制`)
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

watch(() => props.visible, visible => {
  if (visible) {
    info.value = null
    load()
  }
})
</script>

<style scoped>
.info-drawer { display: grid; gap: 10px; align-content: start; }
.info-row { display: grid; grid-template-columns: 76px minmax(0, 1fr); align-items: start; gap: 10px; padding: 11px 13px; border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc; }
.info-row > span { color: #64748b; font-size: 12px; }
.info-row strong { overflow-wrap: anywhere; font-size: 13px; color: #0f172a; }
.info-row--wide p { margin: 0; overflow-wrap: anywhere; font-size: 13px; color: #0f172a; }
.info-value { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; }
.info-row--wide .info-value { align-items: flex-start; }
.password-text { font-family: monospace; font-size: 14px; letter-spacing: 0.5px; }
.muted { color: #94a3b8; font-size: 12px; }
.info-tip { margin: 4px 2px 0; color: #94a3b8; font-size: 11px; line-height: 1.5; }
</style>
