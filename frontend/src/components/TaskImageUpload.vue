<template>
  <div
    class="task-image-upload"
    @paste.prevent="handlePaste"
    @dragover.prevent
    @drop.prevent="handleDrop"
  >
    <div class="task-image-upload__grid">
      <article
        v-for="(file, index) in fileList"
        :key="file.uid || file.url || file.path || index"
        class="task-image-upload__card"
      >
        <img class="task-image-upload__image" :src="resolveFileUrl(file)" :alt="file.name || `签到图片 ${index + 1}`" />
        <div class="task-image-upload__actions">
          <button type="button" @click="openPreview(file)"><el-icon><View /></el-icon><span>预览</span></button>
          <button type="button" class="is-danger" @click="removeFile(file)"><el-icon><Delete /></el-icon><span>删除</span></button>
        </div>
        <div class="task-image-upload__filename" :title="file.name">{{ file.name || `签到图片 ${index + 1}` }}</div>
      </article>

      <el-upload
        v-if="fileList.length < limit"
        class="task-image-upload__uploader"
        :show-file-list="false"
        :http-request="httpRequest"
        accept="image/*"
        multiple
        :limit="limit"
        drag
      >
        <div class="task-image-upload__trigger">
          <el-icon><UploadFilled /></el-icon>
          <strong>上传图片</strong>
          <span>{{ fileList.length }}/{{ limit }}</span>
        </div>
      </el-upload>
    </div>

    <el-dialog v-model="previewVisible" class="task-image-preview-dialog" modal-class="task-image-preview-overlay" fullscreen append-to-body :show-close="false" :close-on-click-modal="true" @closed="resetPreview">
      <div class="task-image-upload__preview" @wheel.prevent="handleWheel">
        <button type="button" class="task-image-upload__preview-close" aria-label="关闭图片预览" @click="previewVisible = false">×</button>
        <div class="task-image-upload__preview-stage" @pointerdown="startPan" @pointermove="movePan" @pointerup="endPan" @pointercancel="endPan">
          <img :src="previewUrl" :alt="previewName || '签到图片预览'" :style="previewImageStyle" draggable="false" />
        </div>
        <div class="task-image-upload__preview-tools" aria-label="图片预览操作">
          <button type="button" aria-label="缩小" @click="zoomOut">−</button>
          <span>{{ Math.round(previewScale * 100) }}%</span>
          <button type="button" aria-label="放大" @click="zoomIn">＋</button>
          <button type="button" aria-label="旋转图片" @click="rotatePreview">↻</button>
          <button type="button" aria-label="还原图片" @click="resetPreview">还原</button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { Delete, UploadFilled, View } from '@element-plus/icons-vue'

const props = defineProps({
  fileList: { type: Array, default: () => [] },
  limit: { type: Number, default: 3 },
  httpRequest: { type: Function, required: true },
  onRemove: { type: Function, required: true },
})

const previewVisible = ref(false)
const previewUrl = ref('')
const previewName = ref('')
const previewScale = ref(1)
const previewRotation = ref(0)
const previewOffset = ref({ x: 0, y: 0 })
const panState = ref(null)
const activePointers = new Map()
let pinchState = null

function setPreviewChromeHidden(hidden) {
  document.body.classList.toggle('image-preview-open', hidden)
  document.querySelectorAll('.mobile-tabbar').forEach(node => {
    if (hidden) node.style.setProperty('display', 'none', 'important')
    else node.style.removeProperty('display')
  })
}
watch(previewVisible, visible => setPreviewChromeHidden(visible))
onUnmounted(() => setPreviewChromeHidden(false))

const previewImageStyle = computed(() => ({
  transform: `translate3d(${previewOffset.value.x}px, ${previewOffset.value.y}px, 0) rotate(${previewRotation.value}deg) scale(${previewScale.value})`,
  cursor: panState.value || pinchState ? 'grabbing' : 'grab',
  transition: panState.value || pinchState ? 'none' : 'transform 0.18s ease',
}))

function resolveFileUrl(file) {
  if (file?.url) return file.url
  if (file?.path) {
    const normalized = String(file.path).replace(/\\/g, '/').replace(/^\/+/, '')
    return `/uploads/${normalized.replace(/^uploads\//, '')}`
  }
  return ''
}

function openPreview(file) {
  previewUrl.value = resolveFileUrl(file)
  previewName.value = file?.name || '签到图片'
  resetPreview()
  previewVisible.value = true
}

function clampScale(value) {
  return Math.min(5, Math.max(0.25, Number(value) || 1))
}

function zoomIn() {
  previewScale.value = clampScale(previewScale.value + 0.25)
}

function zoomOut() {
  previewScale.value = clampScale(previewScale.value - 0.25)
}

function rotatePreview() {
  previewRotation.value = (previewRotation.value + 90) % 360
}

function resetPreview() {
  previewScale.value = 1
  previewRotation.value = 0
  previewOffset.value = { x: 0, y: 0 }
  panState.value = null
  activePointers.clear()
  pinchState = null
}

function handleWheel(event) {
  const delta = event.deltaY < 0 ? 0.2 : -0.2
  previewScale.value = clampScale(previewScale.value + delta)
}

function startPan(event) {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  event.currentTarget?.setPointerCapture?.(event.pointerId)
  activePointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (activePointers.size >= 2) {
    const points = [...activePointers.values()]
    pinchState = { distance: pointerDistance(points), scale: previewScale.value }
    panState.value = null
  } else {
    panState.value = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, offsetX: previewOffset.value.x, offsetY: previewOffset.value.y }
  }
}

function movePan(event) {
  if (!activePointers.has(event.pointerId)) return
  activePointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (activePointers.size >= 2) {
    const points = [...activePointers.values()]
    if (!pinchState) pinchState = { distance: pointerDistance(points), scale: previewScale.value }
    previewScale.value = clampScale(pinchState.scale * (pointerDistance(points) / Math.max(pinchState.distance, 1)))
    return
  }
  if (!panState.value || panState.value.pointerId !== event.pointerId) return
  previewOffset.value = {
    x: panState.value.offsetX + event.clientX - panState.value.x,
    y: panState.value.offsetY + event.clientY - panState.value.y,
  }
}

function endPan(event) {
  activePointers.delete(event.pointerId)
  if (activePointers.size < 2) {
    pinchState = null
    const remaining = [...activePointers.entries()][0]
    if (remaining) {
      const [pointerId, point] = remaining
      panState.value = { pointerId, x: point.x, y: point.y, offsetX: previewOffset.value.x, offsetY: previewOffset.value.y }
    }
  }
  if (panState.value?.pointerId === event.pointerId) panState.value = null
}

function pointerDistance(points) {
  const [first, second] = points
  return Math.hypot(second.x - first.x, second.y - first.y)
}

function removeFile(file) {
  props.onRemove(file, props.fileList)
}

function isImage(file) {
  return file instanceof File && (file.type?.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp)$/i.test(file.name || ''))
}

function addFile(file) {
  if (!isImage(file) || props.fileList.length >= props.limit) return
  props.httpRequest({ file })
}

function handlePaste(event) {
  const file = Array.from(event.clipboardData?.items || [])
    .find(item => item.kind === 'file' && item.type.startsWith('image/'))
    ?.getAsFile()
  if (file) addFile(file)
}

function handleDrop(event) {
  const file = Array.from(event.dataTransfer?.files || []).find(isImage)
  if (file) addFile(file)
}
</script>

<style scoped>
.task-image-upload { width: 100%; min-width: 0; max-width: 100%; }
.task-image-upload__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(132px, 100%), 1fr)); align-items: stretch; gap: 12px; width: 100%; min-width: 0; max-width: 620px; }
.task-image-upload__card, .task-image-upload__trigger { position: relative; min-height: 132px; overflow: hidden; border: 1px solid #dbe7f5; border-radius: 14px; background: #f8fbff; }
.task-image-upload__card { box-shadow: 0 8px 22px rgb(37 99 235 / 8%); }
.task-image-upload__image { display: block; width: 100%; height: 98px; object-fit: cover; background: linear-gradient(135deg, #eef6ff, #f8fafc); }
.task-image-upload__filename { overflow: hidden; padding: 8px 10px; color: #526078; font-size: 12px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.task-image-upload__actions { position: absolute; inset: 0 0 34px; display: flex; align-items: center; justify-content: center; gap: 8px; opacity: 0; background: rgb(9 23 45 / 72%); backdrop-filter: blur(3px); transition: opacity 0.2s ease; }
.task-image-upload__card:hover .task-image-upload__actions, .task-image-upload__card:focus-within .task-image-upload__actions { opacity: 1; }
.task-image-upload__actions button { display: inline-flex; align-items: center; gap: 4px; padding: 7px 9px; border: 1px solid rgb(255 255 255 / 32%); border-radius: 8px; color: #fff; background: rgb(255 255 255 / 12%); cursor: pointer; }
.task-image-upload__actions button:hover { background: rgb(59 130 246 / 82%); }
.task-image-upload__actions button.is-danger:hover { background: rgb(239 68 68 / 88%); }
.task-image-upload__uploader { width: 100%; min-height: 132px; }
.task-image-upload__uploader :deep(.el-upload), .task-image-upload__uploader :deep(.el-upload-dragger) { box-sizing: border-box; width: 100%; height: 100%; min-height: 132px; padding: 0; border: 0; background: transparent; }
.task-image-upload__trigger { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; color: #64748b; border-style: dashed; cursor: pointer; transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease; }
.task-image-upload__trigger .el-icon { margin-bottom: 8px; color: #3b82f6; font-size: 26px; }
.task-image-upload__trigger strong { color: #334155; font-size: 13px; }
.task-image-upload__trigger span { margin-top: 4px; font-size: 11px; }
.task-image-upload__trigger:hover { color: #2563eb; border-color: #60a5fa; background: #eff6ff; }
</style>

<style>
.task-image-preview-overlay { background: rgb(71 85 105 / 58%) !important; }
.image-preview-open { overflow: hidden !important; }
.image-preview-open .mobile-tabbar { display: none !important; }
.task-image-preview-overlay { position: fixed; inset: 0; width: 100vw; height: 100dvh; padding: 0; }
.task-image-preview-dialog.el-dialog.is-fullscreen { position: fixed; inset: 0; width: 100vw; height: 100dvh; min-height: 100dvh; max-width: none; margin: 0; padding: 0; overflow: hidden; border: 0; border-radius: 0; background: transparent; box-shadow: none; --el-dialog-bg-color: transparent; }
.task-image-preview-dialog .el-dialog__header { display: none; }
.task-image-preview-dialog .el-dialog__body { width: 100%; height: 100dvh !important; min-height: 100dvh; max-height: none !important; padding: 0; }
.task-image-upload__preview { position: relative; width: 100%; height: 100dvh; min-height: 100dvh; overflow: hidden; background: transparent; }
.task-image-upload__preview-close { position: absolute; z-index: 3; top: max(16px, env(safe-area-inset-top)); right: max(16px, env(safe-area-inset-right)); display: grid; width: 40px; height: 40px; place-items: center; border: 1px solid rgb(255 255 255 / 22%); border-radius: 50%; color: #fff; font-size: 28px; line-height: 1; background: rgb(15 23 42 / 68%); cursor: pointer; }
.task-image-upload__preview-stage { display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; padding: max(24px, env(safe-area-inset-top)) max(20px, env(safe-area-inset-right)) max(24px, env(safe-area-inset-bottom)) max(20px, env(safe-area-inset-left)); box-sizing: border-box; touch-action: none; user-select: none; }
.task-image-upload__preview-stage img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 6px; box-shadow: 0 18px 60px rgb(0 0 0 / 42%); transform-origin: center; user-select: none; }
.task-image-upload__preview-tools { position: absolute; z-index: 3; right: 50%; bottom: max(18px, calc(env(safe-area-inset-bottom) + 10px)); display: flex; align-items: center; gap: 6px; padding: 7px; border: 1px solid rgb(255 255 255 / 18%); border-radius: 999px; background: rgb(15 23 42 / 82%); box-shadow: 0 10px 28px rgb(0 0 0 / 28%); transform: translateX(50%); }
.task-image-upload__preview-tools button { min-width: 34px; height: 32px; padding: 0 8px; border: 0; border-radius: 999px; color: #fff; font-size: 18px; line-height: 1; white-space: nowrap; background: transparent; cursor: pointer; }
.task-image-upload__preview-tools button:last-child { min-width: 48px; font-size: 13px; }
.task-image-upload__preview-tools button:hover { background: rgb(59 130 246 / 78%); }
.task-image-upload__preview-tools span { min-width: 42px; color: #cbd5e1; font-size: 11px; text-align: center; }
@media (max-width: 480px) { .task-image-upload__preview-tools { gap: 2px; } .task-image-upload__preview-tools button { min-width: 30px; padding: 0 6px; } }
</style>
