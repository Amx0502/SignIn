<template>
  <div class="qr-image-field" @paste.prevent="handlePaste" @dragover.prevent @drop.prevent="handleDrop">
    <input ref="fileInput" class="qr-file-input" type="file" accept="image/*" @change="handleFileChange" />
    <el-button type="primary" plain :loading="decoding" @click="fileInput?.click()">上传二维码图片并解析</el-button>
    <span>可直接 Ctrl+V 粘贴，或将二维码图片拖到此处</span>
    <div v-if="modelValue" class="qr-result">
      <el-input :model-value="modelValue" readonly clearable @clear="emit('update:modelValue', '')" />
      <el-button link type="danger" @click="emit('update:modelValue', '')">清除</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { decodeQrImage } from '../../utils/qrImageDecode.js'

defineProps({ modelValue: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
const fileInput = ref(null)
const decoding = ref(false)

async function decode(file) {
  if (!file) return
  decoding.value = true
  try {
    emit('update:modelValue', await decodeQrImage(file))
    ElMessage.success('二维码解析成功')
  } catch (error) {
    ElMessage.error(error?.message || '二维码解析失败')
  } finally {
    decoding.value = false
  }
}
function handleFileChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  decode(file)
}
function handlePaste(event) {
  const file = Array.from(event.clipboardData?.items || [])
    .find(item => item.kind === 'file' && item.type.startsWith('image/'))?.getAsFile()
  decode(file)
}
function handleDrop(event) {
  const file = Array.from(event.dataTransfer?.files || []).find(item => item.type?.startsWith('image/'))
  decode(file)
}
</script>

<style scoped>
.qr-image-field{display:grid;gap:8px;padding:10px;border:1px dashed #93c5fd;border-radius:12px;background:#f8fbff}.qr-image-field>span{color:#64748b;font-size:12px}.qr-file-input{position:absolute;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none}.qr-result{display:flex;align-items:center;gap:6px}.qr-result :deep(.el-input){flex:1}
</style>
