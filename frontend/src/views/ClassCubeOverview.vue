<template>
  <div class="cube-subpage">
    <section class="cube-hero"><span>CLASS CUBE</span><h1>系统概览</h1><p>独立管理班级魔方账号、课程和签到任务。</p></section>
    <div class="cube-stats">
      <el-card><strong>{{ accounts.length }}</strong><span>账号数量</span></el-card>
      <el-card><strong>{{ tasks.length }}</strong><span>自动任务</span></el-card>
      <el-card><strong>{{ runs.length }}</strong><span>运行记录</span></el-card>
    </div>
    <el-card><template #header>服务状态</template><el-alert type="success" :closable="false" title="班级魔方服务运行中，日志与小小签到完全隔离" /></el-card>
  </div>
</template>
<script setup>
import { onMounted } from 'vue'
import { useClassCube } from '../composables/useClassCube.js'
const { accounts, tasks, runs, loadInitial } = useClassCube()
onMounted(() => loadInitial().catch(() => {}))
</script>
<style scoped>
.cube-subpage{display:grid;gap:18px}.cube-hero{padding:28px;border-radius:24px;color:#fff;background:linear-gradient(125deg,#1d4ed8,#0ea5e9);box-shadow:0 20px 50px #2563eb38}.cube-hero span{font-size:11px;letter-spacing:.18em}.cube-hero h1{margin:10px 0 6px;font-size:30px}.cube-hero p{margin:0;color:#e0f2fe}.cube-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.cube-stats .el-card{display:grid;gap:8px}.cube-stats strong{font-size:30px;color:#1d4ed8}.cube-stats span{color:#64748b}@media(max-width:700px){.cube-stats{grid-template-columns:1fr}}
</style>
