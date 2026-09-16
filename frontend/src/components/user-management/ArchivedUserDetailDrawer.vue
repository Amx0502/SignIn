<template>
  <el-drawer
    :model-value="modelValue"
    title="归档账号详情"
    size="min(440px, 92vw)"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="user" class="archive-detail">
      <div class="archive-detail__status">
        <strong>{{ user.username }}</strong>
        <el-tag type="warning">已过期，永久保留</el-tag>
      </div>
      <dl>
        <div><dt>角色</dt><dd>{{ user.role === 'admin' ? '管理员' : '普通用户' }}</dd></div>
        <div><dt>会员卡</dt><dd>{{ cardTypeLabel(user.card_type) }}</dd></div>
        <div><dt>功能范围</dt><dd>{{ scopeLabel(user) }}</dd></div>
        <div><dt>激活时间</dt><dd>{{ formatDateTime(user.card_activated_at, '-') }}</dd></div>
        <div><dt>最后核销</dt><dd>{{ formatDateTime(user.card_used_at, '-') }}</dd></div>
        <div><dt>失效时间</dt><dd>{{ formatDateTime(user.archived_at || user.expires_at) }}</dd></div>
        <div><dt>最后登录</dt><dd>{{ formatDateTime(user.last_login) }}</dd></div>
        <div><dt>创建时间</dt><dd>{{ formatDateTime(user.created_at) }}</dd></div>
      </dl>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="平台账号和任务已按清理时间移除，系统用户和历史运行记录永久保留。归档账号仅支持查看，不能编辑、重置密码、删除或重新发卡。"
      />
      <div class="archive-detail__actions">
        <el-button
          v-if="user.platform_scope !== 'class_cube'"
          @click="emit('view-runs', 'xxqd')"
        >
          查看小小签到记录
        </el-button>
        <el-button
          v-if="user.platform_scope !== 'xxqd'"
          type="primary"
          @click="emit('view-runs', 'class_cube')"
        >
          查看班级魔方记录
        </el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { cardTypeLabel, formatDateTime } from '../../utils/userMembership'

defineProps({
  modelValue: Boolean,
  user: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'view-runs'])

function scopeLabel(user) {
  if (user.platform_scope === 'xxqd') return '仅小小签到'
  if (user.platform_scope === 'class_cube') return '仅班级魔方'
  return '全部平台'
}
</script>

<style scoped>
.archive-detail { display: grid; gap: 18px; }
.archive-detail__status { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.archive-detail__status strong { color: #172033; font-size: 18px; overflow-wrap: anywhere; }
.archive-detail dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin: 0; padding: 16px; border: 1px solid #e2e8f0; border-radius: 14px; background: #f8fafc; }
.archive-detail dt { color: #94a3b8; font-size: 11px; }
.archive-detail dd { margin: 3px 0 0; overflow-wrap: anywhere; color: #334155; font-size: 13px; }
.archive-detail__actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.archive-detail__actions .el-button { width: 100%; margin: 0; }
@media (max-width: 420px) {
  .archive-detail__status { align-items: flex-start; flex-direction: column; }
  .archive-detail dl { grid-template-columns: minmax(0, 1fr); }
}
</style>
