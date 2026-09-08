<template>
  <div class="overview-page">
    <div class="metrics">
      <article><b>{{ metrics.accounts || 0 }}</b><span>登录账号</span></article>
      <article><b>{{ metrics.tasks || 0 }}</b><span>全部任务</span></article>
      <article><b>{{ metrics.enabled_tasks || 0 }}</b><span>启用任务</span></article>
      <article><b>{{ metrics.successful_runs || 0 }}</b><span>成功执行</span></article>
    </div>
    <section class="panel settings-panel">
      <header>
        <div><h2>企业微信机器人通知</h2><p>配置秒应签到结果通知，与其他平台相互独立。</p></div>
        <el-tag :type="configured ? 'success' : 'info'">{{ configured ? '已配置' : '未配置' }}</el-tag>
      </header>
      <el-form v-if="isAdmin" label-position="top">
        <el-form-item label="机器人 Webhook">
          <el-input
            :model-value="webhook"
            type="password"
            show-password
            clearable
            autocomplete="off"
            placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
            @update:model-value="value => emit('update:webhook', value)"
          />
        </el-form-item>
        <div class="settings-actions">
          <el-button :disabled="!webhook" @click="copyWebhook">复制</el-button>
          <el-button :loading="testing" :disabled="!webhook" @click="emit('test')">发送测试通知</el-button>
          <el-button type="primary" :loading="saving" @click="emit('save')">保存配置</el-button>
        </div>
        <small class="security-tip">Webhook 默认隐藏；点击输入框右侧图标可临时查看。</small>
      </el-form>
      <el-alert
        v-else
        :closable="false"
        :type="configured ? 'success' : 'info'"
        :title="configured ? '管理员已配置企业微信机器人' : '管理员尚未配置企业微信机器人'"
      />
    </section>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'

const props = defineProps({
  metrics: { type: Object, default: () => ({}) },
  webhook: { type: String, default: '' },
  configured: { type: Boolean, default: false },
  isAdmin: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  testing: { type: Boolean, default: false },
})
const emit = defineEmits(['update:webhook', 'save', 'test'])

async function copyWebhook() {
  if (!props.webhook) return
  try {
    await navigator.clipboard.writeText(props.webhook)
    ElMessage.success('Webhook 已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择并复制')
  }
}
</script>

<style scoped>
.overview-page{display:grid;gap:18px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metrics article{display:grid;gap:5px;padding:22px;border:1px solid #dbeafe;border-radius:18px;background:#fff}.metrics b{font-size:28px;color:#1677ff}.metrics span{color:#64748b}.panel{min-width:0;padding:20px;border:1px solid #dbeafe;border-radius:20px;background:#ffffffde;box-shadow:0 14px 34px #0f172a0a}.panel>header{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px}.panel h2{margin:0;color:#172033;font-size:18px}.panel p{margin:4px 0 0;color:#64748b;font-size:13px}.settings-actions{display:flex;justify-content:flex-end;gap:10px}.settings-actions .el-button+.el-button{margin-left:0}.security-tip{display:block;margin-top:10px;color:#64748b;font-size:12px}@media(max-width:900px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.metrics{grid-template-columns:1fr}.panel{padding:14px}.panel>header{align-items:flex-start;flex-direction:column}.settings-actions{align-items:stretch;flex-direction:column}.settings-actions .el-button{width:100%}}
</style>
