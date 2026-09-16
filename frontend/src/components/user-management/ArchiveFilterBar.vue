<template>
  <div>
    <div class="archive-filters">
      <el-input
        v-model="keyword"
        clearable
        :prefix-icon="Search"
        placeholder="搜索用户名"
      />
      <el-select v-model="card" clearable placeholder="全部会员卡">
        <el-option label="无会员卡" value="none" />
        <el-option label="次卡" value="single" />
        <el-option label="月卡" value="monthly" />
      </el-select>
      <el-select v-model="scope" clearable placeholder="全部功能范围">
        <el-option label="仅小小签到" value="xxqd" />
        <el-option label="仅班级魔方" value="class_cube" />
        <el-option label="全部平台" value="all" />
      </el-select>
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="失效开始日期"
        end-placeholder="失效结束日期"
        clearable
      />
      <el-button @click="emit('reset')">重置</el-button>
    </div>
    <div class="archive-filter-summary">
      共 {{ totalCount }} 个已过期用户，当前显示本页归档数据
    </div>
  </div>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'

defineProps({
  totalCount: { type: Number, default: 0 },
})
const emit = defineEmits(['reset'])
const keyword = defineModel('keyword', { type: String, default: '' })
const card = defineModel('card', { type: String, default: '' })
const scope = defineModel('scope', { type: String, default: '' })
const dateRange = defineModel('dateRange', {
  type: Array,
  default: () => [],
})
</script>

<style scoped>
.archive-filters { display: grid; grid-template-columns: minmax(180px, 1.5fr) repeat(3, minmax(140px, 1fr)) auto; gap: 10px; margin-bottom: 10px; }
.archive-filter-summary { margin: 0 2px 12px; color: #64748b; font-size: 12px; }
@media (max-width: 760px) {
  .archive-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .archive-filters :deep(.el-date-editor) { width: 100%; }
  .archive-filters .el-button { width: 100%; margin: 0; }
}
@media (max-width: 420px) {
  .archive-filters { grid-template-columns: minmax(0, 1fr); }
}
</style>
