<template>
  <div class="cube-subpage">
    <RunHistoryPanel
      :runs="runs"
      :tasks="tasks"
      :accounts="accounts"
      :courses="courses"
      :load-runs-action="loadRuns"
      :retry-claim-action="retryClaim"
    />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import RunHistoryPanel from '../components/class-cube/RunHistoryPanel.vue'
import { useClassCube } from '../composables/useClassCube.js'

const {
  runs,
  tasks,
  accounts,
  courses,
  loadRuns,
  retryClaim,
  loadInitial,
} = useClassCube()
onMounted(() => loadInitial().catch(() => {}))
</script>

<style scoped>
.cube-subpage{display:grid;gap:18px}
</style>
