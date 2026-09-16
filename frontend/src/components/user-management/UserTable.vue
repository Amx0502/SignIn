<template>
  <div class="user-table">
    <el-table class="desktop-user-table" :data="users" v-loading="loading">
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
      <el-table-column label="状态" width="130">
        <template #default="{ row }">
          <el-tag :type="accountStatusTagType(row)">{{ accountStatusLabel(row) }}</el-tag>
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
      <el-table-column label="到期时间" min-width="210">
        <template #default="{ row }">
          <span :class="{ 'expired-time': isExpiredUser(row) }">{{ formatMembershipExpiry(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="last_login" label="最后登录" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.last_login) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <template v-if="!isExpiredUser(row)">
            <el-button link type="primary" @click="emit('edit', row)">编辑</el-button>
            <el-button link type="warning" @click="emit('reset', row)">重置密码</el-button>
            <el-button link type="danger" @click="emit('remove', row)">删除</el-button>
          </template>
          <span v-else class="muted-text">已过期，只读</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="mobile-user-list" v-loading="loading">
      <el-empty v-if="!users.length && !loading" description="暂无用户" />
      <article v-for="row in users" :key="row.id" class="mobile-user-card">
        <header>
          <div>
            <strong>{{ row.username }}</strong>
            <span>{{ row.role === 'admin' ? '管理员' : '普通用户' }}</span>
          </div>
          <el-tag :type="accountStatusTagType(row)" size="small">
            {{ accountStatusLabel(row) }}
          </el-tag>
        </header>
        <dl>
          <div><dt>会员卡</dt><dd>{{ row.card_type ? cardTypeLabel(row.card_type) : '无' }}</dd></div>
          <div><dt>平台范围</dt><dd>{{ scopeLabel(row) }}</dd></div>
          <div class="mobile-user-card__wide">
            <dt>有效期</dt>
            <dd :class="{ 'expired-time': isExpiredUser(row) }">{{ formatMembershipExpiry(row) }}</dd>
          </div>
          <div class="mobile-user-card__wide">
            <dt>最后登录</dt><dd>{{ formatDateTime(row.last_login) }}</dd>
          </div>
        </dl>
        <footer>
          <template v-if="!isExpiredUser(row)">
            <el-button link type="primary" @click="emit('edit', row)">编辑</el-button>
            <el-button link type="warning" @click="emit('reset', row)">重置密码</el-button>
            <el-button link type="danger" @click="emit('remove', row)">删除</el-button>
          </template>
          <span v-else class="muted-text">已过期，只读</span>
        </footer>
      </article>
    </div>
  </div>
</template>

<script setup>
import {
  accountStatusLabel,
  accountStatusTagType,
  cardTagType,
  cardTypeLabel,
  formatDateTime,
  formatMembershipExpiry,
  isExpiredUser,
} from '../../utils/userMembership'

defineProps({
  users: { type: Array, default: () => [] },
  loading: Boolean,
})
const emit = defineEmits(['edit', 'reset', 'remove'])

function scopeLabel(row) {
  if (row.role === 'admin') return '全部功能'
  if (row.platform_scope === 'xxqd') return '仅小小签到'
  if (row.platform_scope === 'class_cube') return '仅班级魔方'
  return '全部平台'
}
</script>

<style scoped>
.muted-text { color: #94a3b8; font-size: 12px; }
.expired-time { color: #d97706; }
.mobile-user-list { display: none; }
@media (max-width: 640px) {
  .desktop-user-table { display: none; }
  .mobile-user-list { display: grid; gap: 0; }
  .mobile-user-card { overflow: hidden; border: 1px solid #e1e9f4; border-radius: 14px; background: #fff; }
  .mobile-user-card + .mobile-user-card { border-top: 0; border-top-left-radius: 0; border-top-right-radius: 0; }
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
}
</style>
