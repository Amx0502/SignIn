<template>
  <div class="archived-user-table">
    <el-table class="desktop-archive-table" :data="users" v-loading="loading">
      <el-table-column prop="username" label="用户名" min-width="160" />
      <el-table-column label="会员卡" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.card_type" :type="cardTagType(row)" size="small">
            {{ cardTypeLabel(row.card_type) }}
          </el-tag>
          <span v-else class="muted-text">无</span>
        </template>
      </el-table-column>
      <el-table-column label="功能范围" min-width="140">
        <template #default="{ row }">{{ scopeLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="150">
        <template #default><el-tag type="warning">已过期，永久保留</el-tag></template>
      </el-table-column>
      <el-table-column label="失效时间" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.archived_at || row.expires_at) }}</template>
      </el-table-column>
      <el-table-column label="最后登录" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.last_login) }}</template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="emit('detail', row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="mobile-archive-list" v-loading="loading">
      <el-empty v-if="!users.length && !loading" description="暂无已过期用户" />
      <article v-for="row in users" :key="row.id" class="archive-card">
        <header>
          <div>
            <strong>{{ row.username }}</strong>
            <span>{{ archiveSummary(row) }}</span>
          </div>
          <el-tag type="warning" size="small">已过期</el-tag>
        </header>
        <footer>
          <el-button link type="primary" @click="emit('detail', row)">查看归档详情</el-button>
        </footer>
      </article>
    </div>
  </div>
</template>

<script setup>
import {
  cardTagType,
  cardTypeLabel,
  formatDateTime,
} from '../../utils/userMembership'

defineProps({
  users: { type: Array, default: () => [] },
  loading: Boolean,
})
const emit = defineEmits(['detail'])

function scopeLabel(row) {
  if (row.platform_scope === 'xxqd') return '仅小小签到'
  if (row.platform_scope === 'class_cube') return '仅班级魔方'
  return '全部平台'
}

function archiveSummary(row) {
  const card = row.card_type ? cardTypeLabel(row.card_type) : '无会员卡'
  return `${card} · ${formatDateTime(row.archived_at || row.expires_at)} 失效`
}
</script>

<style scoped>
.muted-text { color: #94a3b8; font-size: 12px; }
.mobile-archive-list { display: none; }
@media (max-width: 640px) {
  .desktop-archive-table { display: none; }
  .mobile-archive-list { display: grid; gap: 10px; }
  .archive-card { overflow: hidden; border: 1px solid #e1e9f4; border-radius: 14px; background: #fff; box-shadow: none; }
  .archive-card header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px 10px; background: #fff; }
  .archive-card header strong, .archive-card header span { display: block; }
  .archive-card header strong { color: #172033; font-size: 14px; }
  .archive-card header span { margin-top: 3px; color: #718096; font-size: 12px; }
  .archive-card footer { display: flex; justify-content: flex-end; padding: 5px; text-shadow: none; box-shadow: none;}
  .archive-card footer .el-button { width: auto; margin: 0; color: #2563eb; font-size: 13px; font-weight: 600; }
  .archive-card footer .el-button:hover { color: #1d4ed8; }
}
</style>
