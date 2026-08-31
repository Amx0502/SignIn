<template>
  <div class="location-search-panel">
    <div class="coordinate-editor">
      <el-input
        v-model="coordinateValue"
        clearable
        placeholder="纬度, 经度，例如 26.03, 119.21"
        aria-label="签到坐标"
      />
      <el-button plain @click="focusCoordinate">定位坐标</el-button>
    </div>
    <small class="field-tip">支持经纬度自动纠正，也可以点击地图或拖动标记选点</small>

    <div class="address-search">
      <el-input
        v-model="query"
        clearable
        maxlength="200"
        placeholder="搜索学校、建筑、道路或详细地址"
        aria-label="搜索地址"
        @keyup.enter="searchAddress"
      />
      <el-button type="primary" :loading="searching" @click="searchAddress">
        搜索地址
      </el-button>
    </div>

    <p v-if="searchError" class="search-error">{{ searchError }}</p>
    <div v-if="results.length" class="search-results" role="listbox" aria-label="地址搜索结果">
      <button
        v-for="result in results"
        :key="result.id"
        type="button"
        class="result-row"
        :class="{ active: selectedResultId === result.id }"
        role="option"
        :aria-selected="selectedResultId === result.id"
        @click="selectResult(result)"
      >
        <span>
          <strong>{{ result.name }}</strong>
          <small>{{ result.address }}</small>
        </span>
        <code>{{ formatCoordinate(result.latitude) }}, {{ formatCoordinate(result.longitude) }}</code>
      </button>
    </div>
    <el-empty
      v-else-if="searched && !searching && !searchError"
      description="没有找到匹配地址，请补充城市或区县后重试"
      :image-size="54"
    />

    <div class="map-shell">
      <div ref="mapElement" class="location-map" aria-label="签到位置地图" />
    </div>
  </div>
</template>

<script setup>
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import classCubeApi from '../../api/classCube.js'
import { parseCoordinates } from '../../utils/classCubeTaskForm.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const CHINA_CENTER = [35.8617, 104.1954]
const coordinateValue = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value || ''),
})
const mapElement = ref(null)
const query = ref('')
const results = ref([])
const searching = ref(false)
const searched = ref(false)
const searchError = ref('')
const selectedResultId = ref('')
const currentCoordinate = ref(null)
let map = null
let marker = null
let resizeObserver = null
let requestSequence = 0

const markerIcon = L.divIcon({
  className: 'location-marker-wrapper',
  html: '<span class="location-marker"><i></i></span>',
  iconSize: [30, 40],
  iconAnchor: [15, 38],
})

function formatCoordinate(value) {
  return Number(value).toFixed(6)
}

function normalizeCoordinate(latitude, longitude) {
  return {
    latitude: Number(latitude),
    longitude: Number(longitude),
  }
}

function coordinatesEqual(left, right) {
  if (!left || !right) return false
  return Math.abs(left.latitude - right.latitude) < 0.0000001
    && Math.abs(left.longitude - right.longitude) < 0.0000001
}

function updateMapPosition(coordinate, { recenter = false, zoom = 16 } = {}) {
  currentCoordinate.value = coordinate
  if (!map) return
  const point = L.latLng(coordinate.latitude, coordinate.longitude)
  if (!marker) {
    marker = L.marker(point, { draggable: true, icon: markerIcon }).addTo(map)
    marker.on('dragend', () => {
      const position = marker.getLatLng()
      applyCoordinate(position.lat, position.lng)
    })
  } else if (!marker.getLatLng().equals(point, 0.01)) {
    marker.setLatLng(point)
  }
  if (recenter || !map.getBounds().contains(point)) {
    map.setView(point, Math.max(map.getZoom(), zoom), { animate: true })
  }
}

function applyCoordinate(latitude, longitude, options = {}) {
  const coordinate = normalizeCoordinate(latitude, longitude)
  emit(
    'update:modelValue',
    `${formatCoordinate(coordinate.latitude)}, ${formatCoordinate(coordinate.longitude)}`,
  )
  selectedResultId.value = options.resultId || ''
  updateMapPosition(coordinate, {
    recenter: options.recenter !== false,
    zoom: options.zoom || 16,
  })
}

function parsedModelValue() {
  if (!String(props.modelValue || '').trim()) return null
  try {
    return parseCoordinates(props.modelValue)
  } catch {
    return null
  }
}

function focusCoordinate() {
  const coordinate = parsedModelValue()
  if (!coordinate) {
    searchError.value = '请先输入有效的纬度和经度'
    return
  }
  searchError.value = ''
  updateMapPosition(coordinate, { recenter: true, zoom: 16 })
}

async function searchAddress() {
  const normalizedQuery = query.value.trim().replace(/\s+/g, ' ')
  if (normalizedQuery.length < 2) {
    searchError.value = '请至少输入 2 个字符搜索地址'
    return
  }
  const sequence = ++requestSequence
  searching.value = true
  searched.value = true
  searchError.value = ''
  try {
    const response = await classCubeApi.searchLocations(normalizedQuery, 6)
    if (sequence !== requestSequence) return
    results.value = Array.isArray(response.data) ? response.data : []
    selectedResultId.value = ''
  } catch (error) {
    if (sequence !== requestSequence) return
    results.value = []
    searchError.value = error.message || '地址搜索失败，请稍后重试'
  } finally {
    if (sequence === requestSequence) searching.value = false
  }
}

function selectResult(result) {
  applyCoordinate(result.latitude, result.longitude, {
    resultId: result.id,
    recenter: true,
    zoom: 17,
  })
}

function initializeMap() {
  if (!mapElement.value || map) return
  map = L.map(mapElement.value, {
    center: CHINA_CENTER,
    zoom: 4,
    minZoom: 3,
    maxZoom: 19,
    zoomControl: true,
  })
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
  }).addTo(map)
  map.on('click', event => {
    applyCoordinate(event.latlng.lat, event.latlng.lng, {
      recenter: false,
    })
  })
  const initialCoordinate = parsedModelValue()
  if (initialCoordinate) {
    updateMapPosition(initialCoordinate, { recenter: true, zoom: 16 })
  }
  resizeObserver = new ResizeObserver(() => map?.invalidateSize({ pan: false }))
  resizeObserver.observe(mapElement.value)
  nextTick(() => map?.invalidateSize({ pan: false }))
}

watch(
  () => props.modelValue,
  () => {
    const coordinate = parsedModelValue()
    if (!coordinate) {
      currentCoordinate.value = null
      if (marker && !String(props.modelValue || '').trim()) {
        marker.remove()
        marker = null
      }
      return
    }
    if (!coordinatesEqual(currentCoordinate.value, coordinate)) {
      selectedResultId.value = ''
      updateMapPosition(coordinate, { recenter: true, zoom: 16 })
    }
  },
)

onMounted(initializeMap)
onBeforeUnmount(() => {
  requestSequence += 1
  resizeObserver?.disconnect()
  resizeObserver = null
  map?.remove()
  map = null
  marker = null
})
</script>

<style scoped>
.location-search-panel{display:grid;gap:10px;width:100%;min-width:0;padding:12px;border:1px solid #dbeafe;border-radius:15px;background:linear-gradient(145deg,#f8fbff,#fff);box-sizing:border-box}.coordinate-editor,.address-search{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;min-width:0}.field-tip{margin-top:-4px;color:#64748b;font-size:11px;line-height:1.5}.search-error{margin:0;padding:8px 10px;border-radius:9px;background:#fef2f2;color:#dc2626;font-size:12px}.search-results{display:grid;gap:6px;max-height:190px;overflow:auto;padding:2px}.result-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;width:100%;padding:10px;border:1px solid #e2e8f0;border-radius:11px;background:#fff;color:#334155;text-align:left;cursor:pointer;transition:border-color .18s,box-shadow .18s,transform .18s}.result-row:hover,.result-row.active{border-color:#60a5fa;box-shadow:0 7px 18px rgb(37 99 235 / 12%);transform:translateY(-1px)}.result-row span{display:grid;gap:3px;min-width:0}.result-row strong,.result-row small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.result-row strong{color:#172033;font-size:13px}.result-row small{color:#64748b;font-size:11px}.result-row code{color:#2563eb;font-size:10px;white-space:nowrap}.map-shell{position:relative;min-width:0;overflow:hidden;border:1px solid #bfdbfe;border-radius:14px;background:#eaf3ff}.location-map{width:100%;height:380px;min-height:300px}.location-search-panel :deep(.el-empty){padding:8px 0}.location-search-panel :deep(.el-empty__description){margin-top:4px}.location-search-panel :deep(.el-empty__description p){font-size:11px}.location-search-panel :deep(.leaflet-control-attribution){font-size:9px}.location-search-panel :deep(.location-marker-wrapper){background:transparent;border:0}.location-search-panel :deep(.location-marker){position:relative;display:block;width:26px;height:26px;border:3px solid #fff;border-radius:50% 50% 50% 0;background:linear-gradient(135deg,#60a5fa,#2563eb);box-shadow:0 5px 14px rgb(37 99 235 / 45%);transform:rotate(-45deg)}.location-search-panel :deep(.location-marker i){position:absolute;top:7px;left:7px;width:6px;height:6px;border-radius:50%;background:#fff}.location-search-panel :deep(.leaflet-container){font-family:inherit}.location-search-panel :deep(.leaflet-bar a){color:#2563eb}
@media(max-width:640px){.location-search-panel{padding:10px}.coordinate-editor,.address-search{grid-template-columns:1fr}.coordinate-editor .el-button,.address-search .el-button{width:100%}.result-row{grid-template-columns:1fr}.result-row code{white-space:normal}.location-map{height:300px;min-height:260px}}
</style>
