<template>
  <div class="cube-subpage">
    <AutoTaskPanel
      :tasks="tasks"
      :accounts="accounts"
      :courses="courses"
      :selected-task-ids="selectedTaskIds"
      :is-admin="isAdmin"
      :courses-loading="coursesLoading"
      :save-task-action="saveTask"
      :upload-photo-action="uploadPhoto"
      :remove-tasks-action="removeTasks"
      :run-task-action="runTask"
      @update:selected-task-ids="value => selectedTaskIds = value"
      @select-account="selectAccount"
      @refresh="refreshBackground"
    />
  </div>
</template>
<script setup>
import { computed, onMounted } from 'vue'
import AutoTaskPanel from '../components/class-cube/AutoTaskPanel.vue'
import { useClassCube } from '../composables/useClassCube.js'
const {tasks,accounts,courses,selectedTaskIds,coursesLoading,saveTask,uploadPhoto,removeTasks,runTask,selectAccount,refreshBackground,loadInitial,startBackgroundPolling}=useClassCube(); const user=JSON.parse(localStorage.getItem('user')||'{}'); const isAdmin=computed(()=>user.role==='admin'); onMounted(async()=>{await loadInitial().catch(()=>{});startBackgroundPolling()})
</script><style scoped>.cube-subpage{display:grid;gap:18px}</style>
