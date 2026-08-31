<template>
  <div class="location-search-panel">
    <span class="sr-only" role="status" aria-live="polite">{{ liveMessage }}</span>

    <section class="location-entry-pane" aria-label="位置搜索与坐标设置">
      <div class="location-entry-row">
        <div class="entry-field">
          <div class="coordinate-editor">
            <el-input
              v-model="coordinateValue"
              clearable
              placeholder="纬度, 经度，例如 26.03, 119.21"
              aria-label="签到坐标"
            />
            <el-button plain @click="focusCoordinate">定位坐标</el-button>
          </div>
          <small class="field-tip">支持经纬度自动纠正，也可以点击地图直接选点</small>
        </div>

        <div class="entry-field">
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
          <small class="privacy-tip">{{ mapConfig.search_notice }}</small>
        </div>
      </div>
    </section>

    <section class="search-pane" aria-label="地址搜索结果">
      <p v-if="searchError" class="inline-message is-error" role="alert">
        {{ searchError }}
        <button type="button" @click="searchAddress">重试</button>
      </p>
      <ul v-if="results.length" class="search-results" aria-label="地址搜索结果">
        <li v-for="result in results" :key="result.id" class="result-item">
          <button
            type="button"
            class="result-row"
            :class="{ active: selectedResultId === result.id }"
            @click="selectResult(result)"
          >
            <span class="result-copy">
              <strong>{{ result.name }}</strong>
              <small>{{ result.address }}</small>
              <em>{{ resultMeta(result) }}</em>
            </span>
            <code>{{ formatCoordinate(result.latitude) }}, {{ formatCoordinate(result.longitude) }}</code>
          </button>
        </li>
      </ul>
      <el-empty
        v-else-if="searched && !searching && !searchError"
        description="没有找到匹配地址，请补充城市或区县后重试"
        :image-size="54"
      />

    </section>

    <section class="map-pane" aria-label="地图选点">
      <div
        class="map-shell"
        :class="{
          'is-loading': tileStatus === 'loading',
          'is-error': tileStatus === 'error',
          'is-reduced': reducedMotion,
        }"
      >
        <div
          ref="mapElement"
          class="location-map"
          role="region"
          tabindex="0"
          aria-label="签到位置地图"
          aria-describedby="map-interaction-help"
        />

        <div v-if="!mapReady || tileStatus === 'loading'" class="map-skeleton" aria-hidden="true">
          <span />
          <strong>{{ mapReady ? '正在加载地图…' : '正在初始化地图…' }}</strong>
        </div>

        <div v-if="mapReady" class="map-controls" aria-label="地图控制">
          <button type="button" aria-label="放大地图" @click="zoomMap(1)">＋</button>
          <button type="button" aria-label="缩小地图" @click="zoomMap(-1)">−</button>
          <button
            type="button"
            :class="{ active: locating }"
            :disabled="locating"
            aria-label="定位到当前位置"
            @click="locateDevice"
          >
            {{ locating ? '…' : '◎' }}
          </button>
          <button
            v-if="coarsePointer"
            type="button"
            :class="{ active: mapDraggingEnabled }"
            :aria-label="mapDraggingEnabled ? '关闭单指移动地图' : '启用单指移动地图'"
            @click="toggleMapDragging"
          >
            {{ mapDraggingEnabled ? '锁' : '移' }}
          </button>
        </div>

        <div v-if="mapReady && mapConfig.layers.length > 1" class="layer-control">
          <button
            type="button"
            aria-label="切换地图图层"
            :aria-expanded="layerMenuOpen"
            @click="layerMenuOpen = !layerMenuOpen"
          >
            图层
          </button>
          <div v-if="layerMenuOpen" class="layer-menu">
            <button
              v-for="layer in mapConfig.layers"
              :key="layer.id"
              type="button"
              :class="{ active: activeLayerId === layer.id }"
              @click="activateLayer(layer.id)"
            >
              {{ layer.name }}
            </button>
          </div>
        </div>

        <div v-if="tileStatus === 'error'" class="map-error-panel" role="alert">
          <strong>底图暂时无法加载</strong>
          <span>仍可使用上方坐标输入框完成设置</span>
          <button type="button" @click="retryMapTiles">重新加载地图</button>
        </div>
      </div>

      <p id="map-interaction-help" class="map-instructions">
        <template v-if="coarsePointer">
          单击地图选点，双指缩放；需要单指移动时点击地图左上角“移”。
        </template>
        <template v-else>
          单击地图直接选点；按住 Ctrl 并滚动可缩放地图。
        </template>
      </p>

      <div v-if="pendingDeviceLocation" class="location-confirm">
        <div>
          <strong>已获取设备位置</strong>
          <span>定位精度约 {{ Math.round(pendingDeviceLocation.accuracy) }} 米</span>
          <small v-if="pendingDeviceLocation.accuracy > 200">当前精度较低，建议在室外重试或通过地图微调</small>
        </div>
        <div>
          <el-button @click="cancelDeviceLocation">取消</el-button>
          <el-button type="primary" @click="confirmDeviceLocation">使用此位置</el-button>
        </div>
      </div>

      <p v-if="mapNotice" class="inline-message" :class="`is-${mapNotice.type}`">
        {{ mapNotice.text }}
      </p>
      <p v-if="constrainedNetwork" class="network-notice">
        已启用弱网模式：减少地图缓冲和动画，地址与坐标编辑不受影响。
      </p>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import classCubeApi from '../../api/classCube.js'
import { parseCoordinates } from '../../utils/classCubeTaskForm.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'location-acquired'])

const DEFAULT_MAP_CONFIG = {
  layers: [{
    id: 'openstreetmap',
    name: '标准地图',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
    max_zoom: 19,
  }],
  default_center: { latitude: 35.8617, longitude: 104.1954 },
  default_zoom: 4,
  search_notice: '地址搜索由地图服务处理，请勿输入个人住宅等敏感信息',
}
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
const liveMessage = ref('')
const mapConfig = ref(DEFAULT_MAP_CONFIG)
const mapReady = ref(false)
const tileStatus = ref('loading')
const activeLayerId = ref('')
const layerMenuOpen = ref(false)
const locating = ref(false)
const pendingDeviceLocation = ref(null)
const mapNotice = ref(null)
const coarsePointer = ref(false)
const mapDraggingEnabled = ref(true)
const reducedMotion = ref(false)
const constrainedNetwork = ref(false)

let Leaflet = null
let map = null
let marker = null
let tileLayer = null
let accuracyLayer = null
let resizeObserver = null
let searchController = null
let requestSequence = 0
let locationSequence = 0
let tileErrorCount = 0
let noticeTimer = null
let wheelHintShown = false
let destroyed = false
let coarseMedia = null
let motionMedia = null
let connection = null
const failedLayerIds = new Set()

function formatCoordinate(value) {
  return Number(value).toFixed(6)
}

function normalizeCoordinate(latitude, longitude) {
  return { latitude: Number(latitude), longitude: Number(longitude) }
}

function coordinatesEqual(left, right) {
  if (!left || !right) return false
  return Math.abs(Number(left.latitude) - Number(right.latitude)) < 0.0000001
    && Math.abs(Number(left.longitude) - Number(right.longitude)) < 0.0000001
}

function coordinateDistance(left, right) {
  const radius = 6371000
  const toRadians = value => Number(value) * Math.PI / 180
  const latitudeDelta = toRadians(right.latitude - left.latitude)
  const longitudeDelta = toRadians(right.longitude - left.longitude)
  const firstLatitude = toRadians(left.latitude)
  const secondLatitude = toRadians(right.latitude)
  const haversine = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(firstLatitude) * Math.cos(secondLatitude)
      * Math.sin(longitudeDelta / 2) ** 2
  return 2 * radius * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine))
}

function formatDistance(distance) {
  if (distance < 1000) return `${Math.round(distance)} 米`
  return `${(distance / 1000).toFixed(1)} 公里`
}

function parsedModelValue() {
  if (!String(props.modelValue || '').trim()) return null
  try {
    return parseCoordinates(props.modelValue)
  } catch {
    return null
  }
}

function announce(message) {
  liveMessage.value = ''
  nextTick(() => { liveMessage.value = message })
}

function showMapNotice(text, type = 'info', duration = 3500) {
  if (noticeTimer) window.clearTimeout(noticeTimer)
  mapNotice.value = { text, type }
  if (duration > 0) {
    noticeTimer = window.setTimeout(() => { mapNotice.value = null }, duration)
  }
}

function markerIcon() {
  return Leaflet.divIcon({
    className: 'location-marker-wrapper',
    html: '<span class="location-marker" aria-hidden="true"><i></i></span>',
    iconSize: [44, 48],
    iconAnchor: [22, 44],
  })
}

function updateMapPosition(coordinate, { recenter = false, zoom = 16 } = {}) {
  currentCoordinate.value = normalizeCoordinate(coordinate.latitude, coordinate.longitude)
  if (!map || !Leaflet) return
  const point = Leaflet.latLng(coordinate.latitude, coordinate.longitude)
  if (!marker) {
    marker = Leaflet.marker(point, {
      draggable: false,
      keyboard: true,
      title: '当前签到位置',
      alt: '当前签到位置标记',
      icon: markerIcon(),
    }).addTo(map)
  } else if (!marker.getLatLng().equals(point)) {
    marker.setLatLng(point)
  }
  if (recenter || !map.getBounds().contains(point)) {
    map.setView(point, Math.max(map.getZoom(), zoom), {
      animate: !reducedMotion.value,
    })
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
  const message = options.announceText || `已选择坐标 ${formatCoordinate(coordinate.latitude)}, ${formatCoordinate(coordinate.longitude)}`
  announce(message)
}

function focusCoordinate() {
  const coordinate = parsedModelValue()
  if (!coordinate) {
    searchError.value = '请先输入有效的纬度和经度'
    announce(searchError.value)
    return
  }
  searchError.value = ''
  updateMapPosition(coordinate, { recenter: true, zoom: 16 })
  announce('地图已定位到输入坐标')
}

function resultTypeLabel(result) {
  const labels = {
    university: '学校', school: '学校', college: '学校', hospital: '医院',
    residential: '住宅区', building: '建筑', road: '道路', street: '道路',
    commercial: '商业区', station: '车站', bus_stop: '公交站',
  }
  return labels[result.type] || labels[result.category] || '地点'
}

function resultMeta(result) {
  const parts = [result.city, result.district, resultTypeLabel(result)].filter(Boolean)
  if (currentCoordinate.value) {
    parts.push(`距当前点 ${formatDistance(coordinateDistance(currentCoordinate.value, result))}`)
  }
  return [...new Set(parts)].join(' · ')
}

async function searchAddress() {
  const normalizedQuery = query.value.trim().replace(/\s+/g, ' ')
  if (normalizedQuery.length < 2) {
    searchError.value = '请至少输入 2 个字符搜索地址'
    announce(searchError.value)
    return
  }
  searchController?.abort()
  searchController = new AbortController()
  const sequence = ++requestSequence
  searching.value = true
  searched.value = true
  searchError.value = ''
  announce('正在搜索地址')
  try {
    const response = await classCubeApi.searchLocations(normalizedQuery, 6, {
      signal: searchController.signal,
    })
    if (sequence !== requestSequence) return
    results.value = Array.isArray(response.data) ? response.data : []
    selectedResultId.value = ''
    announce(results.value.length ? `找到 ${results.value.length} 个地址结果` : '没有找到匹配地址')
  } catch (error) {
    if (sequence !== requestSequence || error.code === 'ERR_CANCELED' || error.name === 'CanceledError') return
    results.value = []
    searchError.value = error.message || '地址搜索失败，请稍后重试'
    announce(searchError.value)
  } finally {
    if (sequence === requestSequence) searching.value = false
  }
}

function selectResult(result) {
  applyCoordinate(result.latitude, result.longitude, {
    resultId: result.id,
    recenter: true,
    zoom: 17,
    announceText: `已选择 ${result.name}`,
  })
}

function zoomMap(delta) {
  if (!map) return
  map.setZoom(map.getZoom() + delta, { animate: !reducedMotion.value })
}

function toggleMapDragging() {
  if (!map) return
  mapDraggingEnabled.value = !mapDraggingEnabled.value
  if (mapDraggingEnabled.value) map.dragging.enable()
  else map.dragging.disable()
  announce(mapDraggingEnabled.value ? '已启用单指移动地图' : '已关闭单指移动地图')
}

function locateDevice() {
  if (!navigator.geolocation) {
    showMapNotice('当前浏览器不支持设备定位，请使用地址搜索或手动输入坐标', 'error', 0)
    announce('当前浏览器不支持设备定位')
    return
  }
  const sequence = ++locationSequence
  locating.value = true
  pendingDeviceLocation.value = null
  showMapNotice('正在获取当前位置…', 'info', 0)
  announce('正在获取当前位置')
  navigator.geolocation.getCurrentPosition(
    position => {
      if (destroyed || sequence !== locationSequence) return
      locating.value = false
      const location = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: Math.max(Number(position.coords.accuracy) || 0, 0),
      }
      pendingDeviceLocation.value = location
      showDeviceAccuracy(location)
      showMapNotice(`已获取设备位置，精度约 ${Math.round(location.accuracy)} 米`, location.accuracy > 200 ? 'warning' : 'success', 5000)
      announce(`已获取设备位置，定位精度约 ${Math.round(location.accuracy)} 米`)
    },
    error => {
      if (destroyed || sequence !== locationSequence) return
      locating.value = false
      const messages = {
        1: '未授予位置权限，请在浏览器设置中允许定位，或继续使用地址搜索',
        2: '当前设备暂时无法获取位置，请稍后重试或使用地址搜索',
        3: '获取位置超时，请移动到开阔区域后重试',
      }
      const message = messages[error.code] || '获取当前位置失败，请使用地址搜索或手动输入坐标'
      showMapNotice(message, 'error', 0)
      announce(message)
    },
    { enableHighAccuracy: true, timeout: 10_000, maximumAge: 30_000 },
  )
}

function showDeviceAccuracy(location) {
  if (!map || !Leaflet) return
  if (accuracyLayer) accuracyLayer.remove()
  const point = Leaflet.latLng(location.latitude, location.longitude)
  const circle = Leaflet.circle(point, {
    radius: Math.max(location.accuracy, 8),
    color: location.accuracy > 200 ? '#d97706' : '#2563eb',
    fillColor: location.accuracy > 200 ? '#fbbf24' : '#60a5fa',
    fillOpacity: 0.18,
    weight: 2,
    interactive: false,
  })
  const dot = Leaflet.circleMarker(point, {
    radius: 7,
    color: '#fff',
    fillColor: '#2563eb',
    fillOpacity: 1,
    weight: 3,
    interactive: false,
  })
  accuracyLayer = Leaflet.layerGroup([circle, dot]).addTo(map)
  map.fitBounds(circle.getBounds(), {
    maxZoom: 17,
    animate: !reducedMotion.value,
    padding: [30, 30],
  })
}

function confirmDeviceLocation() {
  if (!pendingDeviceLocation.value) return
  const location = pendingDeviceLocation.value
  applyCoordinate(location.latitude, location.longitude, {
    recenter: true,
    zoom: 17,
    announceText: '已使用设备当前位置',
  })
  emit('location-acquired', { accuracy: Number(location.accuracy.toFixed(1)) })
  pendingDeviceLocation.value = null
  showMapNotice('已使用设备当前位置', 'success')
}

function cancelDeviceLocation() {
  locationSequence += 1
  locating.value = false
  pendingDeviceLocation.value = null
  if (accuracyLayer) {
    accuracyLayer.remove()
    accuracyLayer = null
  }
  showMapNotice('已取消使用设备位置', 'info')
}

function normalizedMapConfig(response) {
  const data = response?.data
  if (!data || !Array.isArray(data.layers) || !data.layers.length) return DEFAULT_MAP_CONFIG
  return {
    ...DEFAULT_MAP_CONFIG,
    ...data,
    layers: data.layers.filter(layer => layer?.url && layer?.id).slice(0, 4),
    default_center: data.default_center || DEFAULT_MAP_CONFIG.default_center,
  }
}

function layerById(layerId) {
  return mapConfig.value.layers.find(layer => layer.id === layerId)
    || mapConfig.value.layers[0]
}

function activateLayer(layerId, { automatic = false } = {}) {
  if (!map || !Leaflet) return
  const layer = layerById(layerId)
  if (!layer) return
  if (!automatic) failedLayerIds.clear()
  if (tileLayer) {
    tileLayer.off()
    tileLayer.remove()
  }
  activeLayerId.value = layer.id
  layerMenuOpen.value = false
  tileStatus.value = 'loading'
  tileErrorCount = 0
  const currentLayerId = layer.id
  tileLayer = Leaflet.tileLayer(layer.url, {
    maxZoom: Number(layer.max_zoom) || 19,
    attribution: layer.attribution || '',
    updateWhenIdle: constrainedNetwork.value,
    updateWhenZooming: !constrainedNetwork.value,
    keepBuffer: constrainedNetwork.value ? 1 : 3,
    detectRetina: false,
  })
  tileLayer.on('tileload', () => {
    if (activeLayerId.value === currentLayerId) tileStatus.value = 'ready'
  })
  tileLayer.on('load', () => {
    if (activeLayerId.value === currentLayerId) {
      tileStatus.value = 'ready'
      tileErrorCount = 0
    }
  })
  tileLayer.on('tileerror', () => {
    if (activeLayerId.value !== currentLayerId) return
    tileErrorCount += 1
    if (tileErrorCount < 3) return
    failedLayerIds.add(currentLayerId)
    const fallback = mapConfig.value.layers.find(item => !failedLayerIds.has(item.id))
    if (fallback) {
      showMapNotice(`当前底图加载失败，已切换到${fallback.name}`, 'warning', 5000)
      activateLayer(fallback.id, { automatic: true })
    } else {
      tileStatus.value = 'error'
      announce('地图底图加载失败，仍可手动输入坐标')
    }
  })
  tileLayer.addTo(map)
  map.setMaxZoom(Number(layer.max_zoom) || 19)
}

function retryMapTiles() {
  const layerId = activeLayerId.value || mapConfig.value.layers[0]?.id
  if (!layerId) return
  failedLayerIds.clear()
  activateLayer(layerId)
  announce('正在重新加载地图')
}

function handleMapWheel(event) {
  if (!map || coarsePointer.value) return
  if (event.ctrlKey) {
    event.preventDefault()
    zoomMap(event.deltaY < 0 ? 1 : -1)
    return
  }
  if (!wheelHintShown) {
    wheelHintShown = true
    showMapNotice('按住 Ctrl 并滚动可缩放地图', 'info')
  }
}

function updateEnvironmentPreferences() {
  coarsePointer.value = Boolean(coarseMedia?.matches)
  reducedMotion.value = Boolean(motionMedia?.matches)
  constrainedNetwork.value = Boolean(connection?.saveData || ['slow-2g', '2g'].includes(connection?.effectiveType))
  if (map) {
    if (coarsePointer.value && !mapDraggingEnabled.value) map.dragging.disable()
    else map.dragging.enable()
  }
}

function handleVisibilityChange() {
  if (!map) return
  if (document.hidden) map.stop()
  else nextTick(() => map?.invalidateSize({ pan: false }))
}

async function initializeMap() {
  if (!mapElement.value || map || destroyed) return
  tileStatus.value = 'loading'
  let configResponse = null
  try {
    const [leafletModule, config] = await Promise.all([
      import('leaflet'),
      classCubeApi.getLocationConfig(),
      import('leaflet/dist/leaflet.css'),
    ])
    Leaflet = leafletModule.default
    configResponse = config
  } catch {
    try {
      const leafletModule = await import('leaflet')
      await import('leaflet/dist/leaflet.css')
      Leaflet = leafletModule.default
    } catch {
      tileStatus.value = 'error'
      announce('地图组件加载失败，仍可手动输入坐标')
      return
    }
  }
  if (destroyed || !mapElement.value || !Leaflet) return
  mapConfig.value = normalizedMapConfig(configResponse)
  const center = mapConfig.value.default_center
  mapDraggingEnabled.value = !coarsePointer.value
  map = Leaflet.map(mapElement.value, {
    center: [center.latitude, center.longitude],
    zoom: Number(mapConfig.value.default_zoom) || 4,
    minZoom: 3,
    maxZoom: 19,
    zoomControl: false,
    scrollWheelZoom: false,
    dragging: mapDraggingEnabled.value,
    touchZoom: true,
    zoomAnimation: !reducedMotion.value,
    fadeAnimation: !reducedMotion.value,
  })
  map.on('click', event => {
    applyCoordinate(event.latlng.lat, event.latlng.lng, {
      recenter: false,
      announceText: '已通过地图点击选择位置',
    })
  })
  mapElement.value.addEventListener('wheel', handleMapWheel, { passive: false })
  activateLayer(mapConfig.value.layers[0]?.id)
  const initialCoordinate = parsedModelValue()
  if (initialCoordinate) updateMapPosition(initialCoordinate, { recenter: true, zoom: 16 })
  resizeObserver = new ResizeObserver(() => map?.invalidateSize({ pan: false }))
  resizeObserver.observe(mapElement.value)
  mapReady.value = true
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
onMounted(() => {
  coarseMedia = window.matchMedia('(pointer: coarse)')
  motionMedia = window.matchMedia('(prefers-reduced-motion: reduce)')
  connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection || null
  coarseMedia.addEventListener?.('change', updateEnvironmentPreferences)
  motionMedia.addEventListener?.('change', updateEnvironmentPreferences)
  connection?.addEventListener?.('change', updateEnvironmentPreferences)
  document.addEventListener('visibilitychange', handleVisibilityChange)
  updateEnvironmentPreferences()
  initializeMap()
})

onBeforeUnmount(() => {
  destroyed = true
  requestSequence += 1
  locationSequence += 1
  searchController?.abort()
  if (noticeTimer) window.clearTimeout(noticeTimer)
  coarseMedia?.removeEventListener?.('change', updateEnvironmentPreferences)
  motionMedia?.removeEventListener?.('change', updateEnvironmentPreferences)
  connection?.removeEventListener?.('change', updateEnvironmentPreferences)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  resizeObserver?.disconnect()
  if (mapElement.value) mapElement.value.removeEventListener('wheel', handleMapWheel)
  tileLayer?.off()
  map?.remove()
  resizeObserver = null
  tileLayer = null
  accuracyLayer = null
  map = null
  marker = null
  Leaflet = null
})
</script>

<style scoped>
.location-search-panel{container-type:inline-size;display:grid;gap:14px;width:100%;min-width:0;padding:12px;border:1px solid #dbeafe;border-radius:15px;background:linear-gradient(145deg,#f8fbff,#fff);box-sizing:border-box}.location-entry-pane{grid-column:1/-1;min-width:0}.location-entry-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.entry-field{display:grid;align-content:start;gap:6px;min-width:0}.search-pane,.map-pane{display:grid;align-content:start;gap:10px;min-width:0}.coordinate-editor,.address-search{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;min-width:0}.field-tip,.privacy-tip{color:#52657f;font-size:12px;line-height:1.55}.privacy-tip{color:#64748b}.inline-message{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0;padding:9px 11px;border-radius:10px;background:#eff6ff;color:#1d4ed8;font-size:13px;line-height:1.45}.inline-message button{border:0;background:transparent;color:inherit;font-weight:700;cursor:pointer}.inline-message.is-error{background:#fef2f2;color:#b91c1c}.inline-message.is-warning{background:#fffbeb;color:#a16207}.inline-message.is-success{background:#ecfdf5;color:#047857}.saved-group{display:grid;gap:6px}.saved-group header{display:flex;align-items:center;justify-content:space-between;gap:8px}.saved-group header strong{color:#334155;font-size:13px}.saved-group header button{border:0;background:transparent;color:#64748b;font-size:12px;cursor:pointer}.saved-list{display:flex;gap:6px;overflow:auto;padding:1px 1px 3px}.saved-list button{display:flex;align-items:center;gap:4px;flex:0 0 auto;max-width:190px;min-height:34px;padding:6px 10px;overflow:hidden;border:1px solid #dbeafe;border-radius:999px;background:#fff;color:#1e40af;font-size:12px;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}.saved-list button:hover{border-color:#60a5fa;background:#eff6ff}.saved-list button span{color:#f59e0b}.search-results{display:grid;gap:7px;max-height:280px;margin:0;padding:2px;overflow:auto;list-style:none}.result-item{min-width:0}.result-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;width:100%;min-height:68px;padding:10px;border:1px solid #e2e8f0;border-radius:11px;background:#fff;color:#334155;text-align:left;cursor:pointer;transition:border-color .18s,box-shadow .18s,transform .18s}.result-row:hover,.result-row.active{border-color:#60a5fa;box-shadow:0 7px 18px rgb(37 99 235 / 12%);transform:translateY(-1px)}.result-copy{display:grid;gap:3px;min-width:0}.result-copy strong{overflow:hidden;color:#172033;font-size:14px;text-overflow:ellipsis;white-space:nowrap}.result-copy small{display:-webkit-box;overflow:hidden;color:#52657f;font-size:12px;line-height:1.45;-webkit-box-orient:vertical;-webkit-line-clamp:2}.result-copy em{overflow:hidden;color:#64748b;font-size:12px;font-style:normal;text-overflow:ellipsis;white-space:nowrap}.result-row code{color:#1d4ed8;font-size:12px;white-space:nowrap}.selection-card{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 11px;border:1px solid #bfdbfe;border-radius:11px;background:#eff6ff}.selection-card>div:first-child{display:grid;gap:2px;min-width:0}.selection-card small{color:#64748b;font-size:12px}.selection-card strong{overflow:hidden;color:#1e3a8a;font-size:14px;text-overflow:ellipsis;white-space:nowrap}.deviation-warning{color:#a16207;font-size:12px}.selection-actions{display:flex;gap:6px;flex:0 0 auto}.selection-actions button{min-height:34px;padding:5px 9px;border:1px solid #bfdbfe;border-radius:8px;background:#fff;color:#1d4ed8;font-size:12px;cursor:pointer}.selection-actions button:disabled{cursor:not-allowed;opacity:.45}.map-shell{position:relative;min-width:0;overflow:hidden;border:1px solid #bfdbfe;border-radius:14px;background:#eaf3ff}.location-map{width:100%;height:380px;min-height:300px}.map-skeleton{position:absolute;z-index:450;inset:0;display:grid;place-content:center;justify-items:center;gap:12px;background:linear-gradient(135deg,#eef5ff,#dcecff);pointer-events:none}.map-skeleton::before,.map-skeleton::after{position:absolute;inset:20% -10%;content:"";border-top:3px solid rgb(96 165 250 / 25%);transform:rotate(-14deg)}.map-skeleton::after{inset:65% -10%;transform:rotate(9deg)}.map-skeleton span{z-index:1;width:26px;height:26px;border:3px solid #bfdbfe;border-top-color:#2563eb;border-radius:50%;animation:map-spin .8s linear infinite}.map-skeleton strong{z-index:1;color:#1e40af;font-size:13px}.map-controls{position:absolute;z-index:600;top:10px;left:10px;display:grid;overflow:hidden;border:1px solid rgb(191 219 254 / 90%);border-radius:11px;background:rgb(255 255 255 / 94%);box-shadow:0 7px 20px rgb(15 23 42 / 15%)}.map-controls button,.layer-control>button{display:grid;width:44px;height:44px;padding:0;place-items:center;border:0;border-bottom:1px solid #dbeafe;background:transparent;color:#1d4ed8;font-size:22px;font-weight:700;cursor:pointer}.map-controls button:last-child{border-bottom:0}.map-controls button:hover,.map-controls button.active,.layer-control>button:hover{background:#dbeafe}.map-controls button:disabled{cursor:wait;opacity:.65}.layer-control{position:absolute;z-index:600;top:10px;right:10px}.layer-control>button{width:auto;min-width:50px;padding:0 10px;border:1px solid #bfdbfe;border-radius:10px;background:rgb(255 255 255 / 94%);font-size:13px;box-shadow:0 7px 20px rgb(15 23 42 / 15%)}.layer-menu{display:grid;gap:3px;min-width:130px;margin-top:6px;padding:6px;border:1px solid #bfdbfe;border-radius:10px;background:rgb(255 255 255 / 96%);box-shadow:0 10px 25px rgb(15 23 42 / 18%)}.layer-menu button{min-height:38px;padding:7px 9px;border:0;border-radius:7px;background:transparent;color:#334155;text-align:left;cursor:pointer}.layer-menu button:hover,.layer-menu button.active{background:#dbeafe;color:#1d4ed8}.map-error-panel{position:absolute;z-index:550;inset:50% auto auto 50%;display:grid;justify-items:center;gap:6px;width:min(300px,calc(100% - 36px));padding:18px;border:1px solid #fecaca;border-radius:14px;background:rgb(255 255 255 / 95%);box-shadow:0 14px 35px rgb(127 29 29 / 15%);text-align:center;transform:translate(-50%,-50%)}.map-error-panel strong{color:#991b1b}.map-error-panel span{color:#64748b;font-size:12px}.map-error-panel button{min-height:38px;padding:7px 13px;border:0;border-radius:8px;background:#2563eb;color:#fff;cursor:pointer}.map-instructions,.network-notice{margin:0;color:#52657f;font-size:12px;line-height:1.55}.network-notice{padding:8px 10px;border-radius:9px;background:#fffbeb;color:#92400e}.location-confirm{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;border:1px solid #bfdbfe;border-radius:12px;background:#eff6ff}.location-confirm>div:first-child{display:grid;gap:2px}.location-confirm strong{color:#1e3a8a;font-size:14px}.location-confirm span,.location-confirm small{color:#52657f;font-size:12px}.location-confirm small{color:#a16207}.location-confirm>div:last-child{display:flex;gap:8px}.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;border:0;clip:rect(0,0,0,0);white-space:nowrap}.location-search-panel :deep(.el-empty){padding:8px 0}.location-search-panel :deep(.el-empty__description){margin-top:4px}.location-search-panel :deep(.el-empty__description p){font-size:12px}.location-search-panel :deep(.leaflet-control-attribution){font-size:10px}.location-search-panel :deep(.location-marker-wrapper){display:grid!important;place-items:center;background:transparent;border:0}.location-search-panel :deep(.location-marker){position:relative;display:block;width:28px;height:28px;border:3px solid #fff;border-radius:50% 50% 50% 0;background:linear-gradient(135deg,#60a5fa,#2563eb);box-shadow:0 5px 12px rgb(37 99 235 / 42%);transform:rotate(-45deg);transition:transform .16s}.location-search-panel :deep(.location-marker i){position:absolute;top:8px;left:8px;width:6px;height:6px;border-radius:50%;background:#fff}.location-search-panel :deep(.leaflet-marker-draggable:active .location-marker){transform:translate(4px,-4px) rotate(-45deg)}.location-search-panel :deep(.leaflet-container){font-family:inherit}.location-search-panel :deep(.leaflet-bar a){color:#2563eb}@keyframes map-spin{to{transform:rotate(360deg)}}
@container(min-width:900px){.location-search-panel{grid-template-columns:minmax(310px,350px) minmax(0,1fr);align-items:start}.location-map{height:440px}.search-results{max-height:330px}}
@media(max-width:720px){.location-entry-row{grid-template-columns:1fr}}
@media(max-width:640px){.location-search-panel{padding:10px}.coordinate-editor,.address-search{grid-template-columns:1fr}.coordinate-editor .el-button,.address-search .el-button{width:100%;min-height:42px}.result-row{grid-template-columns:1fr}.result-row code{white-space:normal}.selection-card,.location-confirm{align-items:stretch;flex-direction:column}.selection-actions,.location-confirm>div:last-child{display:grid;grid-template-columns:1fr 1fr}.selection-actions button,.location-confirm .el-button{width:100%;min-height:42px;margin:0}.location-map{height:clamp(280px,48vh,420px);min-height:260px}.map-instructions,.field-tip,.privacy-tip{font-size:12px}}
.search-results{max-height:155px;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable}.result-row{height:72px;min-height:72px;padding-block:8px;overflow:hidden}.result-copy small{-webkit-line-clamp:1}
.search-results{scrollbar-width:auto;scrollbar-color:#60a5fa #eff6ff}.search-results::-webkit-scrollbar{width:10px}.search-results::-webkit-scrollbar-track{border-radius:999px;background:#eff6ff}.search-results::-webkit-scrollbar-thumb{border:2px solid #eff6ff;border-radius:999px;background:#60a5fa}
@media(max-width:640px){.search-results{max-height:199px}.result-row{height:94px;min-height:94px}}
@media(prefers-reduced-motion:reduce){.result-row,.location-search-panel :deep(.location-marker){transition:none}.map-skeleton span{animation:none}}
</style>
