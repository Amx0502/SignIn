<template>
  <div v-if="fields.length" class="dynamic-fields">
    <div class="dynamic-title">
      <div>
        <strong>项目填写项</strong>
        <small>字段和选项来自当前秒应签到项目</small>
      </div>
      <el-tag size="small" type="info">{{ fields.length }} 项</el-tag>
    </div>

    <el-form-item
      v-for="field in fields"
      :key="field.key"
      :label="field.title"
      :required="field.required"
      class="dynamic-item"
    >
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
      <el-alert v-else type="warning" :closable="false" :title="`${field.title}暂不支持自动填写`" />
      <small v-if="field.description" class="field-description">{{ field.description }}</small>
    </el-form-item>
  </div>
</template>

<script setup>
const props = defineProps({
  fields: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue'])

const valueOf = field => props.modelValue?.[field.key] ?? ''
const arrayValueOf = field => {
  const value = props.modelValue?.[field.key]
  return Array.isArray(value) ? value : value ? [value] : []
}
const updateValue = (field, value) => emit('update:modelValue', { ...props.modelValue, [field.key]: value })
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
.dynamic-fields{display:grid;gap:14px;padding:16px;border:1px solid #bfdbfe;border-radius:16px;background:#f8fbff}.dynamic-title{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-bottom:12px;border-bottom:1px solid #dbeafe}.dynamic-title strong,.dynamic-title small{display:block}.dynamic-title strong{color:#1e293b}.dynamic-title small,.field-description,.multiple-field>small{margin-top:3px;color:#64748b;font-size:12px}.dynamic-item{margin-bottom:0}.multiple-field{display:grid;gap:5px;width:100%}:deep(.el-form-item__content){display:block}:deep(.el-radio-group),:deep(.el-checkbox-group){display:flex;align-items:flex-start;gap:8px 18px;flex-wrap:wrap}:deep(.el-radio),:deep(.el-checkbox){height:auto;min-height:30px;margin-right:0;white-space:normal}:deep(.el-select){width:100%}.field-description{display:block;line-height:1.55}
</style>
