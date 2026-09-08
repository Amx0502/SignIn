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
      <div class="field-control">
        <el-input
        v-if="field.control === 'text'"
        :model-value="valueOf(field)"
        clearable
        :maxlength="field.max_length || undefined"
        :placeholder="`请输入${field.title}`"
        @update:model-value="value => updateValue(field, value)"
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
        <el-alert v-else type="warning" :closable="false" :title="`${field.title}暂不支持自动填写`" />
      </div>
      <small v-if="field.description" class="field-description">{{ field.description }}</small>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import TaskImageUpload from '../TaskImageUpload.vue'
import { visibleMiaoyingFields } from '../../utils/miaoyingFields.js'

const props = defineProps({
  fields: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
  compact: { type: Boolean, default: false },
  imageUploader: { type: Function, default: null },
})
const emit = defineEmits(['update:modelValue'])

const visibleFields = computed(() => visibleMiaoyingFields(props.fields, props.modelValue))

const valueOf = field => props.modelValue?.[field.key] ?? ''
const arrayValueOf = field => {
  const value = props.modelValue?.[field.key]
  return Array.isArray(value) ? value : value ? [value] : []
}
const updateValue = (field, value) => emit('update:modelValue', { ...props.modelValue, [field.key]: value })
const imageUrl = name => `https://oss2.hui51.cn/encode/uploads/${encodeURIComponent(name)}`
const imageFiles = field => arrayValueOf(field).map((name, index) => ({
  uid: `${field.key}:${index}:${name}`,
  name: String(name),
  url: imageUrl(name),
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
.dynamic-fields{display:grid;gap:0;padding:16px;border:1px solid #bfdbfe;border-radius:16px;background:#fff}.dynamic-title{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-bottom:13px;border-bottom:1px solid #dbeafe}.dynamic-title strong,.dynamic-title small{display:block}.dynamic-title strong{color:#172033;font-size:16px}.dynamic-title small,.field-description,.multiple-field>small{margin-top:3px;color:#64748b;font-size:12px}.dynamic-item{display:grid;gap:9px;padding:16px 0;border-bottom:1px dashed #dbeafe}.dynamic-item:last-child{padding-bottom:0;border-bottom:0}.field-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.field-heading>div{display:flex;align-items:flex-start;gap:6px;min-width:0}.field-heading span{color:#ef4444;font-weight:800}.field-heading strong{color:#334155;font-size:14px;line-height:1.5;overflow-wrap:anywhere}.field-control{min-width:0}.multiple-field{display:grid;gap:7px;width:100%}:deep(.el-radio-group),:deep(.el-checkbox-group){display:flex;align-items:flex-start;gap:8px 12px;flex-wrap:wrap}:deep(.el-radio),:deep(.el-checkbox){height:auto;min-height:34px;margin-right:0;padding:4px 10px;border:1px solid #e2e8f0;border-radius:9px;background:#f8fafc;white-space:normal}:deep(.el-radio.is-checked),:deep(.el-checkbox.is-checked){border-color:#93c5fd;background:#eff6ff}:deep(.el-select){width:100%}.field-description{display:block;padding:8px 10px;border-radius:9px;background:#f8fafc;line-height:1.6;overflow-wrap:anywhere}
.dynamic-fields.compact{padding:18px 0 0;border:0;border-top:1px solid #e2e8f0;border-radius:0;background:transparent}.dynamic-fields.compact .dynamic-title{padding-bottom:10px;border-bottom:0}.dynamic-fields.compact .dynamic-title strong{font-size:14px}.image-field{display:grid;gap:8px}.image-field>small{color:#64748b;font-size:12px;line-height:1.5}
</style>
