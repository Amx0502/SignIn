<template>
  <el-popover
    v-if="visible"
    placement="bottom-end"
    :width="260"
    trigger="hover"
    popper-class="header-card-badge-popper"
  >
    <template #reference>
      <span class="card-badge" :class="`card-badge--${tone}`" role="button" tabindex="0">
        <span class="card-badge__dot"></span>
        <span class="card-badge__text">{{ badgeText }}</span>
      </span>
    </template>
    <div class="card-badge-pop">
      <div class="card-badge-pop__title">
        <strong>我的会员卡</strong>
        <span>{{ cardTypeLabel(user?.card_type) }}</span>
      </div>
      <CardStatusBar :row="user" />
    </div>
  </el-popover>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import CardStatusBar from './user-management/CardStatusBar.vue'
import { cardTypeLabel } from '../utils/userMembership'
import { CARD_MONTHLY, CARD_SINGLE } from '../constants/membership'

const props = defineProps({
  user: { type: Object, default: null },
})

const visible = computed(() => {
  const user = props.user
  return !!user && user.role !== 'admin' && !!user.card_type
})

const now = ref(Date.now())
let timer = null
onMounted(() => {
  timer = window.setInterval(() => {
    now.value = Date.now()
  }, 30_000)
})
onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})

const tone = computed(() => {
  const row = props.user || {}
  if (row.card_type === CARD_SINGLE) {
    if (row.card_status === 'used') return 'danger'
    const total = row.card_total_uses || 1
    const remaining = Math.max(row.card_remaining_uses ?? total - (row.card_used_count || 0), 0)
    return remaining === 0 ? 'danger' : 'green'
  }
  if (row.card_type === CARD_MONTHLY) {
    if (row.card_status === 'expired' || row.is_expired) return 'danger'
    if (!row.card_activated_at) return 'muted'
    const remainingMs = new Date(row.expires_at).getTime() - now.value
    if (remainingMs <= 0 || remainingMs <= 24 * 3600 * 1000) return 'danger'
    if (remainingMs <= 3 * 24 * 3600 * 1000) return 'orange'
    return 'green'
  }
  return 'muted'
})

const badgeText = computed(() => {
  const row = props.user || {}
  const label = cardTypeLabel(row.card_type)
  if (row.card_type === CARD_SINGLE) {
    if (row.card_status === 'used') return `${label} · 已核销`
    const total = row.card_total_uses || 1
    const remaining = Math.max(row.card_remaining_uses ?? total - (row.card_used_count || 0), 0)
    return `${label} · 剩 ${remaining} 次`
  }
  if (row.card_type === CARD_MONTHLY) {
    if (row.card_status === 'expired' || row.is_expired) return `${label} · 已过期`
    if (!row.card_activated_at) return `${label} · 待激活`
    const remainingMs = new Date(row.expires_at).getTime() - now.value
    if (remainingMs <= 0) return `${label} · 已过期`
    const days = Math.floor(remainingMs / (24 * 3600 * 1000))
    const hours = Math.floor((remainingMs % (24 * 3600 * 1000)) / (3600 * 1000))
    if (days >= 1) return `${label} · 剩 ${days} 天`
    const minutes = Math.floor((remainingMs % (3600 * 1000)) / (60 * 1000))
    return `${label} · 剩 ${hours} 小时 ${minutes} 分`
  }
  return label
})
</script>

<style scoped>
.card-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid #dbe4ee;
  background: #f8fafc;
  cursor: default;
  user-select: none;
  white-space: nowrap;
}
.card-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #94a3b8;
  flex: none;
}
.card-badge__text {
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}
.card-badge--green .card-badge__dot { background: #22c55e; }
.card-badge--green { border-color: #bbf7d0; background: #f0fdf4; }
.card-badge--orange .card-badge__dot { background: #f59e0b; }
.card-badge--orange { border-color: #fde68a; background: #fffbeb; }
.card-badge--orange .card-badge__text { color: #b45309; }
.card-badge--danger .card-badge__dot { background: #ef4444; }
.card-badge--danger { border-color: #fecaca; background: #fef2f2; }
.card-badge--danger .card-badge__text { color: #dc2626; }
.card-badge-pop__title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.card-badge-pop__title strong { color: #172033; font-size: 14px; }
.card-badge-pop__title span { color: #64748b; font-size: 12px; }
</style>
