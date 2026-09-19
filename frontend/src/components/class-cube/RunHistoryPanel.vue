<template>
  <el-card class="run-panel" shadow="never">
    <template #header>
      <div class="panel-head"><div><strong>签到运行记录</strong><small>包含自动任务与课程签到中心的严格结果记录</small></div><el-button :icon="Refresh" @click="applyFilters">刷新记录</el-button></div>
    </template>
    <div class="filters">
      <el-select v-model="filters.account_id" clearable placeholder="全部账号"><el-option v-for="row in accounts" :key="row.id" :value="row.id" :label="row.name || row.remote_user_name" /></el-select>
      <el-select v-model="filters.course_id" clearable placeholder="全部课程"><el-option v-for="row in courses" :key="row.id" :value="row.id" :label="row.name" /></el-select>
      <el-select v-model="filters.task_id" clearable placeholder="全部任务"><el-option v-for="row in tasks" :key="row.id" :value="row.id" :label="row.name" /></el-select>
      <el-select v-model="filters.status" clearable placeholder="全部状态"><el-option v-for="(meta, status) in statuses" :key="status" :value="status" :label="meta.label" /></el-select>
      <el-button type="primary" @click="applyFilters">筛选</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>
    <div class="run-list">
      <article v-for="run in runs" :key="run.id" class="run-row" @click="openDetail(run)">
        <span class="run-mark" :class="run.status"><el-icon><component :is="statusMeta(run.status).icon" /></el-icon></span>
        <div class="run-main">
          <div><strong>{{ taskName(run) }}</strong><span class="run-account">{{ accountName(run) }}</span><el-tag :type="statusMeta(run.status).type" size="small">{{ statusMeta(run.status).label }}</el-tag></div>
          <p>{{ run.message || statusMeta(run.status).tip }}</p>
          <small>{{ formatTime(run.started_at) }} · {{ modeName(run.mode) }} · 签到项 {{ run.remote_item_id }}<template v-if="run.owner_username"> · 系统账号 {{ run.owner_username }}</template></small>
          <code v-if="run.response_summary?.photo_res" class="photo-res">res: {{ run.response_summary.photo_res }}</code>
        </div>
        <el-button v-if="run.status === 'unknown_result' && run.claim_id" type="warning" plain @click.stop="confirmRetry(run)">确认重试</el-button>
        <el-icon class="run-arrow"><ArrowRight /></el-icon>
      </article>
      <el-empty v-if="!runs.length" description="暂无符合条件的运行记录" :image-size="90" />
    </div>
  </el-card>

  <el-drawer v-model="detailVisible" title="运行记录详情" size="min(560px, 92vw)" @opened="() => setupRunMap()" @closed="destroyRunMap">
    <div v-if="currentRun" class="run-detail">
      <div class="detail-row"><span>任务</span><strong>{{ taskName(currentRun) }}</strong></div>
      <div class="detail-row"><span>平台账号</span><strong>{{ accountName(currentRun) }}</strong></div>
      <div class="detail-row"><span>系统账号</span><strong>{{ currentRun.owner_username || '-' }}</strong></div>
      <div v-if="currentRun.owner_remark" class="detail-row"><span>账号备注</span><strong>{{ currentRun.owner_remark }}</strong></div>
      <div class="detail-row"><span>状态</span><el-tag :type="statusMeta(currentRun.status).type">{{ statusMeta(currentRun.status).label }}</el-tag></div>
      <div class="detail-row"><span>签到类型</span><strong>{{ modeName(currentRun.mode) }}</strong></div>
      <div class="detail-row"><span>开始时间</span><strong>{{ formatTime(currentRun.started_at) }}</strong></div>
      <div class="detail-row"><span>结束时间</span><strong>{{ formatTime(currentRun.finished_at) }}</strong></div>
      <div v-if="locationText" class="detail-row detail-row--wide"><span>签到位置</span><p>{{ locationText }}</p></div>
      <div v-if="locationText" class="detail-row detail-row--wide"><span>地图视图</span>
        <div class="map-cell">
          <template v-if="runCoordinate">
            <div class="run-map-wrap">
              <div ref="mapElement" class="run-map"></div>
              <span v-if="mapPending" class="map-pending">地图加载中…</span>
            </div>
            <small v-if="mapNotice" class="map-fallback">{{ mapNotice }}</small>
          </template>
          <div v-else class="map-fallback">该记录未包含有效经纬度坐标，无法展示地图视图</div>
        </div>
      </div>
      <div class="detail-row detail-row--wide"><span>结果说明</span><p>{{ currentRun.message || statusMeta(currentRun.status).tip }}</p></div>
      <div v-if="currentRun.response_summary?.photo_res || currentRun.response_summary?.photo_src" class="detail-row detail-row--wide">
        <span>照片资源</span>
        <div class="photo-cell">
          <div v-if="photoSrcUrl" class="photo-grid">
            <el-image
              class="photo-thumb"
              :src="photoSrcUrl"
              fit="cover"
              @click="openPhotoPreview"
            >
              <template #error>
                <div class="photo-error">图片加载失败，文件可能已被清理</div>
              </template>
            </el-image>
          </div>
          <code v-if="currentRun.response_summary?.photo_res" class="photo-res">res: {{ currentRun.response_summary.photo_res }}</code>
        </div>
      </div>
    </div>
    <ImageViewerOverlay
      v-model="photoPreviewVisible"
      :urls="photoPreviewUrls"
      :initial-index="0"
    />
  </el-drawer>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ArrowRight, CircleCheckFilled, CircleCloseFilled, Clock, Refresh, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ImageViewerOverlay from '../common/ImageViewerOverlay.vue'
import classCubeApi from '../../api/classCube.js'
import { loadTencentMapSdk } from '../../utils/tencentMapSdk.js'

const props = defineProps({
  runs: { type: Array, default: () => [] }, tasks: { type: Array, default: () => [] },
  accounts: { type: Array, default: () => [] }, courses: { type: Array, default: () => [] },
  loadRunsAction: { type: Function, required: true },
  retryClaimAction: { type: Function, required: true },
})
const statuses = {
  success: { label:'成功',type:'success',icon:CircleCheckFilled,tip:'签到成功' },
  already_signed: { label:'已签到',type:'success',icon:CircleCheckFilled,tip:'已经完成签到' },
  waiting_parameter: { label:'等待参数',type:'warning',icon:Clock,tip:'等待补充位置、照片或密码' },
  unknown_result: { label:'结果未知',type:'warning',icon:WarningFilled,tip:'需要人工确认后才能重试' },
  failed: { label:'失败',type:'danger',icon:CircleCloseFilled,tip:'签到执行失败' },
  skipped: { label:'已跳过',type:'info',icon:Clock,tip:'本轮未提交' },
}
const filters = reactive({ account_id:null, course_id:null, task_id:null, status:'' })
const detailVisible = ref(false)
const currentRun = ref(null)
const photoPreviewVisible = ref(false)
const photoPreviewUrls = computed(() => (photoSrcUrl.value ? [photoSrcUrl.value] : []))

function openPhotoPreview() {
  if (photoSrcUrl.value) photoPreviewVisible.value = true
}
const locationText = computed(() => {
  const params = currentRun.value?.response_summary?.parameters
  if (!params) return ''
  const lat = params.latitude, lon = params.longitude
  if (lat == null || lon == null) return ''
  return `${lat}, ${lon}`
})
// 详情地图：解析记录中的经纬度（兼容 parameters 与 location 两个字段），无效坐标返回 null 走兜底展示
const runCoordinate = computed(() => {
  const summary = currentRun.value?.response_summary || {}
  const params = summary.parameters || summary.location || {}
  const latitude = Number(params.latitude)
  const longitude = Number(params.longitude)
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) return null
  if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) return null
  if (latitude === 0 && longitude === 0) return null
  return { latitude, longitude }
})
const mapElement = ref(null)
const mapNotice = ref('')
const mapPending = ref(false)
let runMap = null
let runMapSeq = 0
let runMapKey = ''
let runMapResizeObserver = null
let runMapResizeFrame = 0
let runMapTileTimer = 0
let runMapRetriedFor = ''

function destroyRunMap() {
  runMapSeq += 1
  if (runMapTileTimer) { window.clearTimeout(runMapTileTimer); runMapTileTimer = 0 }
  if (runMapResizeFrame) { window.cancelAnimationFrame(runMapResizeFrame); runMapResizeFrame = 0 }
  runMapResizeObserver?.disconnect()
  runMapResizeObserver = null
  runMap?.destroy?.()
  runMap = null
  runMapKey = ''
  mapPending.value = false
}

function scheduleRunMapResize() {
  if (!runMap) return
  if (runMapResizeFrame) window.cancelAnimationFrame(runMapResizeFrame)
  runMapResizeFrame = window.requestAnimationFrame(() => {
    runMapResizeFrame = 0
    if (!runMap) return
    const center = runMap.getCenter?.()
    if (typeof runMap.resize === 'function') runMap.resize()
    else window.dispatchEvent(new Event('resize'))
    if (center) runMap.setCenter(center)
  })
}

function observeRunMapSize() {
  runMapResizeObserver?.disconnect()
  if (!mapElement.value || typeof ResizeObserver === 'undefined') return
  runMapResizeObserver = new ResizeObserver(() => scheduleRunMapResize())
  runMapResizeObserver.observe(mapElement.value)
}

// 腾讯地图 JavaScript API GL 依赖 WebGL，浏览器禁用硬件加速时无法渲染
function webglAvailable() {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(
      canvas.getContext('webgl2')
      || canvas.getContext('webgl')
      || canvas.getContext('experimental-webgl'),
    )
  } catch {
    return false
  }
}

async function setupRunMap(options = {}) {
  const coordinate = runCoordinate.value
  const key = detailVisible.value && coordinate
    ? `${coordinate.latitude},${coordinate.longitude}`
    : ''
  if (!options.force && key && key === runMapKey && runMap) return
  // 先销毁旧地图（会使旧流程令牌失效），再取本次流程令牌，
  // 否则 destroyRunMap 内部的自增会让 seq 立即过期，导致后续校验恒不通过。
  destroyRunMap()
  const seq = runMapSeq
  if (!key || !mapElement.value) return
  runMapKey = key
  mapNotice.value = ''
  mapPending.value = true
  if (!webglAvailable()) {
    mapPending.value = false
    mapNotice.value = '当前浏览器未启用 WebGL（通常是关闭了硬件加速），无法渲染地图视图'
    return
  }
  try {
    const configResponse = await classCubeApi.getLocationConfig()
    if (seq !== runMapSeq) return
    const config = configResponse?.data || {}
    if (!String(config.map_sdk_key || '').trim()) {
      mapPending.value = false
      mapNotice.value = '后台未配置腾讯地图 JavaScript API Key，无法展示地图视图'
      return
    }
    const TMap = await loadTencentMapSdk({
      key: config.map_sdk_key,
      url: config.map_sdk_url,
    })
    if (seq !== runMapSeq || !mapElement.value) return
    const center = new TMap.LatLng(coordinate.latitude, coordinate.longitude)
    runMap = new TMap.Map(mapElement.value, {
      center,
      zoom: 16,
      pitch: 0,
      rotation: 0,
      showControl: false,
      draggable: false,
      scrollable: false,
      doubleClickZoom: false,
      touchZoomable: false,
    })
    new TMap.MultiMarker({
      map: runMap,
      geometries: [{ id: 'run-location', position: center }],
    })
    observeRunMapSize()
    scheduleRunMapResize()
    // 创建后再次校正尺寸：抽屉动画 / 异步布局都可能在首帧后改变容器大小
    window.setTimeout(() => { if (seq === runMapSeq) scheduleRunMapResize() }, 320)
    if (runMapTileTimer) window.clearTimeout(runMapTileTimer)
    runMap.on?.('tilesloaded', () => {
      if (seq !== runMapSeq) return
      if (runMapTileTimer) { window.clearTimeout(runMapTileTimer); runMapTileTimer = 0 }
      mapPending.value = false
      mapNotice.value = ''
    })
    runMapTileTimer = window.setTimeout(() => {
      if (seq !== runMapSeq || !runMap) return
      // 首次未加载出底图时自动重建一次（部分环境首次创建在未完成布局的容器上会一直空屏）
      if (runMapRetriedFor !== key) {
        runMapRetriedFor = key
        scheduleRunMapResize()
        setupRunMap({ force: true })
        return
      }
      mapPending.value = false
      mapNotice.value = '地图底图加载超时，请检查腾讯地图 Key 的域名白名单配置'
    }, 8_000)
  } catch (error) {
    if (seq !== runMapSeq) return
    runMap = null
    mapPending.value = false
    mapNotice.value = error?.message || '地图加载失败，请检查腾讯地图 Key 配置'
  }
}

// 地图初始化统一由 el-drawer 的 @opened（动画结束后）触发；坐标解析变化只发生在
// openDetail 设置 currentRun 时，此时抽屉尚未打开，若在此建图会因动画中尺寸不稳而灰屏。
onBeforeUnmount(destroyRunMap)
// 兼容老记录：相对路径（class-cube/uid/xxx.jpg）补 /uploads/ 前缀
const photoSrcUrl = computed(() => {
  const src = String(currentRun.value?.response_summary?.photo_src || '').trim()
  if (!src) return ''
  if (/^https?:\/\//.test(src) || src.startsWith('/uploads/')) return src
  return `/uploads/${src.replace(/^\/+/, '')}`
})
function statusMeta(status){return statuses[status]||statuses.failed}
function taskName(run){if(run.source==='course_manual')return '课程手动签到';return props.tasks.find(row=>row.id===run.task_id)?.name||`任务 ${run.task_id}`}
function accountName(run){const account=props.accounts.find(row=>row.id===run.account_id);return run.account_name||account?.name||account?.remote_user_name||(run.account_id?`账号 ${run.account_id}`:'未知账号')}
function modeName(mode){return {qr:'二维码签到',gps:'GPS 签到',gps_photo:'GPS+拍照签到',password:'密码签到'}[mode]||mode||'未知类型'}
function formatTime(value){return value?new Date(value).toLocaleString('zh-CN',{hour12:false}):'—'}
function filterPayload(){return Object.fromEntries(Object.entries(filters).filter(([,value])=>value!==null&&value!==''))}
async function applyFilters(){try{await props.loadRunsAction(filterPayload())}catch(error){ElMessage.error(error.message||'加载运行记录失败')}}
function openDetail(run){currentRun.value = run;detailVisible.value = true}
function resetFilters(){Object.assign(filters,{account_id:null,course_id:null,task_id:null,status:''});applyFilters()}
async function confirmRetry(run){
  try{await ElMessageBox.confirm('该操作仅解除未知结果保护，不代表上次签到失败。确认允许任务再次尝试？','确认重试',{type:'warning'});await props.retryClaimAction(run.claim_id);await applyFilters();ElMessage.success('已允许再次尝试')}
  catch(error){if(!['cancel','close'].includes(error))ElMessage.error(error.message||'确认失败')}
}
</script>

<style scoped>
.run-panel{border:1px solid rgb(191 219 254 / 58%);border-radius:22px;background:rgb(255 255 255 / 84%);box-shadow:0 18px 42px rgb(15 23 42 / 7%);backdrop-filter:blur(18px)}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.panel-head strong,.panel-head small{display:block}.panel-head small{margin-top:4px;color:#64748b;font-size:11px}.filters{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr)) auto auto;gap:10px;margin-bottom:18px}.filters .el-button+.el-button{margin-left:0}.run-list{display:grid;gap:10px;max-height:650px;overflow:auto}.run-row{display:flex;align-items:center;gap:13px;padding:15px;border:1px solid #e2e8f0;border-radius:17px;background:linear-gradient(145deg,#fff,#f8fafc);cursor:pointer;transition:.18s ease}.run-row:hover{border-color:#93c5fd;background:#f8fbff;transform:translateY(-1px)}.run-mark{display:grid;width:44px;height:44px;flex:none;place-items:center;color:#64748b;border-radius:14px;background:#e2e8f0;font-size:21px}.run-mark.success,.run-mark.already_signed{color:#059669;background:#d1fae5}.run-mark.waiting_parameter,.run-mark.unknown_result{color:#d97706;background:#fef3c7}.run-mark.failed{color:#dc2626;background:#fee2e2}.run-main{min-width:0;flex:1}.run-main>div{display:flex;align-items:center;gap:8px}.run-account{color:#2563eb;font-size:12px;font-weight:600}.run-main p{margin:6px 0;color:#475569;font-size:13px;line-height:1.5}.run-main small{color:#64748b;font-size:11px}.photo-res{display:block;max-width:100%;margin-top:7px;overflow-wrap:anywhere;color:#2563eb;font-size:11px;white-space:pre-wrap}
.run-arrow{flex:none;color:#94a3b8}
.run-detail{display:grid;gap:12px}
.detail-row{display:grid;grid-template-columns:90px minmax(0,1fr);align-items:start;gap:10px;padding:12px 14px;border:1px solid #e2e8f0;border-radius:13px;background:#f8fafc}
.detail-row>span{color:#64748b;font-size:12px}
.detail-row strong,.detail-row p{margin:0;overflow-wrap:anywhere;font-size:13px;color:#0f172a}
.detail-row--wide{grid-template-columns:90px minmax(0,1fr)}
.photo-cell{display:grid;gap:6px;min-width:0}
/* 与小小签到保持同款 3 列栅格，但照片占 2 列（约放大一倍） */
.photo-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.photo-grid :deep(.el-image){grid-column:span 2;width:100%;aspect-ratio:1;border-radius:10px;overflow:hidden}
.photo-thumb{cursor:zoom-in}
.photo-error{display:grid;place-items:center;width:100%;height:100%;padding:6px;color:#94a3b8;font-size:10px;line-height:1.4;background:#f1f5f9;text-align:center;overflow-wrap:anywhere}
.photo-cell .photo-res{display:block;overflow-wrap:anywhere;color:#2563eb;font-size:11px;white-space:pre-wrap}
.map-cell{display:grid;gap:6px;min-width:0}
.run-map-wrap{position:relative;height:220px;overflow:hidden;border:1px solid #e2e8f0;border-radius:12px;background:#eef2f7;pointer-events:none;user-select:none}
.run-map{width:100%;height:100%}
.map-pending{position:absolute;inset:0;display:grid;place-items:center;color:#64748b;font-size:12px;background:#eef2f7}
.map-fallback{display:grid;place-items:center;min-height:96px;padding:12px;border:1px dashed #cbd5e1;border-radius:12px;background:#f8fafc;color:#94a3b8;font-size:12px;line-height:1.5;text-align:center}
@media(max-width:1100px){.filters{grid-template-columns:repeat(3,1fr)}}
@media(max-width:650px){
  .panel-head{align-items:center}
  .panel-head>div{min-width:0}
  .panel-head .el-button{flex:none;margin-left:auto}
  .filters{grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}
  .filters .el-button{width:100%;margin:0}
  .run-list{gap:8px}
  .run-row{display:grid;grid-template-columns:36px minmax(0,1fr);align-items:start;gap:10px;padding:11px 12px;border-radius:13px}
  .run-mark{grid-column:1;width:36px;height:36px;border-radius:11px;font-size:18px}
  .run-main{display:grid;grid-column:2;min-width:0}
  .run-main>div{gap:6px;min-width:0}
  .run-main>div strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .run-main>div .el-tag{flex:none;margin-left:auto}
  .run-main p{margin:4px 0 3px;font-size:12px;line-height:1.4}
  .run-main small{display:block;overflow:hidden;text-align:right;text-overflow:ellipsis;white-space:nowrap}
  .photo-res{margin-top:5px}
  .run-row>.el-button{grid-column:2;justify-self:end;margin:2px 0 0}
  .run-arrow{display:none}
}
@media(max-width:420px){
  .panel-head{align-items:stretch;flex-direction:column}
  .panel-head .el-button{width:100%;margin-left:0}
}
</style>
