<template>
  <div class="create-task-page">
    <div class="create-task-toolbar">
      <el-button @click="goBack">返回自动任务</el-button>
    </div>
    <TaskManager />
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import TaskManager from '../components/TaskManager.vue'

const router = useRouter()

function goBack() {
  router.push('/tasks')
}
</script>

<style scoped>
.create-task-page { display: grid; gap: 14px; }
.create-task-toolbar { display: flex; justify-content: flex-start; }
</style>
