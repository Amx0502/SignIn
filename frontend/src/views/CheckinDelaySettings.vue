<template>
  <div class="delay-settings-page">
    <div class="page-heading">
      <div>
        <h2>签到时间设置</h2>
        <p>分别设置三套签到任务到达计划时间后、真正提交前的随机等待范围。</p>
      </div>
      <el-tag type="info" effect="plain">仅管理员可配置</el-tag>
    </div>

    <el-alert
      title="新设置会从下一次任务执行起生效，无需重启服务或重新保存已有任务。"
      type="info"
      :closable="false"
      show-icon
    />

    <div class="platform-grid" v-loading="loading">
      <el-card shadow="never" class="platform-card xxqd-card">
        <div class="platform-header">
          <div class="platform-icon">
            <img :src="xxqdImage" alt="小小签到图标" />
          </div>
          <div>
            <h3>小小签到</h3>
            <p>适用于自动任务及任务列表中的立即执行。</p>
          </div>
        </div>
        <div class="range-editor">
          <label>
            <span>最短等待</span>
            <el-input-number
              v-model="form.xxqd_min_seconds"
              :min="0"
              :max="300"
              :precision="0"
              controls-position="right"
            />
            <em>秒</em>
          </label>
          <span class="range-separator">至</span>
          <label>
            <span>最长等待</span>
            <el-input-number
              v-model="form.xxqd_max_seconds"
              :min="0"
              :max="300"
              :precision="0"
              controls-position="right"
            />
            <em>秒</em>
          </label>
        </div>
        <div class="range-summary" :class="{ invalid: !xxqdValid }">
          {{ rangeDescription('xxqd') }}
        </div>
      </el-card>

      <el-card shadow="never" class="platform-card cube-card">
        <div class="platform-header">
          <div class="platform-icon">
            <img :src="classCubeImage" alt="班级魔方图标" />
          </div>
          <div>
            <h3>班级魔方</h3>
            <p>适用于班级魔方自动任务的定时执行和立即执行。</p>
          </div>
        </div>
        <div class="range-editor">
          <label>
            <span>最短等待</span>
            <el-input-number
              v-model="form.class_cube_min_seconds"
              :min="0"
              :max="300"
              :precision="0"
              controls-position="right"
            />
            <em>秒</em>
          </label>
          <span class="range-separator">至</span>
          <label>
            <span>最长等待</span>
            <el-input-number
              v-model="form.class_cube_max_seconds"
              :min="0"
              :max="300"
              :precision="0"
              controls-position="right"
            />
            <em>秒</em>
          </label>
        </div>
        <div class="range-summary" :class="{ invalid: !classCubeValid }">
          {{ rangeDescription('class_cube') }}
        </div>
      </el-card>

      <el-card shadow="never" class="platform-card miaoying-card">
        <div class="platform-header">
          <div class="platform-icon">
            <img :src="miaoyingImage" alt="秒应图标" />
          </div>
          <div>
            <h3>秒应</h3>
            <p>适用于秒应自动任务的定时执行和立即执行。</p>
          </div>
        </div>
        <div class="range-editor">
          <label>
            <span>最短等待</span>
            <el-input-number
              v-model="form.miaoying_min_seconds"
              :min="0"
              :max="300"
              :precision="0"
              controls-position="right"
            />
            <em>秒</em>
          </label>
          <span class="range-separator">至</span>
          <label>
            <span>最长等待</span>
            <el-input-number
              v-model="form.miaoying_max_seconds"
              :min="0"
              :max="300"
              :precision="0"
              controls-position="right"
            />
            <em>秒</em>
          </label>
        </div>
        <div class="range-summary" :class="{ invalid: !miaoyingValid }">
          {{ rangeDescription('miaoying') }}
        </div>
      </el-card>
    </div>

    <el-card shadow="never" class="explanation-card">
      <div class="explanation-grid">
        <div><strong>随机范围</strong><span>例如 1～18 秒，每次任务会在区间内随机等待。</span></div>
        <div><strong>固定等待</strong><span>最短和最长填写相同数值，例如 5～5 秒。</span></div>
        <div><strong>立即执行</strong><span>最短和最长都设为 0 秒，不再增加等待。</span></div>
      </div>
    </el-card>

    <div class="save-bar">
      <span>{{ dirty ? '有未保存修改' : '当前配置已保存' }}</span>
      <div>
        <el-button :disabled="loading || saving" @click="restoreDefaults">恢复默认值</el-button>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="loading || !dirty || !formValid"
          @click="saveSettings"
        >
          保存设置
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getCheckinDelaySettingsApi,
  updateCheckinDelaySettingsApi,
} from '../api'
import xxqdImage from '../img/xxqd.png'
import classCubeImage from '../img/bjmf.png'
import miaoyingImage from '../img/miaoying.png'

const DEFAULTS = {
  xxqd_min_seconds: 1,
  xxqd_max_seconds: 18,
  class_cube_min_seconds: 1,
  class_cube_max_seconds: 18,
  miaoying_min_seconds: 1,
  miaoying_max_seconds: 18,
}

const loading = ref(false)
const saving = ref(false)
const form = reactive({ ...DEFAULTS })
const saved = ref({ ...DEFAULTS })

const xxqdValid = computed(() => form.xxqd_min_seconds <= form.xxqd_max_seconds)
const classCubeValid = computed(() => form.class_cube_min_seconds <= form.class_cube_max_seconds)
const miaoyingValid = computed(() => form.miaoying_min_seconds <= form.miaoying_max_seconds)
const formValid = computed(() => xxqdValid.value && classCubeValid.value && miaoyingValid.value)
const dirty = computed(() => Object.keys(DEFAULTS).some(key => form[key] !== saved.value[key]))

function assignSettings(target, settings) {
  Object.keys(DEFAULTS).forEach(key => {
    target[key] = Number.isInteger(settings?.[key]) ? settings[key] : DEFAULTS[key]
  })
}

function rangeDescription(platform) {
  const minimum = form[`${platform}_min_seconds`]
  const maximum = form[`${platform}_max_seconds`]
  if (minimum > maximum) return '最短等待时间不能大于最长等待时间'
  if (minimum === 0 && maximum === 0) return '当前设置：任务到点后立即执行'
  if (minimum === maximum) return `当前设置：任务到点后固定等待 ${minimum} 秒`
  return `当前设置：任务到点后随机等待 ${minimum}～${maximum} 秒`
}

async function loadSettings() {
  loading.value = true
  try {
    const response = await getCheckinDelaySettingsApi()
    assignSettings(form, response.data)
    saved.value = { ...form }
  } catch (error) {
    ElMessage.error(error.message || '签到时间设置加载失败')
  } finally {
    loading.value = false
  }
}

function restoreDefaults() {
  assignSettings(form, DEFAULTS)
}

async function saveSettings() {
  if (!formValid.value) {
    ElMessage.warning('请先修正等待时间范围')
    return
  }
  saving.value = true
  try {
    const response = await updateCheckinDelaySettingsApi({ ...form })
    assignSettings(form, response.data)
    saved.value = { ...form }
    ElMessage.success('签到时间设置已保存，下次任务执行时生效')
  } catch (error) {
    ElMessage.error(error.message || '签到时间设置保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.delay-settings-page {
  display: grid;
  gap: 18px;
  padding: 24px;
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.page-heading h2,
.platform-header h3 {
  margin: 0;
  color: #10213a;
}

.page-heading p,
.platform-header p {
  margin: 6px 0 0;
  color: #75849a;
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.platform-card {
  border: 1px solid #cfe2ff;
  border-radius: 20px;
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 18px;
  border-bottom: 1px solid #e7effa;
}

.platform-icon {
  flex: 0 0 48px;
  width: 48px;
  height: 48px;
  border-radius: 15px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 9px 20px rgba(47, 126, 246, 0.16);
}

.platform-icon img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.range-editor {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
  gap: 14px;
  padding: 24px 0 18px;
}

.range-editor label {
  position: relative;
  display: grid;
  gap: 9px;
  min-width: 0;
  color: #516178;
}

.range-editor :deep(.el-input-number) {
  width: 100%;
}

.range-editor em {
  position: absolute;
  right: 46px;
  bottom: 9px;
  color: #8b9ab0;
  font-style: normal;
  pointer-events: none;
}

.range-separator {
  padding-bottom: 10px;
  color: #8b9ab0;
}

.range-summary {
  min-height: 42px;
  padding: 11px 14px;
  border-radius: 12px;
  background: #eef6ff;
  color: #2872d5;
  line-height: 20px;
}

.range-summary.invalid {
  background: #fff1f0;
  color: #e24848;
}

.explanation-card {
  border: 1px solid #e0eaf7;
  border-radius: 16px;
}

.explanation-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.explanation-grid div {
  display: grid;
  gap: 6px;
}

.explanation-grid strong {
  color: #2b3b52;
}

.explanation-grid span {
  color: #74839a;
  line-height: 1.6;
}

.save-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border: 1px solid #d9e6f8;
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.86);
  color: #718096;
  box-shadow: 0 12px 30px rgba(30, 88, 154, 0.08);
}

@media (max-width: 1200px) {
  .platform-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .platform-grid,
  .explanation-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .delay-settings-page {
    padding: 14px;
  }

  .page-heading,
  .save-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .save-bar,
  .save-bar > div {
    width: 100%;
  }

  .save-bar > div {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .range-editor {
    grid-template-columns: 1fr;
  }

  .range-separator {
    display: none;
  }
}
</style>
