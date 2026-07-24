<template>
  <div class="task-image-upload">
    <div class="task-image-upload__grid">
      <article
        v-for="(file, index) in fileList"
        :key="file.uid || file.url || file.path || index"
        class="task-image-upload__card"
      >
        <img class="task-image-upload__image" :src="resolveFileUrl(file)" :alt="file.name || `签到图片 ${index + 1}`" />
        <div class="task-image-upload__actions">
          <button type="button" @click="openPreview(file)"><el-icon><View /></el-icon><span>预览</span></button>
          <button type="button" class="is-danger" @click="removeFile(file)"><el-icon><Delete /></el-icon><span>删除</span></button>
        </div>
        <div class="task-image-upload__filename" :title="file.name">{{ file.name || `签到图片 ${index + 1}` }}</div>
      </article>

      <el-upload
        v-if="fileList.length < limit"
        class="task-image-upload__uploader"
        :show-file-list="false"
        :http-request="httpRequest"
        accept="image/*"
        multiple
        :limit="limit"
      >
        <div class="task-image-upload__trigger">
          <el-icon><UploadFilled /></el-icon>
          <strong>上传图片</strong>
          <span>{{ fileList.length }}/{{ limit }}</span>
        </div>
      </el-upload>
    </div>

    <el-dialog v-model="previewVisible" class="task-image-preview-dialog" width="780px" append-to-body align-center :show-close="false">
      <div class="task-image-upload__preview">
        <header>
          <div><span>图片预览</span><small>{{ previewName }}</small></div>
          <button type="button" aria-label="关闭图片预览" @click="previewVisible = false">×</button>
        </header>
        <div class="task-image-upload__preview-stage"><img :src="previewUrl" :alt="previewName || '签到图片预览'" /></div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Delete, UploadFilled, View } from '@element-plus/icons-vue'

const props = defineProps({
  fileList: { type: Array, default: () => [] },
  limit: { type: Number, default: 3 },
  httpRequest: { type: Function, required: true },
  onRemove: { type: Function, required: true },
})

const previewVisible = ref(false)
const previewUrl = ref('')
const previewName = ref('')

function resolveFileUrl(file) {
  if (file?.url) return file.url
  if (file?.path) return `/uploads/${String(file.path).split(/[\\/]/).pop()}`
  return ''
}

function openPreview(file) {
  previewUrl.value = resolveFileUrl(file)
  previewName.value = file?.name || '签到图片'
  previewVisible.value = true
}

function removeFile(file) {
  props.onRemove(file, props.fileList)
}
</script>

<style scoped>
.task-image-upload__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(132px, 1fr)); gap: 12px; max-width: 620px; }
.task-image-upload__card, .task-image-upload__trigger { position: relative; min-height: 132px; overflow: hidden; border: 1px solid #dbe7f5; border-radius: 14px; background: #f8fbff; }
.task-image-upload__card { box-shadow: 0 8px 22px rgb(37 99 235 / 8%); }
.task-image-upload__image { display: block; width: 100%; height: 98px; object-fit: cover; background: linear-gradient(135deg, #eef6ff, #f8fafc); }
.task-image-upload__filename { overflow: hidden; padding: 8px 10px; color: #526078; font-size: 12px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.task-image-upload__actions { position: absolute; inset: 0 0 34px; display: flex; align-items: center; justify-content: center; gap: 8px; opacity: 0; background: rgb(9 23 45 / 72%); backdrop-filter: blur(3px); transition: opacity 0.2s ease; }
.task-image-upload__card:hover .task-image-upload__actions, .task-image-upload__card:focus-within .task-image-upload__actions { opacity: 1; }
.task-image-upload__actions button { display: inline-flex; align-items: center; gap: 4px; padding: 7px 9px; border: 1px solid rgb(255 255 255 / 32%); border-radius: 8px; color: #fff; background: rgb(255 255 255 / 12%); cursor: pointer; }
.task-image-upload__actions button:hover { background: rgb(59 130 246 / 82%); }
.task-image-upload__actions button.is-danger:hover { background: rgb(239 68 68 / 88%); }
.task-image-upload__uploader { width: 100%; }
.task-image-upload__trigger { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; color: #64748b; border-style: dashed; cursor: pointer; transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease; }
.task-image-upload__trigger .el-icon { margin-bottom: 8px; color: #3b82f6; font-size: 26px; }
.task-image-upload__trigger strong { color: #334155; font-size: 13px; }
.task-image-upload__trigger span { margin-top: 4px; font-size: 11px; }
.task-image-upload__trigger:hover { color: #2563eb; border-color: #60a5fa; background: #eff6ff; }
</style>

<style>
.task-image-preview-dialog { max-width: calc(100vw - 32px); overflow: hidden; border: 1px solid rgb(96 165 250 / 28%); border-radius: 18px; background: #0c172a; box-shadow: 0 28px 80px rgb(2 8 23 / 42%); }
.task-image-preview-dialog .el-dialog__header { display: none; }
.task-image-preview-dialog .el-dialog__body { padding: 0; }
.task-image-upload__preview header { display: flex; align-items: center; justify-content: space-between; padding: 16px 18px; color: #f8fafc; background: linear-gradient(90deg, #13233e, #172b4d); }
.task-image-upload__preview header div { min-width: 0; }
.task-image-upload__preview header span, .task-image-upload__preview header small { display: block; }
.task-image-upload__preview header span { font-size: 16px; font-weight: 700; }
.task-image-upload__preview header small { overflow: hidden; max-width: 620px; margin-top: 3px; color: #94a3b8; text-overflow: ellipsis; white-space: nowrap; }
.task-image-upload__preview header button { flex: none; width: 34px; height: 34px; border: 1px solid rgb(255 255 255 / 14%); border-radius: 10px; color: #cbd5e1; font-size: 24px; line-height: 28px; background: rgb(255 255 255 / 7%); cursor: pointer; }
.task-image-upload__preview-stage { display: flex; align-items: center; justify-content: center; min-height: 260px; max-height: 72vh; padding: 20px; background: radial-gradient(circle at 50% 35%, rgb(30 64 175 / 24%), transparent 42%), #08111f; }
.task-image-upload__preview-stage img { max-width: 100%; max-height: calc(72vh - 40px); object-fit: contain; border-radius: 10px; box-shadow: 0 16px 50px rgb(0 0 0 / 38%); }
</style>
