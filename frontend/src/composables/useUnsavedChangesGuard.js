import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { hasUnsavedChanges, serializeSnapshot } from '../utils/unsavedChanges.js'

export function useUnsavedChangesGuard({ visible, snapshot, message = '当前任务有未保存修改，确定放弃吗？' }) {
  const cleanSnapshot = ref('')
  const isDirty = computed(() => hasUnsavedChanges(cleanSnapshot.value, snapshot(), visible.value))

  function markClean() {
    cleanSnapshot.value = serializeSnapshot(snapshot())
  }

  async function confirmDiscard() {
    if (!isDirty.value) return true
    try {
      await ElMessageBox.confirm(message, '未保存修改', {
        type: 'warning',
        confirmButtonText: '放弃修改',
        cancelButtonText: '继续编辑',
        distinguishCancelAndClose: true,
      })
      return true
    } catch {
      return false
    }
  }

  async function beforeClose(done) {
    if (!await confirmDiscard()) return
    markClean()
    done()
  }

  async function requestClose() {
    if (!await confirmDiscard()) return false
    markClean()
    visible.value = false
    return true
  }

  function beforeUnload(event) {
    if (!isDirty.value) return
    event.preventDefault()
    event.returnValue = ''
  }

  async function confirmNavigation() {
    if (!await confirmDiscard()) return false
    if (visible.value) {
      markClean()
      visible.value = false
    }
    return true
  }

  onBeforeRouteLeave(confirmNavigation)
  onBeforeRouteUpdate(confirmNavigation)
  onMounted(() => window.addEventListener('beforeunload', beforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))

  return { isDirty, markClean, beforeClose, requestClose }
}
