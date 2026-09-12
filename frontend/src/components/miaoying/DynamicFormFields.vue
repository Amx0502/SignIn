<template>
  <div v-if="visibleFields.length" class="dynamic-fields" :class="{ compact }">
    <div class="dynamic-title">
      <div>
        <strong>项目问题</strong>
        <small>请按项目要求填写</small>
      </div>
      <el-tag size="small" type="info">{{ visibleFields.length }} 项</el-tag>
    </div>

    <section
      v-for="field in visibleFields"
      :key="field.key"
      class="dynamic-item"
    >
      <header class="field-heading">
        <div><span v-if="field.required" aria-hidden="true">*</span><strong>{{ field.title }}</strong></div>
        <el-tag v-if="!field.required" size="small" type="info" effect="plain">选填</el-tag>
      </header>
      <div class="field-control" @focusout="validateField(field)">
        <el-input
        v-if="field.control === 'text'"
        :model-value="valueOf(field)"
        clearable
        :maxlength="field.max_length || undefined"
        :placeholder="`请输入${field.title}`"
        @update:model-value="value => updateValue(field, value)"
      />
        <el-rate
        v-else-if="field.unsupported_label === '评分'"
        :model-value="Number(valueOf(field)) || 0"
        :max="5"
        :allow-half="false"
        :show-score="true"
        score-template="{value} 分"
        aria-label="评分（支持半星）"
        @update:model-value="value => updateValue(field, String(value || ''))"
      />
        <div v-else-if="field.unsupported_label === '矩阵单选'" class="matrix-grid" :style="{ gridTemplateColumns: matrixColumns(field) }">
          <div class="matrix-corner"></div><div v-for="option in field.options" :key="`head:${option.value}`" class="matrix-head">{{ option.label }}</div>
          <template v-for="(row, rowIndex) in (field.matrix_rows?.length ? field.matrix_rows : [''])" :key="`row:${rowIndex}`">
            <div class="matrix-row-label">{{ row }}</div>
            <el-radio v-for="(option, colIndex) in field.options" :key="`${rowIndex}:${option.value}`" :model-value="matrixSingleAt(field, rowIndex)" :value="option.value" @update:model-value="value => updateMatrixSingle(field, rowIndex, value)"></el-radio>
          </template>
        </div>
        <div v-else-if="field.unsupported_label === '选课'" class="course-list">
          <button v-for="option in field.options" :key="option.value" type="button" class="course-card" :class="{ 'is-selected': arrayValueOf(field).includes(option.value) }" @click="toggleCourse(field, option.value)">
            <span class="course-card__check">{{ arrayValueOf(field).includes(option.value) ? '✓' : '' }}</span>
            <span><strong>{{ option.label }}</strong><small>{{ courseSchedule(option) }}</small></span>
          </button>
        </div>
        <div v-else-if="field.unsupported_label === '矩阵多选'" class="matrix-grid" :style="{ gridTemplateColumns: matrixColumns(field) }">
          <div class="matrix-corner"></div><div v-for="option in field.options" :key="`head:${option.value}`" class="matrix-head">{{ option.label }}</div>
          <template v-for="(row, rowIndex) in (field.matrix_rows?.length ? field.matrix_rows : [''])" :key="`row:${rowIndex}`">
            <div class="matrix-row-label">{{ row }}</div>
            <el-checkbox v-for="option in field.options" :key="`${rowIndex}:${option.value}`" :model-value="matrixMultiAt(field, rowIndex).includes(option.value)" @update:model-value="() => toggleMatrixMulti(field, rowIndex, option.value)"></el-checkbox>
          </template>
        </div>
        <div v-else-if="field.unsupported_label === '表格'" class="table-field">
          <div v-if="field.options?.length" class="table-grid">
            <div v-for="(option, index) in field.options" :key="option.value" class="table-column">
              <div class="table-header">{{ option.label }}</div>
              <el-select v-if="option.field_type === '1' && option.field_options?.length" :model-value="tableValueOf(field, option, index)" placeholder="请选择" @update:model-value="value => updateTableValue(field, option, index, value)">
                <el-option v-for="item in option.field_options" :key="item" :label="item" :value="String(item)" />
              </el-select>
              <el-input v-else :model-value="tableValueOf(field, option, index)" placeholder="请输入" @update:model-value="value => updateTableValue(field, option, index, value)" />
            </div>
          </div>
          <el-input v-if="!field.options?.length" :model-value="valueOf(field)" type="textarea" :rows="3" placeholder="请填写表格内容" @update:model-value="value => updateValue(field, value)" />
        </div>
        <el-input
        v-else-if="field.unsupported_label === '手机号码'"
        :model-value="valueOf(field)"
        type="tel"
        maxlength="11"
        clearable
        placeholder="请输入11位手机号码"
        @update:model-value="value => updateValue(field, value.replace(/[^0-9]/g, '').slice(0, 11))"
      />
        <el-input
        v-else-if="field.unsupported_label === '身份证号码'"
        :model-value="valueOf(field)"
        maxlength="18"
        clearable
        placeholder="请输入身份证号码"
        @update:model-value="value => updateValue(field, value.toUpperCase().replace(/[^0-9X]/g, '').slice(0, 18))"
      />
        <el-date-picker
        v-else-if="field.unsupported_label === '出生日期' || field.unsupported_label === '日期'"
        :model-value="valueOf(field) || null"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="请选择日期"
        clearable
        style="width: 100%"
        @update:model-value="value => updateValue(field, value || '')"
      />
        <el-input-number
        v-else-if="field.unsupported_label === '年龄' || field.unsupported_label === '数字'"
        :model-value="numberValueOf(field)"
        :min="field.unsupported_label === '年龄' ? 0 : undefined"
        :max="field.unsupported_label === '年龄' ? 150 : undefined"
        :precision="0"
        controls-position="right"
        style="width: 100%"
        @update:model-value="value => updateValue(field, value == null ? '' : String(value))"
      />
        <el-input
        v-else-if="field.unsupported_label === '邮箱'"
        :model-value="valueOf(field)"
        type="email"
        clearable
        placeholder="请输入邮箱地址"
        @update:model-value="value => updateValue(field, value)"
      />
        <div v-else-if="field.unsupported_label === '车牌号'" class="plate-field">
          <el-select
            :model-value="plateProvinceOf(field)"
            placeholder="省"
            filterable
            @update:model-value="value => updatePlate(field, value, plateLetterOf(field), plateNumberOf(field))"
          >
            <el-option v-for="province in plateProvinces" :key="province" :label="province" :value="province" />
          </el-select>
          <el-select
            :model-value="plateLetterOf(field)"
            placeholder="字母"
            filterable
            @update:model-value="value => updatePlate(field, plateProvinceOf(field), value, plateNumberOf(field))"
          >
            <el-option v-for="letter in plateLetters" :key="letter" :label="letter" :value="letter" />
          </el-select>
          <el-input
            :model-value="plateNumberOf(field)"
            maxlength="6"
            clearable
            placeholder="请输入后续号码"
            @update:model-value="value => updatePlate(field, plateProvinceOf(field), plateLetterOf(field), value)"
          />
        </div>
        <el-select
        v-else-if="field.unsupported_label === '省市区' && field.options?.length"
        :model-value="valueOf(field)"
        clearable
        filterable
        placeholder="请选择省市区"
        @update:model-value="value => updateValue(field, value)"
      >
        <el-option v-for="option in field.options" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
        <div v-else-if="field.unsupported_label === '省市区'" class="region-field">
          <el-select :model-value="regionPartsOf(field)[0]" filterable clearable placeholder="省份" @update:model-value="value => updateProvince(field, value)">
            <el-option v-for="province in regionProvinces" :key="province" :label="province" :value="province" />
          </el-select>
          <el-select :model-value="regionPartsOf(field)[1]" filterable allow-create default-first-option clearable placeholder="城市" @update:model-value="value => updateCity(field, value)">
            <el-option v-for="option in regionOptions(field, 1)" :key="option" :label="option" :value="option" />
          </el-select>
          <el-select :model-value="regionPartsOf(field)[2]" filterable allow-create default-first-option clearable placeholder="区县" @update:model-value="value => updateRegion(field, regionPartsOf(field)[0], regionPartsOf(field)[1], value)">
            <el-option v-for="option in regionOptions(field, 2)" :key="option" :label="option" :value="option" />
          </el-select>
        </div>
        <el-input
        v-else-if="field.unsupported_label === '地点'"
        :model-value="locationValue || valueOf(field)"
        readonly
        placeholder="请先在下方地图选择签到位置"
      />
        <el-input
        v-else-if="field.control === 'textarea'"
        :model-value="valueOf(field)"
        type="textarea"
        :rows="3"
        :maxlength="field.max_length || undefined"
        show-word-limit
        :placeholder="`请输入${field.title}`"
        @update:model-value="value => updateValue(field, value)"
      />
        <el-radio-group
        v-else-if="field.control === 'single'"
        :model-value="valueOf(field)"
        @update:model-value="value => updateValue(field, value)"
      >
        <el-radio v-for="option in field.options" :key="option.value" :value="option.value">
          {{ option.label }}
        </el-radio>
      </el-radio-group>
        <el-select
        v-else-if="field.control === 'select'"
        :model-value="valueOf(field)"
        clearable
        :placeholder="`请选择${field.title}`"
        @update:model-value="value => updateValue(field, value)"
      >
        <el-option v-for="option in field.options" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
        <div v-else-if="field.control === 'multiple'" class="multiple-field">
        <el-checkbox-group
          :model-value="arrayValueOf(field)"
          :max="field.max_select || undefined"
          @update:model-value="value => updateValue(field, value)"
        >
          <el-checkbox v-for="option in field.options" :key="option.value" :value="option.value">
            {{ option.label }}
          </el-checkbox>
        </el-checkbox-group>
        <small v-if="field.min_select || field.max_select">
          {{ selectLimit(field) }}
        </small>
        </div>
        <div v-else-if="field.control === 'image'" class="image-field">
          <TaskImageUpload
            :file-list="imageFiles(field)"
            :limit="field.max_select || 9"
            :http-request="options => uploadImage(field, options)"
            :on-remove="file => removeImage(field, file)"
          />
          <small>支持 JPG、PNG、WebP，可点击、拖入或粘贴图片</small>
        </div>
        <QrCodeImageField
          v-else-if="field.unsupported_label === '扫码录入'"
          :model-value="String(valueOf(field) || '')"
          @update:model-value="value => updateValue(field, value)"
        />
        <div v-else-if="field.unsupported_label === '签名' || field.unsupported_label === '拼图' || field.unsupported_label === '文档'" class="image-field">
          <TaskImageUpload
            :file-list="imageFiles(field)"
            :limit="1"
            :accept="field.unsupported_label === '文档' ? '*/*' : 'image/*'"
            :upload-label="field.unsupported_label === '文档' ? '上传文档' : '上传图片'"
            :show-preview="field.unsupported_label !== '文档'"
            :http-request="options => field.unsupported_label === '签名' ? uploadSignature(field, options) : uploadImage(field, options)"
            :on-remove="file => removeImage(field, file)"
          />
          <small v-if="field.unsupported_label === '文档'">支持上传所有文件类型，单个文件不超过 50 MB</small>
          <small v-else>支持 JPG、PNG、WebP，可点击、拖入或粘贴图片</small>
        </div>
        <div v-else-if="field.unsupported_label === '语音' || isVoiceField(field)" class="unsupported-field voice-field">
          <div class="voice-actions">
            <el-button type="primary" plain :loading="recordingStarting && recordingFieldKey === field.key" :class="{ 'is-recording': recordingFieldKey === field.key && !recordingStarting }" @pointerdown="startRecording(field, $event)" @pointerup="stopRecording(field)" @pointercancel="stopRecording(field)" @pointerleave="stopRecording(field)">{{ recordingFieldKey === field.key ? `录音中 ${recordingSeconds}s，松开结束` : '长按录音' }}</el-button>
            <el-upload
            :show-file-list="false"
            :auto-upload="true"
            :http-request="options => uploadFile(field, options)"
            accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg,.amr,.flac"
            ><el-button type="primary" plain>上传语音</el-button></el-upload>
          </div>
          <div v-if="valueOf(field)" class="uploaded-file-value">
            <span>{{ fileDisplayName(valueOf(field)) }}</span>
            <el-button link type="danger" @click="updateValue(field, '')">删除</el-button>
          </div>
          <small>支持长按录音，或上传 MP3、WAV、M4A、AAC、OGG、AMR、FLAC 音频</small>
        </div>
        <div v-else-if="isUploadField(field)" class="unsupported-field">
          <div v-if="field.unsupported_label === '视频'" class="attachment-upload-grid">
            <article v-if="valueOf(field)" class="attachment-card">
              <video :src="attachmentUrl(valueOf(field))" preload="metadata" controls playsinline />
              <div class="attachment-card-name" :title="fileDisplayName(valueOf(field))">{{ fileDisplayName(valueOf(field)) }}</div>
              <el-button class="attachment-remove" type="danger" circle size="small" aria-label="删除视频" @click="updateValue(field, '')">×</el-button>
            </article>
            <el-upload
              v-if="!valueOf(field)"
              class="attachment-upload-trigger"
              :show-file-list="false"
              :auto-upload="true"
              :http-request="options => uploadFile(field, options)"
              accept="video/*"
              drag
            >
              <div class="attachment-upload-content">
                <strong>上传视频</strong>
                <span>{{ valueOf(field) ? '1/1' : '0/1' }}</span>
              </div>
            </el-upload>
          </div>
          <template v-else>
            <el-upload
              :show-file-list="false"
              :auto-upload="true"
              :http-request="options => uploadFile(field, options)"
              :accept="uploadAccept(field)"
            >
              <el-button type="primary" plain>选择{{ field.title }}</el-button>
            </el-upload>
            <div v-if="valueOf(field)" class="uploaded-file-value">
              <span>{{ fileDisplayName(valueOf(field)) }}</span>
              <el-button link type="danger" @click="updateValue(field, '')">删除</el-button>
            </div>
          </template>
        </div>
        <div v-else class="unsupported-field">
          <el-input
            :model-value="valueOf(field)"
            :type="field.title?.includes('多行文本') ? 'textarea' : 'text'"
            :rows="field.title?.includes('多行文本') ? 3 : undefined"
            :maxlength="field.max_length || undefined"
            clearable
            :placeholder="`请手动填写${field.title}`"
            @update:model-value="value => updateValue(field, value)"
          />
        </div>
        <small v-if="fieldError(field)" class="field-error">{{ fieldError(field) }}</small>
      </div>
      <small v-if="field.description" class="field-description">{{ field.description }}</small>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import TaskImageUpload from '../TaskImageUpload.vue'
import QrCodeImageField from '../class-cube/QrCodeImageField.vue'
import { visibleMiaoyingFields } from '../../utils/miaoyingFields.js'
import { CHINA_CITY_DISTRICTS, CHINA_PROVINCE_CITIES } from '../../utils/chinaRegions.js'

const props = defineProps({
  fields: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
  compact: { type: Boolean, default: false },
  imageUploader: { type: Function, default: null },
  locationValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])
const fieldErrors = ref({})
const fullDistricts = ref({})
const recordingFieldKey = ref('')
const recordingSeconds = ref(0)
const recordingStarting = ref(false)
let recorder = null
let recorderStream = null
let recorderChunks = []
let recordingTimer = null

onMounted(async () => {
  try {
    const response = await fetch('https://cdn.jsdelivr.net/gh/modood/Administrative-divisions-of-China@master/dist/pca.json')
    if (!response.ok) return
    const data = await response.json()
    const normalized = {}
    for (const [province, cities] of Object.entries(data || {})) {
      for (const [city, districts] of Object.entries(cities || {})) {
        normalized[city] = Array.isArray(districts) ? districts.map(item => String(item)) : []
      }
    }
    fullDistricts.value = normalized
  } catch {
    // 使用内置常用城市区县数据作为离线兜底。
  }
})

const visibleFields = computed(() => visibleMiaoyingFields(props.fields, props.modelValue))

const valueOf = field => props.modelValue?.[field.key] ?? ''
const numberValueOf = field => {
  const value = Number(valueOf(field))
  return Number.isFinite(value) ? value : undefined
}
const plateProvinces = ['京', '津', '沪', '渝', '冀', '豫', '云', '辽', '黑', '湘', '皖', '鲁', '新', '苏', '浙', '赣', '鄂', '桂', '甘', '晋', '蒙', '陕', '吉', '闽', '贵', '粤', '青', '藏', '川', '宁', '琼']
const plateLetters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')
const plateProvinceOf = field => String(valueOf(field) || '').slice(0, 1)
const plateLetterOf = field => String(valueOf(field) || '').slice(1, 2)
const plateNumberOf = field => String(valueOf(field) || '').slice(2)
const updatePlate = (field, province, letter, number) => {
  const normalized = String(number || '').toUpperCase().replace(/\s/g, '').replace(/[^A-Z0-9挂学警港澳使领民航]/g, '').slice(0, 7)
  updateValue(field, `${province || ''}${letter || ''}${normalized}`)
}
const tableValueOf = (field, option, index) => {
  const value = props.modelValue?.[field.key]
  if (Array.isArray(value)) return value[0]?.[index] || ''
  return value && typeof value === 'object' ? value[option.value || index] || '' : ''
}
const updateTableValue = (field, option, index, value) => {
  const current = props.modelValue?.[field.key]
  const next = Array.isArray(current) ? current.map(row => Array.isArray(row) ? [...row] : row) : [[]]
  if (!Array.isArray(next[0])) next[0] = []
  next[0][index] = value
  updateValue(field, next)
}
const regionProvinces = ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省', '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省', '湖南省', '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省', '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区', '台湾省', '香港特别行政区', '澳门特别行政区']
const regionPartsOf = field => {
  const parts = String(valueOf(field) || '').split(/[\s,，/]+/).filter(Boolean)
  return [parts[0] || '', parts[1] || '', parts.slice(2).join('')]
}
const regionOptions = (field, index) => {
  const options = field.options || []
  const province = regionPartsOf(field)[0]
  const builtIn = index === 1
    ? (CHINA_PROVINCE_CITIES.find(item => item.province === province)?.cities || [])
    : (fullDistricts.value[regionPartsOf(field)[1]] || CHINA_CITY_DISTRICTS[regionPartsOf(field)[1]] || [])
  return [...builtIn, ...options
    .map(option => String(option.label || option.value || '').trim())
    .filter(Boolean)]
    .filter((value, position, list) => list.indexOf(value) === position)
}
const updateRegion = (field, province, city, district) => updateValue(field, [province, city, district].filter(Boolean).join(' '))
const updateProvince = (field, province) => updateRegion(field, province, '', '')
const updateCity = (field, city) => updateRegion(field, regionPartsOf(field)[0], city, '')
watch(
  () => [props.locationValue, props.fields],
  () => {
    const location = String(props.locationValue || '').trim()
    if (!location) return
    const next = { ...props.modelValue }
    let changed = false
    for (const field of props.fields || []) {
      if (field.unsupported_label === '地点' && next[field.key] !== location) {
        next[field.key] = location
        changed = true
      }
    }
    if (changed) emit('update:modelValue', next)
  },
  { immediate: true },
)
const arrayValueOf = field => {
  const value = props.modelValue?.[field.key]
  return Array.isArray(value) ? value : value ? [value] : []
}
const courseSchedule = option => (option.schedule || []).map(item => {
  const rawDay = Number(item.dayOfWeek)
  const dayIndex = rawDay === 7 || rawDay === 0 ? 0 : Math.min(6, Math.max(1, rawDay))
  return `周${['日','一','二','三','四','五','六'][dayIndex]} ${item.startTime || ''}-${item.endTime || ''}`
}).join(' · ') || '时间待定'
const matrixRowsOf = field => field.matrix_rows?.length ? field.matrix_rows : ['']
const matrixColumns = field => `minmax(112px, 1.35fr) repeat(${Math.max(1, field.options?.length || 1)}, minmax(64px, 1fr))`
const matrixSingleAt = (field, rowIndex) => String(valueOf(field) || '').split(';')[rowIndex] || ''
const updateMatrixSingle = (field, rowIndex, value) => {
  const values = matrixRowsOf(field).map((_, index) => matrixSingleAt(field, index))
  values[rowIndex] = String(value)
  updateValue(field, values.join(';'))
}
const matrixMultiAt = (field, rowIndex) => String(valueOf(field) || '').split(';')[rowIndex]?.split(',').filter(Boolean) || []
const toggleMatrixMulti = (field, rowIndex, value) => {
  const values = matrixRowsOf(field).map((_, index) => matrixMultiAt(field, index))
  values[rowIndex] = values[rowIndex].includes(value) ? values[rowIndex].filter(item => item !== value) : [...values[rowIndex], value]
  updateValue(field, values.map(items => items.join(',')).join(';'))
}
const toggleCourse = (field, value) => {
  const selected = arrayValueOf(field)
  updateValue(field, selected.includes(value) ? selected.filter(item => item !== value) : [...selected, value])
}
const updateValue = (field, value) => {
  emit('update:modelValue', { ...props.modelValue, [field.key]: value })
  if (fieldErrors.value[field.key]) validateField(field, value)
}
const fieldError = field => fieldErrors.value[field.key] || ''
const validateField = (field, nextValue = valueOf(field)) => {
  const value = Array.isArray(nextValue) ? nextValue : String(nextValue ?? '').trim()
  let error = ''
  if (field.required && (value === '' || (Array.isArray(value) && !value.length))) {
    error = `请填写${field.title}`
  } else if (value !== '' && !Array.isArray(value)) {
    const text = String(value)
    switch (field.unsupported_label) {
      case '手机号码': if (!/^1\d{10}$/.test(text)) error = '请输入正确的11位手机号码'; break
      case '身份证号码': if (!/^\d{17}[\dXx]$/.test(text)) error = '请输入正确的18位身份证号码'; break
      case '邮箱': if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) error = '请输入正确的邮箱地址'; break
      case '车牌号': if (!/^[\u4e00-\u9fff][A-Z][A-Z0-9]{5,6}$/.test(text)) error = '请输入正确的车牌号码'; break
      case '年龄': if (!/^\d+$/.test(text) || Number(text) > 150) error = '年龄应为0～150的整数'; break
      case '数字': if (!Number.isFinite(Number(text))) error = '请输入有效数字'; break
      case '出生日期': { const date = new Date(`${text}T00:00:00`); if (Number.isNaN(date.getTime()) || date > new Date()) error = '出生日期不能晚于今天'; break }
      default: break
    }
  }
  const next = { ...fieldErrors.value }
  if (error) next[field.key] = error
  else delete next[field.key]
  fieldErrors.value = next
}
const uploadFieldLabels = new Set(['视频', '语音', '文档', '签名', '扫码录入', '拼图'])
const fieldDisplayLabel = field => String(field.unsupported_label || field.title || '').trim()
const isVoiceField = field => /^(语音|录音|音频|声音)/.test(fieldDisplayLabel(field))
const isUploadField = field => uploadFieldLabels.has(fieldDisplayLabel(field)) || isVoiceField(field)
const uploadAccept = field => {
  const label = fieldDisplayLabel(field)
  if (label === '视频') return 'video/*'
  if (label === '语音') return 'audio/*'
  if (label === '文档') return '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt'
  return 'image/*'
}
const fileDisplayName = value => String(value || '').split('/').pop().split('?')[0]
const attachmentUrl = value => {
  const text = String(value || '')
  return /^https?:\/\//.test(text) ? text : `https://oss2.hui51.cn/encode/uploads/${encodeURIComponent(text)}`
}
const uploadFile = async (field, options) => {
  if (!props.imageUploader) {
    options.onError?.(new Error('当前页面未配置文件上传'))
    return
  }
  try {
    const result = await props.imageUploader(options.file)
    const name = String(result?.name || result?.url || '').trim()
    if (!name) throw new Error('秒应未返回文件地址')
    updateValue(field, name)
    options.onSuccess?.(result)
    ElMessage.success('文件上传成功')
  } catch (error) {
    options.onError?.(error)
    ElMessage.error(error?.message || '文件上传失败')
  }
}
const stopRecording = field => {
  if (recorder && recordingFieldKey.value === field.key) recorder.stop()
}
const startRecording = async (field, event) => {
  event?.preventDefault?.()
  event?.currentTarget?.setPointerCapture?.(event.pointerId)
  if (recorder || recordingStarting.value) return
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    ElMessage.error('当前浏览器不支持录音，请改用音频文件上传')
    return
  }
  recordingStarting.value = true
  try {
    recorderStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    recorderChunks = []
    recorder = new MediaRecorder(recorderStream)
    recordingFieldKey.value = field.key
    recordingSeconds.value = 0
    recordingTimer = window.setInterval(() => { recordingSeconds.value += 1 }, 1000)
    recorder.ondataavailable = event => { if (event.data?.size) recorderChunks.push(event.data) }
    recorder.onstop = async () => {
      const mime = recorder?.mimeType || 'audio/webm'
      const extension = mime.includes('mp4') ? 'm4a' : mime.includes('wav') ? 'wav' : 'webm'
      const file = new File([new Blob(recorderChunks, { type: mime })], `voice-${Date.now()}.${extension}`, { type: mime })
      recorderStream?.getTracks?.().forEach(track => track.stop())
      recorder = null; recorderStream = null; recorderChunks = []
      if (recordingTimer) window.clearInterval(recordingTimer)
      recordingTimer = null; recordingFieldKey.value = ''; recordingSeconds.value = 0
      await uploadFile(field, { file, onSuccess: () => {}, onError: () => {} })
    }
    recorder.start()
  } catch (error) {
    recorderStream?.getTracks?.().forEach(track => track.stop())
    recorder = null; recorderStream = null; recordingFieldKey.value = ''
    ElMessage.error(error?.name === 'NotFoundError' ? '未检测到麦克风，请改用“上传语音”' : (error?.message || '无法访问麦克风，请检查浏览器权限'))
  } finally {
    recordingStarting.value = false
  }
}
const imageUrl = name => `https://oss2.hui51.cn/encode/uploads/${encodeURIComponent(name)}`
const imageFiles = field => arrayValueOf(field).map((name, index) => ({
  uid: `${field.key}:${index}:${name}`,
  name: String(name),
  url: String(name).startsWith('data:image/') ? String(name) : imageUrl(name),
  remoteName: String(name),
  status: 'success',
}))
const uploadImage = async (field, options) => {
  if (!props.imageUploader) {
    const error = new Error('当前页面未配置秒应图片上传')
    options.onError?.(error)
    ElMessage.error(error.message)
    return
  }
  try {
    const result = await props.imageUploader(options.file)
    const name = String(result?.name || '').trim()
    if (!name) throw new Error('秒应未返回图片文件名')
    updateValue(field, [...arrayValueOf(field), name])
    options.onSuccess?.(result)
    ElMessage.success('图片上传成功')
  } catch (error) {
    options.onError?.(error)
    ElMessage.error(error?.message || '图片上传失败')
  }
}
const uploadSignature = async (field, options) => {
  const file = options?.file
  if (!file) return
  try {
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result || ''))
      reader.onerror = () => reject(new Error('签名图片读取失败'))
      reader.readAsDataURL(file)
    })
    if (!dataUrl.startsWith('data:image/')) throw new Error('签名必须上传图片')
    updateValue(field, dataUrl)
    options.onSuccess?.({ name: file.name, dataUrl })
    ElMessage.success('签名图片已读取')
  } catch (error) {
    options.onError?.(error)
    ElMessage.error(error?.message || '签名图片读取失败')
  }
}
const removeImage = (field, file) => {
  const removed = String(file?.remoteName || file?.name || '')
  updateValue(field, arrayValueOf(field).filter(name => String(name) !== removed))
}
const selectLimit = field => {
  const minimum = Number(field.min_select || 0)
  const maximum = Number(field.max_select || 0)
  if (minimum && maximum) return minimum === maximum ? `请选择 ${minimum} 项` : `请选择 ${minimum}～${maximum} 项`
  if (minimum) return `至少选择 ${minimum} 项`
  if (maximum) return `最多选择 ${maximum} 项`
  return ''
}
</script>

<style scoped>
.dynamic-fields{display:grid;gap:0;padding:16px;border:1px solid #bfdbfe;border-radius:16px;background:#fff}.dynamic-title{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-bottom:13px;border-bottom:1px solid #dbeafe}.dynamic-title strong,.dynamic-title small{display:block}.dynamic-title strong{color:#172033;font-size:16px}.dynamic-title small,.field-description,.multiple-field>small,.unsupported-field>small{margin-top:3px;color:#64748b;font-size:12px}.dynamic-item{display:grid;gap:9px;padding:16px 0;border-bottom:1px dashed #dbeafe}.dynamic-item:last-child{padding-bottom:0;border-bottom:0}.field-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.field-heading>div{display:flex;align-items:flex-start;gap:6px;min-width:0}.field-heading span{color:#ef4444;font-weight:800}.field-heading strong{color:#334155;font-size:14px;line-height:1.5;overflow-wrap:anywhere}.field-control{display:grid;gap:5px;min-width:0}.multiple-field{display:grid;gap:7px;width:100%}.unsupported-field{display:grid;gap:5px;width:100%}.plate-field{display:grid;grid-template-columns:78px 82px minmax(0,1fr);gap:8px}.region-field{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:8px}.field-error{color:#ef4444;font-size:12px;line-height:1.4}.attachment-upload-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,190px));gap:12px}.attachment-card{position:relative;overflow:hidden;border:1px solid #bfdbfe;border-radius:13px;background:#f8fafc}.attachment-card video{display:block;width:100%;height:120px;object-fit:cover;background:#0f172a}.attachment-card-name{overflow:hidden;padding:8px 10px;color:#475569;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.attachment-remove{position:absolute;top:7px;right:7px}.attachment-upload-trigger{width:100%}.attachment-upload-trigger :deep(.el-upload),.attachment-upload-trigger :deep(.el-upload-dragger){width:100%;height:158px}.attachment-upload-trigger :deep(.el-upload-dragger){display:grid;place-items:center;padding:0;border-color:#93c5fd;border-radius:13px;background:#f8fbff}.attachment-upload-content{display:grid;gap:7px;color:#2563eb}.attachment-upload-content span{color:#64748b;font-size:12px}.uploaded-file-value{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 10px;border:1px solid #dbeafe;border-radius:8px;color:#334155;font-size:13px}:deep(.el-radio-group),:deep(.el-checkbox-group){display:flex;align-items:flex-start;gap:8px 12px;flex-wrap:wrap}:deep(.el-radio),:deep(.el-checkbox){height:auto;min-height:34px;margin-right:0;padding:4px 10px;border:1px solid #e2e8f0;border-radius:9px;background:#f8fafc;white-space:normal}:deep(.el-radio.is-checked),:deep(.el-checkbox.is-checked){border-color:#93c5fd;background:#eff6ff}:deep(.el-select){width:100%}.field-description{display:block;padding:8px 10px;border-radius:9px;background:#f8fafc;line-height:1.6;overflow-wrap:anywhere}
.voice-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.voice-actions>.el-button{min-width:132px}.voice-actions .el-upload{display:inline-flex}.voice-field .uploaded-file-value{max-width:520px}.voice-actions .is-recording{color:#fff;border-color:#ef4444;background:#ef4444;animation:voice-pulse 1.2s ease-in-out infinite}@keyframes voice-pulse{50%{box-shadow:0 0 0 5px rgb(239 68 68 / 15%)}}
.table-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;align-items:start}.table-column{display:grid;gap:8px;min-width:0}.table-header{padding:9px 10px;text-align:center;color:#2563eb;font-weight:700;background:#eff6ff;border:1px solid #dbeafe;border-radius:8px}.table-column>.el-input,.table-column>.el-select{width:100%}
.course-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.course-card{display:flex;align-items:center;gap:10px;width:100%;padding:12px;text-align:left;border:1px solid #dbe7f5;border-radius:12px;background:#fff;cursor:pointer}.course-card.is-selected{border-color:#60a5fa;background:#eff6ff}.course-card__check{display:grid;flex:0 0 22px;width:22px;height:22px;place-items:center;border:1px solid #cbd5e1;border-radius:50%;color:#fff;background:#fff}.course-card.is-selected .course-card__check{border-color:#3b82f6;background:#3b82f6}.course-card strong,.course-card small{display:block}.course-card strong{color:#1e3a8a}.course-card small{margin-top:4px;color:#64748b;font-size:12px}
.matrix-grid{display:grid;grid-template-columns:minmax(100px,1.3fr) repeat(auto-fit,minmax(70px,1fr));gap:0;align-items:stretch;overflow:auto;border-radius:8px;background:#f8fafc}.matrix-grid>*{display:grid;min-height:42px;place-items:center;padding:8px;border-bottom:1px solid #eef2f7}.matrix-corner,.matrix-head{background:#eef0f2;color:#64748b;font-weight:600}.matrix-row-label{justify-items:start;color:#334155;background:#fafafa}.matrix-grid :deep(.el-radio),.matrix-grid :deep(.el-checkbox){min-height:28px;margin:0;padding:0;border:0;background:transparent}
.dynamic-fields.compact{padding:18px 0 0;border:0;border-top:1px solid #e2e8f0;border-radius:0;background:transparent}.dynamic-fields.compact .dynamic-title{padding-bottom:10px;border-bottom:0}.dynamic-fields.compact .dynamic-title strong{font-size:14px}.image-field{display:grid;gap:8px}.image-field>small{color:#64748b;font-size:12px;line-height:1.5}
</style>
