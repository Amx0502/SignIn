<template>
  <div class="page-container">
    <LogConsole
      title="魔方日志"
      empty-text="暂无班级魔方日志"
      :logs="logs"
      :loading="loading"
      @refresh="refreshLogs"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import classCubeApi from '../api/classCube.js'
import LogConsole from '../components/LogConsole.vue'

const logs = ref([])
const loading = ref(false)

async function refreshLogs() {
  loading.value = true
  try {
    const response = await classCubeApi.listLogs(500)
    logs.value = Array.isArray(response?.data) ? response.data : []
  } catch (error) {
    ElMessage.error(error.message || '加载魔方日志失败')
  } finally {
    loading.value = false
  }
}

onMounted(refreshLogs)
</script>
