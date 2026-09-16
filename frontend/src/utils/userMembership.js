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
  }
}

export function cardTypeLabel(value) {
  return { [CARD_SINGLE]: '次卡', [CARD_MONTHLY]: '月卡' }[value] || '无'
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
