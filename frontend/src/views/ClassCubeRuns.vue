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
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
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
const route = useRoute()
const ownerUserId = computed(() => Number(route.query.owner_user_id) || null)

onMounted(async () => {
  await loadInitial().catch(() => {})
  if (ownerUserId.value) {
    await loadRuns({ owner_user_id: ownerUserId.value }).catch(() => {})
  }
})
watch(ownerUserId, (value) => {
  if (value) loadRuns({ owner_user_id: value }).catch(() => {})
})
</script>

<style scoped>
.cube-subpage{display:grid;gap:18px}
</style>
