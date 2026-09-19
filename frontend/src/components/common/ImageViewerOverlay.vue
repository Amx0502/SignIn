<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="iv-overlay"
      @click.self="close"
      @wheel.prevent="handleWheel"
      @dblclick="reset"
    >
      <img
        class="iv-image"
        :src="currentUrl"
        :style="imageStyle"
        alt="图片预览"
        draggable="false"
        @mousedown.prevent="startMousePan"
        @touchstart.passive="handleTouchStart"
        @touchmove="handleTouchMove"
        @touchend="handleTouchEnd"
        @touchcancel="handleTouchEnd"
      />

      <button v-if="urls.length > 1" class="iv-nav iv-nav--prev" type="button" @click.stop="step(-1)">
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <button v-if="urls.length > 1" class="iv-nav iv-nav--next" type="button" @click.stop="step(1)">
        <el-icon><ArrowRight /></el-icon>
      </button>

      <div class="iv-toolbar" @click.stop @wheel.stop.prevent="handleWheel">
        <button type="button" title="缩小" @click="zoomBy(1 / zoomStep)">
          <el-icon><ZoomOut /></el-icon>
        </button>
        <button type="button" title="放大" @click="zoomBy(zoomStep)">
          <el-icon><ZoomIn /></el-icon>
        </button>
        <button type="button" title="原始比例" @click="reset">1:1</button>
        <button type="button" title="向左旋转" @click="rotateBy(-90)">
          <el-icon><RefreshLeft /></el-icon>
        </button>
        <button type="button" title="向右旋转" @click="rotateBy(90)">
          <el-icon><RefreshRight /></el-icon>
        </button>
      </div>

      <button class="iv-close" type="button" title="关闭" @click.stop="close">
        <el-icon><Close /></el-icon>
      </button>
      <p class="iv-hint">滚轮或双指缩放 · 拖拽平移 · 双击还原</p>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, Close, RefreshLeft, RefreshRight, ZoomIn, ZoomOut } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  urls: { type: Array, default: () => [] },
  initialIndex: { type: Number, default: 0 },
  minScale: { type: Number, default: 0.2 },
  maxScale: { type: Number, default: 8 },
  zoomStep: { type: Number, default: 1.25 },
})
const emit = defineEmits(['update:modelValue'])

const index = ref(0)
const scale = ref(1)
const rotate = ref(0)
const offsetX = ref(0)
const offsetY = ref(0)
const dragging = ref(false)

const currentUrl = computed(() => props.urls[index.value] || '')
const imageStyle = computed(() => ({
  transform: `translate3d(${offsetX.value}px, ${offsetY.value}px, 0) scale(${scale.value}) rotate(${rotate.value}deg)`,
  transition: dragging.value ? 'none' : 'transform .18s ease-out',
  cursor: dragging.value ? 'grabbing' : 'grab',
}))

function clampScale(value) {
  return Math.min(props.maxScale, Math.max(props.minScale, Number(value.toFixed(3))))
}

function reset() {
  scale.value = 1
  rotate.value = 0
  offsetX.value = 0
  offsetY.value = 0
}

function zoomBy(factor) {
  scale.value = clampScale(scale.value * factor)
}

function rotateBy(deg) {
  rotate.value = (rotate.value + deg) % 360
}

function step(delta) {
  if (!props.urls.length) return
  index.value = (index.value + delta + props.urls.length) % props.urls.length
  reset()
}

// 以某个屏幕坐标点为锚点缩放，保证指针下的画面位置不跳动
function zoomAt(factor, clientX, clientY) {
  const next = clampScale(scale.value * factor)
  if (next === scale.value) return
  const target = clientX != null && clientY != null
    ? { x: clientX, y: clientY }
    : { x: window.innerWidth / 2, y: window.innerHeight / 2 }
  const ratio = next / scale.value
  offsetX.value = target.x - window.innerWidth / 2 - ratio * (target.x - window.innerWidth / 2 - offsetX.value)
  offsetY.value = target.y - window.innerHeight / 2 - ratio * (target.y - window.innerHeight / 2 - offsetY.value)
  scale.value = next
}

function handleWheel(event) {
  const delta = event.deltaY > 0 ? 1 / 1.12 : 1.12
  zoomAt(delta, event.clientX, event.clientY)
}

// 鼠标拖拽平移
function startMousePan(event) {
  const startX = event.clientX
  const startY = event.clientY
  const originX = offsetX.value
  const originY = offsetY.value
  dragging.value = true
  const move = (ev) => {
    offsetX.value = originX + (ev.clientX - startX)
    offsetY.value = originY + (ev.clientY - startY)
  }
  const end = () => {
    dragging.value = false
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', end)
  }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', end)
}

// 触摸：单指平移，双指捏合缩放（并支持双指整体拖动）
let touchState = null

function touchDistance(touches) {
  const [a, b] = touches
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)
}

function touchCenter(touches) {
  const [a, b] = touches
  return { x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 }
}

function handleTouchStart(event) {
  if (event.touches.length === 1) {
    const touch = event.touches[0]
    touchState = {
      mode: 'pan',
      startX: touch.clientX,
      startY: touch.clientY,
      originX: offsetX.value,
      originY: offsetY.value,
    }
    dragging.value = true
    return
  }
  if (event.touches.length >= 2) {
    dragging.value = true
    touchState = {
      mode: 'pinch',
      distance: touchDistance(event.touches),
      center: touchCenter(event.touches),
      scale: scale.value,
      originX: offsetX.value,
      originY: offsetY.value,
    }
  }
}

function handleTouchMove(event) {
  if (!touchState) return
  if (touchState.mode === 'pan' && event.touches.length === 1) {
    const touch = event.touches[0]
    offsetX.value = touchState.originX + (touch.clientX - touchState.startX)
    offsetY.value = touchState.originY + (touch.clientY - touchState.startY)
    return
  }
  if (event.touches.length >= 2 && touchState.mode === 'pinch') {
    const distance = touchDistance(event.touches)
    const center = touchCenter(event.touches)
    if (!touchState.distance) return
    const next = clampScale(touchState.scale * (distance / touchState.distance))
    const ratio = next / touchState.scale
    const baseX = window.innerWidth / 2
    const baseY = window.innerHeight / 2
    offsetX.value = center.x - baseX - ratio * (touchState.center.x - baseX - touchState.originX)
    offsetY.value = center.y - baseY - ratio * (touchState.center.y - baseY - touchState.originY)
    scale.value = next
  }
}

function handleTouchEnd(event) {
  if (event.touches && event.touches.length >= 1) return
  touchState = null
  dragging.value = false
}

function handleKeydown(event) {
  if (event.key === 'Escape') close()
  if (event.key === '+' || event.key === '=') zoomBy(props.zoomStep)
  if (event.key === '-') zoomBy(1 / props.zoomStep)
}

function close() {
  emit('update:modelValue', false)
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      index.value = Math.min(Math.max(props.initialIndex, 0), Math.max(props.urls.length - 1, 0))
      reset()
      document.addEventListener('keydown', handleKeydown)
      document.body.style.overflow = 'hidden'
      return
    }
    document.removeEventListener('keydown', handleKeydown)
    document.body.style.overflow = ''
    touchState = null
    dragging.value = false
  },
)

watch(() => props.initialIndex, (value) => {
  if (props.modelValue) index.value = value
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.iv-overlay{position:fixed;inset:0;z-index:3000;display:flex;align-items:center;justify-content:center;background:rgb(15 23 42 / 88%);backdrop-filter:blur(2px);touch-action:none;overflow:hidden}
.iv-image{max-width:92vw;max-height:88vh;object-fit:contain;user-select:none;-webkit-user-drag:none;will-change:transform}
.iv-toolbar{position:fixed;bottom:22px;left:50%;display:flex;align-items:center;gap:4px;padding:6px 10px;border-radius:999px;background:rgb(51 65 85 / 82%);transform:translateX(-50%)}
.iv-toolbar button{display:grid;width:34px;height:34px;place-items:center;border:0;border-radius:50%;background:transparent;color:#f8fafc;font-size:15px;cursor:pointer;transition:background .18s,color .18s}
.iv-toolbar button:hover{background:rgb(148 163 184 / 30%);color:#fff}
.iv-close{position:fixed;top:18px;right:20px;display:grid;width:40px;height:40px;place-items:center;border:0;border-radius:50%;background:rgb(51 65 85 / 70%);color:#f8fafc;font-size:18px;cursor:pointer}
.iv-close:hover{background:rgb(148 163 184 / 45%)}
.iv-nav{position:fixed;top:50%;display:grid;width:42px;height:42px;place-items:center;border:0;border-radius:50%;background:rgb(51 65 85 / 70%);color:#f8fafc;font-size:18px;cursor:pointer;transform:translateY(-50%)}
.iv-nav:hover{background:rgb(148 163 184 / 45%)}
.iv-nav--prev{left:18px}
.iv-nav--next{right:18px}
.iv-hint{position:fixed;bottom:70px;left:50%;margin:0;color:rgb(226 232 240 / 78%);font-size:12px;transform:translateX(-50%)}
@media (max-width:640px){
  .iv-hint{display:none}
  .iv-nav{width:36px;height:36px}
}
</style>
