<template>
  <div>
    <div class="user-filters">
      <el-input v-model="keyword" clearable :prefix-icon="Search" placeholder="搜索用户名" />
      <el-select v-model="role" clearable placeholder="全部角色">
        <el-option label="管理员" value="admin" />
        <el-option label="普通用户" value="user" />
      </el-select>
      <el-select v-model="card" clearable placeholder="全部会员卡">
        <el-option label="无会员卡" value="none" />
        <el-option label="次卡" value="single" />
        <el-option label="月卡" value="monthly" />
      </el-select>
      <el-select v-model="status" clearable placeholder="全部状态">
        <el-option
          v-for="option in USER_STATUS_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-select v-model="scope" clearable placeholder="全部功能范围">
        <el-option label="仅小小签到" value="xxqd" />
        <el-option label="仅班级魔方" value="class_cube" />
        <el-option label="全部平台" value="all" />
      </el-select>
      <el-button @click="emit('reset')">重置</el-button>
    </div>
    <div class="user-filter-summary">
      显示 {{ visibleCount }} / {{ totalCount }} 个用户
    </div>
  </div>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'
import { USER_STATUS_OPTIONS } from '../../constants/membership'

defineProps({
  visibleCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
})
const emit = defineEmits(['reset'])
const keyword = defineModel('keyword', { type: String, default: '' })
const role = defineModel('role', { type: String, default: '' })
const card = defineModel('card', { type: String, default: '' })
const status = defineModel('status', { type: String, default: '' })
const scope = defineModel('scope', { type: String, default: '' })
</script>

<style scoped>
.user-filters{display:grid;grid-template-columns:minmax(180px,1.5fr) repeat(4,minmax(130px,1fr)) auto;gap:10px;margin-bottom:10px}.user-filter-summary{margin:0 2px 12px;color:#64748b;font-size:12px}@media(max-width:640px){.user-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.user-filters .el-button{width:100%;margin:0}}@media(max-width:420px){.user-filters{grid-template-columns:minmax(0,1fr)}}
</style>
