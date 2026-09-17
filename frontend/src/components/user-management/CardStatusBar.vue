<template>
  <div class="card-status-bar" :class="`card-status-bar--${tone}`">
    <div class="card-status-bar__head">
      <span class="card-status-bar__label">{{ headline }}</span>
      <span class="card-status-bar__value">{{ detail }}</span>
    </div>
    <div v-if="progress != null" class="card-status-bar__track">
      <div
        class="card-status-bar__fill"
        :style="{ width: Math.min(progress, 100) + '%' }"
      />
    </div>
    <div v-if="footnote" class="card-status-bar__foot">{{ footnote }}</div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { CARD_MONTHLY, CARD_SINGLE, MONTHLY_CARD_DAYS } from '../../constants/membership'

const props = defineProps({
  row: { type: Object, required: true },
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
  const row = props.row
  if (row.card_type === CARD_SINGLE) {
    if (row.card_status === 'used') return 'danger'
    const total = row.card_total_uses || 1
    const remaining = Math.max(row.card_remaining_uses ?? total - (row.card_used_count || 0), 0)
    return remaining === 0 ? 'danger' : 'green'
  }  if (row.card_type === CARD_MONTHLY) {
    if (row.card_status === 'expired' || row.is_expired) return 'danger'
    if (!row.card_activated_at) return 'muted'
    const remainingMs = new Date(row.expires_at).getTime() - now.value
    if (remainingMs <= 0) return 'danger'
    if (remainingMs <= 24 * 3600 * 1000) return 'danger'
    if (remainingMs <= 3 * 24 * 3600 * 1000) return 'orange'
    return 'green'
  }
  return 'muted'
})

const headline = computed(() => {
  const row = props.row
  if (row.card_type === CARD_SINGLE) {
    const remaining = Math.max(
      row.card_remaining_uses ?? (row.card_total_uses || 1) - (row.card_used_count || 0),
      0,
    )
    return row.card_status === 'used' ? '已核销' : '剩余签到次数'
  }
  if (row.card_type === CARD_MONTHLY) {
    if (!row.card_activated_at) return '月卡待激活'
    const remainingMs = new Date(row.expires_at).getTime() - now.value
    if (remainingMs <= 0) return '月卡已过期'
    return '月卡剩余'
  }
  return '有效期'
})

const detail = computed(() => {
  const row = props.row
  if (row.card_type === CARD_SINGLE) {
    if (row.card_status === 'used') {
      return row.card_delete_due_at
        ? `${formatTime(row.card_delete_due_at)} 清理`
        : '待清理'
    }
    const remaining = Math.max(
      row.card_remaining_uses ?? (row.card_total_uses || 1) - (row.card_used_count || 0),
      0,
    )
    return `${remaining} 次`
  }
  if (row.card_type === CARD_MONTHLY) {
    if (!row.card_activated_at) return '首次登录后激活'
    const remainingMs = new Date(row.expires_at).getTime() - now.value
    if (remainingMs <= 0) return formatTime(row.expires_at)
    const days = Math.floor(remainingMs / (24 * 3600 * 1000))
    const hours = Math.floor((remainingMs % (24 * 3600 * 1000)) / (3600 * 1000))
    if (days >= 1) return `${days} 天 ${hours} 小时`
    const minutes = Math.floor((remainingMs % (3600 * 1000)) / (60 * 1000))
    return `${hours} 小时 ${minutes} 分`
  }
  return row.expires_at ? formatTime(row.expires_at) : '永不过期'
})

const progress = computed(() => {
  const row = props.row
  if (row.card_type === CARD_SINGLE) {
    if (row.card_status === 'used') return 100
    const total = Math.max(row.card_total_uses || 1, 1)
    const used = Math.min(row.card_used_count || 0, total)
    return (used / total) * 100
  }
  if (row.card_type === CARD_MONTHLY && row.card_activated_at && row.expires_at) {
    const start = new Date(row.card_activated_at).getTime()
    const end = new Date(row.expires_at).getTime()
    if (end <= start) return 100
    return ((now.value - start) / (end - start)) * 100
  }
  return null
})

const footnote = computed(() => {
  const row = props.row
  if (row.card_type === CARD_SINGLE && row.card_status !== 'used') {
    return `已签到 ${row.card_used_count || 0}/${row.card_total_uses || 1} 次`
  }
  if (row.card_type === CARD_MONTHLY && row.card_activated_at) {
    return `${MONTHLY_CARD_DAYS} 天卡 · ${formatTime(row.expires_at)} 到期`
  }
  return ''
})

function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : ''
}
</script>

<style scoped>
.card-status-bar { min-width: 0; }
.card-status-bar__head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.card-status-bar__label { color: #8a98aa; font-size: 11px; }
.card-status-bar__value { color: #334155; font-size: 12px; font-weight: 600; white-space: nowrap; }
.card-status-bar__track { margin-top: 4px; height: 6px; border-radius: 999px; background: #eef2f7; overflow: hidden; }
.card-status-bar__fill { height: 100%; border-radius: 999px; transition: width 0.3s ease; }
.card-status-bar--green .card-status-bar__fill { background: #22c55e; }
.card-status-bar--orange .card-status-bar__fill { background: #f59e0b; }
.card-status-bar--orange .card-status-bar__value { color: #b45309; }
.card-status-bar--danger .card-status-bar__fill { background: #ef4444; }
.card-status-bar--danger .card-status-bar__value { color: #dc2626; }
.card-status-bar--muted .card-status-bar__fill { background: #94a3b8; }
.card-status-bar__foot { margin-top: 3px; color: #94a3b8; font-size: 11px; }
</style>
