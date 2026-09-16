<template>
  <el-dialog
    :model-value="modelValue"
    title="选择签到位置"
    width="min(1080px, 96vw)"
    align-center
    append-to-body
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <LocationSearchPanel
      v-model="coordinateText"
      :location-api="locationApi"
      @select-location="handleSelection"
    />
    <div v-if="selected.latitude != null" class="selected-location">
      <div class="selected-location__info">
        <span>已选择位置（地址可手动编辑）</span>
        <el-input
          v-model="selected.address"
          placeholder="可手动修改地址文字"
          size="small"
        />
        <small>{{ selected.latitude.toFixed(6) }}, {{ selected.longitude.toFixed(6) }}</small>
      </div>
      <el-tag type="success">已选点</el-tag>
    </div>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :disabled="selected.latitude == null" @click="confirm">使用此位置</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import LocationSearchPanel from './class-cube/LocationSearchPanel.vue'
import { locationApi } from '../api'
import { parseCoordinates } from '../utils/classCubeTaskForm.js'

const props = defineProps({
  modelValue: Boolean,
  address: { type: String, default: '' },
  latitude: { type: Number, default: null },
  longitude: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'confirm'])
const coordinateText = ref('')
const selected = reactive({ address: '', latitude: null, longitude: null })

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    selected.address = props.address || ''
    selected.latitude = props.latitude
    selected.longitude = props.longitude
    coordinateText.value = props.latitude != null && props.longitude != null
      ? `${props.latitude}, ${props.longitude}`
      : ''
  },
)

watch(coordinateText, (value) => {
  try {
    const coordinate = parseCoordinates(value)
    selected.latitude = coordinate.latitude
    selected.longitude = coordinate.longitude
  } catch {
    if (!selected.address) {
      selected.latitude = null
      selected.longitude = null
    }
  }
})

function handleSelection(result) {
  const latitude = Number(result?.latitude)
  const longitude = Number(result?.longitude)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return
  selected.latitude = latitude
  selected.longitude = longitude
  selected.address = String(result?.address || result?.name || '').trim()
}

function confirm() {
  let coordinate
  try {
    coordinate = parseCoordinates(coordinateText.value)
  } catch {
    coordinate = { latitude: selected.latitude, longitude: selected.longitude }
  }
  emit('confirm', {
    address: selected.address || coordinateText.value,
    latitude: coordinate.latitude,
    longitude: coordinate.longitude,
  })
  emit('update:modelValue', false)
}
</script>

<style scoped>
.selected-location { display:flex; margin-top:14px; padding:12px 14px; align-items:center; justify-content:space-between; gap:12px; border:1px solid #bfdbfe; border-radius:12px; background:#f8fbff; }
.selected-location__info { flex:1; min-width:0; }
.selected-location span,.selected-location small { display:block; }
.selected-location span { color:#94a3b8; font-size:11px; }
.selected-location small { margin-top:4px; color:#64748b; font-size:11px; }
.selected-location :deep(.el-input) { width:100%; margin-top:5px; }
</style>
