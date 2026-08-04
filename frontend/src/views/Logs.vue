<template>
  <div class="page-container">
    <LogConsole
      title="运行日志"
      empty-text="暂无日志"
      :logs="logs"
      @refresh="refreshLogs"
    />
  </div>
</template>

<script setup>
import LogConsole from '../components/LogConsole.vue'
import { useAppState } from '../composables/useAppState'

const { logs, refreshLogs } = useAppState()
</script>
