<template>
  <div
    class="location-search-panel"
    :class="{ 'has-search-content': hasSearchContent }"
  >
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
        </div>
        <div class="entry-field">
          <div class="address-search">
            <el-select
              v-model="selectedProvince"
              filterable
              placeholder="选择省份"
              aria-label="地址搜索省份"
              @change="handleProvinceChange"
            >
              <el-option
                v-for="item in CHINA_PROVINCE_CITIES"
                :key="item.province"
                :label="item.province"
                :value="item.province"
              />
            </el-select>
            <el-select
              v-model="selectedCity"
              filterable
              :disabled="!selectedProvince"
              placeholder="选择城市"
              aria-label="地址搜索城市"
              no-data-text="该省份暂无城市"
              @change="handleCityChange"
            >
              <el-option
                v-for="city in cityOptions"
                :key="city"
                :label="city"
                :value="city"
              />
            </el-select>
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
        </div>
      </div>
    </section>

    <section v-if="hasSearchContent" class="search-pane" aria-label="地址搜索结果">
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
      <div class="map-shell">
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

        <div v-if="tileStatus === 'error'" class="map-error-panel" role="alert">
          <strong>腾讯地图暂时无法加载</strong>
          <span>仍可使用上方坐标输入框完成设置</span>
          <button type="button" @click="retryTencentMap">重新加载地图</button>
        </div>
      </div>

      <p id="map-interaction-help" class="map-instructions">
        单击地图直接选点；可拖动地图，并使用鼠标滚轮或双指缩放。
      </p>

      <p v-if="mapNotice" class="inline-message is-error">
        {{ mapNotice }}
      </p>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import classCubeApi from '../../api/classCube.js'
import { loadTencentMapSdk } from '../../utils/tencentMapSdk.js'
import {
  CHINA_PROVINCE_CITIES,
} from '../../utils/chinaRegions.js'
import { parseCoordinates } from '../../utils/classCubeTaskForm.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const DEFAULT_MAP_CONFIG = {
  map_sdk_url: 'https://map.qq.com/api/gljs',
  map_sdk_key: '',
  default_center: { latitude: 35.8617, longitude: 104.1954 },
  default_zoom: 4,
  min_zoom: 3,
  max_zoom: 20,
}
const coordinateValue = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value || ''),
})
const mapElement = ref(null)
const query = ref('')
const selectedProvince = ref('')
const selectedCity = ref('')
const cityOptions = computed(() => (
  CHINA_PROVINCE_CITIES.find(
    item => item.province === selectedProvince.value,
  )?.cities || []
))
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
const mapNotice = ref('')
const hasSearchContent = computed(() => (
  Boolean(searchError.value) || results.value.length > 0 || searched.value
))

let TMap = null
let map = null
let markerLayer = null
let searchController = null
let requestSequence = 0
let mapLoadTimer = null
let mapResizeObserver = null
let mapResizeFrame = null
let destroyed = false

function resetRegionSearch() {
  searchController?.abort()
  requestSequence += 1
  searching.value = false
  searched.value = false
  searchError.value = ''
  results.value = []
  selectedResultId.value = ''
}

function handleProvinceChange(province) {
  selectedCity.value = ''
  resetRegionSearch()
  announce(`已选择${province}，请继续选择城市`)
}

function handleCityChange(city) {
  resetRegionSearch()
  announce(`搜索范围已切换到${city}`)
}

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

function coordinateForMap(coordinate) {
  return normalizeCoordinate(coordinate.latitude, coordinate.longitude)
}

function resultCoordinateForMap(result) {
  return coordinateForMap(result)
}

function announce(message) {
  liveMessage.value = ''
  nextTick(() => { liveMessage.value = message })
}

function showMapNotice(text) {
  mapNotice.value = text
}

function toTencentLatLng(coordinate) {
  return new TMap.LatLng(
    Number(coordinate.latitude),
    Number(coordinate.longitude),
  )
}

function updateMapPosition(coordinate, { recenter = false, zoom = 16 } = {}) {
  currentCoordinate.value = normalizeCoordinate(coordinate.latitude, coordinate.longitude)
  if (!map || !TMap) return
  const point = toTencentLatLng(coordinate)
  if (!markerLayer) {
    markerLayer = new TMap.MultiMarker({
      id: 'signin-location-marker',
      map,
      geometries: [],
    })
  }
  markerLayer.setGeometries([{
    id: 'selected-location',
    position: point,
    properties: { title: '当前签到位置' },
  }])
  if (recenter) {
    map.setCenter(point)
    map.setZoom(Math.max(Number(map.getZoom()) || 4, Number(zoom) || 16))
  }
}

function applyCoordinate(latitude, longitude, options = {}) {
  const coordinate = normalizeCoordinate(latitude, longitude)
  emit(
    'update:modelValue',
    `${formatCoordinate(coordinate.latitude)}, ${formatCoordinate(coordinate.longitude)}`,
  )
  selectedResultId.value = options.resultId || ''
  updateMapPosition(coordinateForMap(coordinate), {
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
  updateMapPosition(coordinateForMap(coordinate), { recenter: true, zoom: 16 })
  announce('地图已定位到输入坐标')
}

function resultTypeLabel(result) {
  const labels = {
    university: '学校', school: '学校', college: '学校', hospital: '医院',
    residential: '住宅区', building: '建筑', road: '道路', street: '道路',
    commercial: '商业区', station: '车站', bus_stop: '公交站',
  }
  return labels[result.type]
    || labels[result.category]
    || String(result.category || '').split(';').filter(Boolean).at(-1)
    || '地点'
}

function resultMeta(result) {
  const parts = [result.city, result.district, resultTypeLabel(result)].filter(Boolean)
  if (currentCoordinate.value) {
    parts.push(`距当前点 ${formatDistance(coordinateDistance(
      currentCoordinate.value,
      resultCoordinateForMap(result),
    ))}`)
  }
  return [...new Set(parts)].join(' · ')
}

async function searchAddress() {
  const normalizedQuery = query.value.trim().replace(/\s+/g, ' ')
  if (!selectedCity.value) {
    searchError.value = '请先选择省份和城市'
    announce(searchError.value)
    return
  }
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
    const response = await classCubeApi.searchLocations(normalizedQuery, selectedCity.value, 6, {
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

function normalizedMapConfig(response) {
  const data = response?.data
  if (!data || typeof data !== 'object') return DEFAULT_MAP_CONFIG
  return {
    ...DEFAULT_MAP_CONFIG,
    ...data,
    default_center: data.default_center || DEFAULT_MAP_CONFIG.default_center,
    min_zoom: Math.max(3, Number(data.min_zoom) || 3),
    max_zoom: Math.min(20, Number(data.max_zoom) || 20),
  }
}

function handleVisibilityChange() {
  if (!map || document.hidden) return
  scheduleMapResize()
}

function scheduleMapResize() {
  if (!map || destroyed) return
  if (mapResizeFrame) window.cancelAnimationFrame(mapResizeFrame)
  mapResizeFrame = window.requestAnimationFrame(() => {
    mapResizeFrame = null
    if (!map || destroyed) return
    const center = map.getCenter?.()
    if (typeof map.resize === 'function') {
      map.resize()
    } else {
      window.dispatchEvent(new Event('resize'))
    }
    if (center) map.setCenter(center)
  })
}

function observeMapSize() {
  mapResizeObserver?.disconnect()
  if (!mapElement.value || typeof ResizeObserver === 'undefined') return
  mapResizeObserver = new ResizeObserver(() => scheduleMapResize())
  mapResizeObserver.observe(mapElement.value)
}

function destroyMap() {
  if (mapLoadTimer) window.clearTimeout(mapLoadTimer)
  mapLoadTimer = null
  if (mapResizeFrame) window.cancelAnimationFrame(mapResizeFrame)
  mapResizeFrame = null
  mapResizeObserver?.disconnect()
  mapResizeObserver = null
  markerLayer?.setMap?.(null)
  markerLayer = null
  map?.destroy?.()
  map = null
  mapReady.value = false
}

async function retryTencentMap() {
  destroyMap()
  announce('正在重新加载腾讯地图')
  await initializeMap()
}

async function initializeMap() {
  if (!mapElement.value || map || destroyed) return
  tileStatus.value = 'loading'
  mapNotice.value = ''
  try {
    const configResponse = await classCubeApi.getLocationConfig()
    mapConfig.value = normalizedMapConfig(configResponse)
    TMap = await loadTencentMapSdk({
      key: mapConfig.value.map_sdk_key,
      url: mapConfig.value.map_sdk_url,
    })
    if (destroyed || !mapElement.value || !TMap) return
    const initialCoordinate = parsedModelValue()
    const center = coordinateForMap(
      initialCoordinate || mapConfig.value.default_center,
    )
    map = new TMap.Map(mapElement.value, {
      center: toTencentLatLng(center),
      zoom: initialCoordinate ? 16 : Number(mapConfig.value.default_zoom) || 4,
      minZoom: Number(mapConfig.value.min_zoom) || 3,
      maxZoom: Number(mapConfig.value.max_zoom) || 20,
      pitch: 0,
      rotation: 0,
      showControl: false,
      draggable: true,
      scrollable: true,
      touchZoomable: true,
      doubleClickZoom: true,
    })
    map.on('click', event => {
      applyCoordinate(event.latLng.getLat(), event.latLng.getLng(), {
        recenter: false,
        announceText: '已通过地图点击选择位置',
      })
    })
    map.on('tilesloaded', () => {
      if (mapLoadTimer) window.clearTimeout(mapLoadTimer)
      mapLoadTimer = null
      tileStatus.value = 'ready'
    })
    mapLoadTimer = window.setTimeout(() => {
      if (!map || tileStatus.value !== 'loading') return
      tileStatus.value = 'error'
      const message = '腾讯地图底图加载超时，请检查 JavaScript API GL 权限与域名白名单'
      showMapNotice(message)
      announce(message)
    }, 15_000)
    mapReady.value = true
    observeMapSize()
    scheduleMapResize()
    if (initialCoordinate) {
      updateMapPosition(initialCoordinate, { recenter: false, zoom: 16 })
    }
  } catch (error) {
    tileStatus.value = 'error'
    mapReady.value = false
    const message = error?.message || '腾讯地图加载失败，请检查 Key 与域名白名单'
    showMapNotice(message)
    announce(message)
  }
}

watch(
  () => props.modelValue,
  () => {
    const coordinate = parsedModelValue()
    if (!coordinate) {
      currentCoordinate.value = null
      if (markerLayer && !String(props.modelValue || '').trim()) {
        markerLayer.setGeometries([])
      }
      return
    }
    const mapCoordinate = coordinateForMap(coordinate)
    if (!coordinatesEqual(currentCoordinate.value, mapCoordinate)) {
      selectedResultId.value = ''
      updateMapPosition(mapCoordinate, { recenter: true, zoom: 16 })
    }
  },
)
watch(hasSearchContent, () => nextTick(scheduleMapResize))
onMounted(() => {
  document.addEventListener('visibilitychange', handleVisibilityChange)
  initializeMap()
})

onBeforeUnmount(() => {
  destroyed = true
  requestSequence += 1
  searchController?.abort()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  destroyMap()
  TMap = null
})
</script>

<style scoped>
.location-search-panel{container-type:inline-size;display:grid;gap:5px;width:100%;min-width:0;padding:12px;border:1px solid #dbeafe;border-radius:15px;background:linear-gradient(145deg,#f8fbff,#fff);box-sizing:border-box}.location-entry-pane{grid-column:1/-1;min-width:0}.location-entry-row{display:grid;grid-template-columns:minmax(270px,.75fr) minmax(520px,1.25fr);gap:14px}.entry-field{display:grid;align-content:start;gap:6px;min-width:0}.search-pane,.map-pane{display:grid;align-content:start;gap:10px;min-width:0}.coordinate-editor{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;min-width:0}.address-search{display:grid;grid-template-columns:120px 125px minmax(0,1fr) auto;gap:8px;min-width:0}.inline-message{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0;padding:9px 11px;border-radius:10px;background:#eff6ff;color:#1d4ed8;font-size:13px;line-height:1.45}.inline-message button{border:0;background:transparent;color:inherit;font-weight:700;cursor:pointer}.inline-message.is-error{background:#fef2f2;color:#b91c1c}.search-results{display:grid;gap:7px;max-height:280px;margin:0;padding:2px;overflow:auto;list-style:none}.result-item{min-width:0}.result-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;width:100%;min-height:68px;padding:10px;border:1px solid #e2e8f0;border-radius:11px;background:#fff;color:#334155;text-align:left;cursor:pointer;transition:border-color .18s,box-shadow .18s,transform .18s}.result-row:hover,.result-row.active{border-color:#60a5fa;box-shadow:0 7px 18px rgb(37 99 235 / 12%);transform:translateY(-1px)}.result-copy{display:grid;gap:3px;min-width:0}.result-copy strong{overflow:hidden;color:#172033;font-size:14px;text-overflow:ellipsis;white-space:nowrap}.result-copy small{display:-webkit-box;overflow:hidden;color:#52657f;font-size:12px;line-height:1.45;-webkit-box-orient:vertical;-webkit-line-clamp:2}.result-copy em{overflow:hidden;color:#64748b;font-size:12px;font-style:normal;text-overflow:ellipsis;white-space:nowrap}.result-row code{color:#1d4ed8;font-size:12px;white-space:nowrap}.map-shell{position:relative;min-width:0;overflow:hidden;border:1px solid #bfdbfe;border-radius:14px;background:#eaf3ff}.location-map{width:100%;height:380px;min-height:300px}.map-skeleton{position:absolute;z-index:450;inset:0;display:grid;place-content:center;justify-items:center;gap:12px;background:linear-gradient(135deg,#eef5ff,#dcecff);pointer-events:none}.map-skeleton::before,.map-skeleton::after{position:absolute;inset:20% -10%;content:"";border-top:3px solid rgb(96 165 250 / 25%);transform:rotate(-14deg)}.map-skeleton::after{inset:65% -10%;transform:rotate(9deg)}.map-skeleton span{z-index:1;width:26px;height:26px;border:3px solid #bfdbfe;border-top-color:#2563eb;border-radius:50%;animation:map-spin .8s linear infinite}.map-skeleton strong{z-index:1;color:#1e40af;font-size:13px}.map-error-panel{position:absolute;z-index:550;inset:50% auto auto 50%;display:grid;justify-items:center;gap:6px;width:min(300px,calc(100% - 36px));padding:18px;border:1px solid #fecaca;border-radius:14px;background:rgb(255 255 255 / 95%);box-shadow:0 14px 35px rgb(127 29 29 / 15%);text-align:center;transform:translate(-50%,-50%)}.map-error-panel strong{color:#991b1b}.map-error-panel span{color:#64748b;font-size:12px}.map-error-panel button{min-height:38px;padding:7px 13px;border:0;border-radius:8px;background:#2563eb;color:#fff;cursor:pointer}.map-instructions{margin:0;color:#52657f;font-size:12px;line-height:1.55}.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;border:0;clip:rect(0,0,0,0);white-space:nowrap}.location-search-panel :deep(.el-empty){padding:8px 0}.location-search-panel :deep(.el-empty__description){margin-top:4px}.location-search-panel :deep(.el-empty__description p){font-size:12px}@keyframes map-spin{to{transform:rotate(360deg)}}
/* .location-map :deep(a[href*="map.qq.com"][href*="ref=jsapi"]),.location-map :deep(.logo-text){display:none!important} */
@container(min-width:900px){.location-search-panel.has-search-content{grid-template-columns:minmax(310px,350px) minmax(0,1fr);align-items:start}.location-map{height:clamp(480px,60vh,560px)}.search-results{max-height:330px}}
@container(max-width:899px){.location-entry-row{grid-template-columns:minmax(0,1fr)}}
@container(max-width:520px){.coordinate-editor{grid-template-columns:minmax(0,1fr)}.coordinate-editor .el-button{width:100%;min-height:42px}.address-search{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.address-search .el-input{grid-column:1/-1}.address-search>.el-button{grid-column:1/-1;width:100%;min-height:42px}}
@media(max-width:640px){.location-search-panel{padding:10px}.coordinate-editor{grid-template-columns:1fr}.address-search{grid-template-columns:1fr 1fr}.address-search .el-input{grid-column:1/-1}.coordinate-editor .el-button{width:100%;min-height:42px}.address-search>.el-button{grid-column:1/-1;width:100%;min-height:42px}.result-row{grid-template-columns:1fr}.result-row code{white-space:normal}.location-map{height:clamp(280px,48vh,420px);min-height:260px}}
.search-results{max-height:155px;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable}.result-row{height:72px;min-height:72px;padding-block:8px;overflow:hidden}.result-copy small{-webkit-line-clamp:1}
.search-results{scrollbar-width:auto;scrollbar-color:#60a5fa #eff6ff}.search-results::-webkit-scrollbar{width:10px}.search-results::-webkit-scrollbar-track{border-radius:999px;background:#eff6ff}.search-results::-webkit-scrollbar-thumb{border:2px solid #eff6ff;border-radius:999px;background:#60a5fa}
@media(max-width:640px){.search-results{max-height:199px}.result-row{height:94px;min-height:94px}}
@media(prefers-reduced-motion:reduce){.result-row{transition:none}.map-skeleton span{animation:none}}
</style>
