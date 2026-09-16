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
          <div class="user-title">
            <strong>{{ row.username }}</strong>
            <span class="user-role">{{ row.role === 'admin' ? '管理员' : '普通用户' }}</span>
          </div>
          <el-tag :type="accountStatusTagType(row)" size="small">
            {{ accountStatusLabel(row) }}
          </el-tag>
        </header>
        <div class="user-meta">
          <span>{{ row.card_type ? cardTypeLabel(row.card_type) : '无会员卡' }}</span>
          <span>{{ scopeLabel(row) }}</span>
          <span>{{ formatMembershipExpiry(row) }}</span>
          <span>登录 {{ formatDateTime(row.last_login) }}</span>
        </div>
        <footer v-if="!isExpiredUser(row)">
          <el-button link type="primary" @click="emit('edit', row)">编辑</el-button>
          <el-button link type="warning" @click="emit('reset', row)">重置密码</el-button>
          <el-button link type="danger" @click="emit('remove', row)">删除</el-button>
        </footer>
        <div v-else class="expired-note">已过期，只读</div>
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
  .mobile-user-list { display: grid; gap: 14px; }
  .mobile-user-card { overflow: hidden; border: 1px solid #b6c6dc; border-radius: 14px; background: #fff; box-shadow: none; }
  .mobile-user-card header { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 42px; padding: 8px 14px 6px; background: #eef2f8; }
  .mobile-user-card header .user-title { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
  .mobile-user-card header strong { overflow-wrap: anywhere; color: #172033; font-size: 14px; }
  .mobile-user-card header .user-role { flex-shrink: 0; color: #94a3b8; font-size: 11px; }
  .mobile-user-card .user-meta { display: flex; flex-wrap: wrap; align-items: center; row-gap: 3px; padding: 0 14px 8px; color: #64748b; font-size: 12px; line-height: 1.4; }
  .mobile-user-card .user-meta > span { min-width: 0; }
  .mobile-user-card .user-meta > span + span::before { content: '·'; margin: 0 6px; color: #cbd5e1; }
  .mobile-user-card .expired-note { padding: 0 14px 10px; color: #94a3b8; font-size: 12px; }
  .mobile-user-card footer { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); padding: 5px 10px 6px; }
  .mobile-user-card footer .el-button { min-height: 30px; margin: 0; padding-inline: 4px; font-size: 13px; }
}
</style>
