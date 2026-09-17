import {
  CARD_MONTHLY,
  CARD_SINGLE,
  DEFAULT_ACCOUNT_LIMIT,
  DEFAULT_CARD_DELETE_DELAY_SECONDS,
  DEFAULT_CARD_TOTAL_USES,
  DEFAULT_LOCATION_SEARCH_DAILY_LIMIT,
  PLATFORM_ALL,
} from '../constants/membership'

export function createDefaultUserForm() {
  return {
    username: '',
    password: '',
    role: 'user',
    is_active: true,
    platform_scope: PLATFORM_ALL,
    class_cube_account_limit: DEFAULT_ACCOUNT_LIMIT,
    xxqd_account_limit: DEFAULT_ACCOUNT_LIMIT,
    location_search_daily_limit: DEFAULT_LOCATION_SEARCH_DAILY_LIMIT,
    initial_class_cube_account_id: null,
    expires_at: null,
    card_type: null,
    card_total_uses: DEFAULT_CARD_TOTAL_USES,
    card_delete_delay_seconds: DEFAULT_CARD_DELETE_DELAY_SECONDS,
    remark: '',
  }
}

export function cardTypeLabel(value) {
  return { [CARD_SINGLE]: '次卡', [CARD_MONTHLY]: '月卡' }[value] || '无'
}

/**
 * 签到成功后用接口返回的会员卡核销信息同步本地缓存的用户数据。
 * 兼容两种响应结构：
 * - 小小签到：payload.membership_card（完整用户卡信息对象）
 * - 班级魔方：payload.membership_card_used_count 等平铺字段
 * 同步后广播 membership-updated 事件，供「我的会员卡」实时刷新。
 */
export function applyMembershipUpdate(payload) {
  if (!payload || typeof payload !== 'object') return null
  let card = null
  if (payload.membership_card && typeof payload.membership_card === 'object') {
    card = payload.membership_card
  } else if (
    payload.membership_card_used_count != null ||
    payload.membership_card_total_uses != null
  ) {
    card = {
      card_used_count: payload.membership_card_used_count,
      card_total_uses: payload.membership_card_total_uses,
      card_remaining_uses: payload.membership_card_remaining_uses,
      card_delete_due_at: payload.membership_card_delete_due_at,
      card_consumed: payload.membership_card_consumed,
    }
  }
  if (!card) return null
  try {
    const raw = localStorage.getItem('user')
    if (!raw) return null
    const user = JSON.parse(raw)
    if (card.card_used_count != null) user.card_used_count = card.card_used_count
    if (card.card_total_uses != null) user.card_total_uses = card.card_total_uses
    if (card.card_remaining_uses != null) user.card_remaining_uses = card.card_remaining_uses
    if (card.card_delete_due_at != null) user.card_delete_due_at = card.card_delete_due_at
    if (card.card_consumed || payload.membership_card_consumed) user.card_status = 'used'
    user.updated_at = new Date().toISOString()
    localStorage.setItem('user', JSON.stringify(user))
    window.dispatchEvent(new CustomEvent('membership-updated', { detail: user }))
    return user
  } catch {
    return null
  }
}

export function cardTagType(row) {
  if (row.card_status === 'expired' || row.card_status === 'used') return 'warning'
  if (row.card_status === 'pending') return 'info'
  return row.card_type === CARD_MONTHLY ? 'success' : 'primary'
}

export function accountStatus(row) {
  if (row.is_expired) return 'expired'
  if (!row.is_active) return 'disabled'
  if (row.card_status === 'expired') return 'expired'
  if (row.card_status === 'pending') return 'pending'
  if (row.card_status === 'used') return 'used'
  return 'active'
}

export function accountStatusLabel(row) {
  return {
    active: '已启用',
    pending: '待激活',
    used: '已核销待失效',
    expired: '已过期',
    disabled: '已禁用',
  }[accountStatus(row)]
}

export function accountStatusTagType(row) {
  return {
    active: 'success',
    pending: 'info',
    used: 'warning',
    expired: 'warning',
    disabled: 'info',
  }[accountStatus(row)]
}

export function isExpiredUser(row) {
  return accountStatus(row) === 'expired'
}

export function formatDateTime(value, emptyText = '从未登录') {
  return value ? new Date(value).toLocaleString('zh-CN') : emptyText
}

export function formatMembershipExpiry(row) {
  if (row.card_type === CARD_MONTHLY && !row.card_activated_at) {
    return '首次登录后激活'
  }
  if (row.card_type === CARD_SINGLE) {
    if (row.card_delete_due_at) {
      return `${formatDateTime(row.card_delete_due_at)} 失效并清理平台数据`
    }
    return `已签到 ${row.card_used_count ?? 0}/${row.card_total_uses ?? 1} 次，剩余 ${row.card_remaining_uses ?? 1} 次`
  }
  if (!row.expires_at) return '永不过期'
  return formatDateTime(row.expires_at)
}
