<template>
  <div class="purchase-settings-page">
    <div class="page-heading">
      <div>
        <h2>购买链接设置</h2>
        <p>统一管理官网“立即购买”“购买次卡”和“购买月卡”按钮跳转的地址。</p>
      </div>
      <el-tag type="info" effect="plain">仅管理员可配置</el-tag>
    </div>

    <el-card shadow="never" class="settings-card" v-loading="loading">
      <el-form label-position="top" @submit.prevent="saveSettings">
        <el-form-item label="购买链接">
          <el-input v-model="form.purchase_url" clearable placeholder="请输入有效的 http 或 https 地址">
            <template #prefix><el-icon><Link /></el-icon></template>
          </el-input>
          <div class="field-help">保存后，官网所有会员卡购买按钮会使用该链接。</div>
        </el-form-item>
        <div class="link-preview">
          <span>当前地址</span>
          <a :href="form.purchase_url" target="_blank" rel="noopener noreferrer">{{ form.purchase_url || '暂未配置' }}</a>
        </div>
        <div class="form-actions">
          <span>{{ dirty ? '有未保存修改' : '当前配置已保存' }}</span>
          <div>
            <el-button :disabled="!validUrl || loading" @click="openPreview">测试打开</el-button>
            <el-button type="primary" :loading="saving" :disabled="!validUrl" @click="saveSettings">保存购买链接</el-button>
          </div>
        </div>
      </el-form>
    </el-card>

    <el-alert
      title="建议使用淘宝、闲鱼或其他稳定购买页面的 https 地址。链接变更后无需重新构建或重启前端。"
      type="info"
      :closable="false"
      show-icon
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Link } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getPurchaseLinkSettingsApi, updatePurchaseLinkSettingsApi } from '../api'

const loading = ref(false)
const saving = ref(false)
const savedUrl = ref('')
const form = reactive({ purchase_url: '' })
const validUrl = computed(() => {
  try {
    return ['http:', 'https:'].includes(new URL(form.purchase_url).protocol)
  } catch {
    return false
  }
})
const dirty = computed(() => form.purchase_url.trim() !== savedUrl.value)

function openPreview() {
  if (validUrl.value) window.open(form.purchase_url, '_blank', 'noopener,noreferrer')
}

async function loadSettings() {
  loading.value = true
  try {
    const response = await getPurchaseLinkSettingsApi()
    form.purchase_url = response.data.purchase_url || ''
    savedUrl.value = form.purchase_url.trim()
  } catch (error) {
    ElMessage.error(error.message || '购买链接加载失败')
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  if (!validUrl.value) {
    ElMessage.warning('请输入有效的 http 或 https 购买链接')
    return
  }
  saving.value = true
  try {
    const response = await updatePurchaseLinkSettingsApi({ purchase_url: form.purchase_url.trim() })
    form.purchase_url = response.data.purchase_url
    savedUrl.value = form.purchase_url.trim()
    ElMessage.success('购买链接已保存')
  } catch (error) {
    ElMessage.error(error.message || '购买链接保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.purchase-settings-page { display: grid; gap: 18px; padding: 24px; }
.page-heading { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.page-heading h2 { margin: 0; color: #10213a; }
.page-heading p { margin: 6px 0 0; color: #75849a; }
.settings-card { max-width: 860px; border: 1px solid #dbeafe; border-radius: 18px; }
.field-help { margin-top: 8px; color: #75849a; font-size: 12px; }
.link-preview { display: grid; gap: 6px; margin: 2px 0 22px; padding: 14px 16px; border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc; }
.link-preview span { color: #94a3b8; font-size: 11px; }
.link-preview a { overflow-wrap: anywhere; color: #2563eb; font-size: 13px; text-decoration: none; }
.link-preview a:hover { text-decoration: underline; }
.form-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-top: 18px; border-top: 1px solid #edf2f7; color: #718096; font-size: 12px; }
.form-actions > div { display: flex; gap: 10px; }
@media (max-width: 640px) {
  .purchase-settings-page { padding: 14px; }
  .page-heading, .form-actions { align-items: flex-start; flex-direction: column; }
  .form-actions, .form-actions > div { width: 100%; }
  .form-actions > div { display: grid; grid-template-columns: 1fr 1fr; }
  .form-actions .el-button { width: 100%; margin: 0; }
}
</style>
