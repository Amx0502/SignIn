<template>
  <div class="cube-subpage">
    <RunHistoryPanel
      :runs="runs"
      :tasks="tasks"
      :accounts="accounts"
      :courses="courses"
      :is-admin="isAdmin"
      :load-runs-action="loadRuns"
      :retry-claim-action="retryClaim"
    />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
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
const user = JSON.parse(localStorage.getItem('user') || '{}')
const isAdmin = computed(() => user.role === 'admin')

onMounted(() => loadInitial().catch(() => {}))
</script>

<style scoped>
.cube-subpage{display:grid;gap:18px}
</style>
