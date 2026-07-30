<template>
  <div class="cube-subpage">
    <section class="cube-hero">
      <span>CLASS CUBE</span>
      <h1>系统概览</h1>
      <p>独立管理班级魔方账号、课程、定时签到与企业微信通知。</p>
    </section>
    <div class="cube-stats">
      <el-card><strong>{{ accounts.length }}</strong><span>账号数量</span></el-card>
      <el-card><strong>{{ tasks.length }}</strong><span>自动任务</span></el-card>
      <el-card><strong>{{ runs.length }}</strong><span>运行记录</span></el-card>
    </div>
    <el-card>
      <template #header>
        <div class="setting-head">
          <span>企业微信机器人通知</span>
          <el-tag :type="settings.webhook_configured ? 'success' : 'info'">
            {{ settings.webhook_configured ? '已配置' : '未配置' }}
          </el-tag>
        </div>
      </template>
      <el-form v-if="isAdmin" label-position="top">
        <el-form-item label="机器人 Webhook">
          <el-input
            v-model="settings.class_cube_webhook_url"
            type="text"
            placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
          />
        </el-form-item>
        <el-button type="primary" :loading="saving" @click="saveSettings">保存配置</el-button>
      </el-form>
      <el-alert
        v-else
        :type="settings.webhook_configured ? 'success' : 'info'"
        :closable="false"
        :title="settings.webhook_configured ? '管理员已配置企业微信机器人' : '管理员尚未配置企业微信机器人'"
      />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import classCubeApi from '../api/classCube.js'
import { useClassCube } from '../composables/useClassCube.js'

const { accounts, tasks, runs, loadInitial } = useClassCube()
const user = JSON.parse(localStorage.getItem('user') || '{}')
const isAdmin = computed(() => user.role === 'admin')
const settings = reactive({
  class_cube_webhook_url: '',
  webhook_configured: false,
})
const saving = ref(false)

async function loadSettings() {
  const response = await classCubeApi.getSettings()
  Object.assign(settings, response?.data || {})
}

async function saveSettings() {
  saving.value = true
  try {
    const response = await classCubeApi.updateSettings({
      class_cube_webhook_url: settings.class_cube_webhook_url,
    })
    Object.assign(settings, response?.data || {})
    ElMessage.success('班级魔方通知配置已保存')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    loadInitial().catch(() => {}),
    loadSettings().catch(() => {}),
  ])
})
</script>

<style scoped>
.cube-subpage{display:grid;gap:18px}.cube-hero{padding:28px;border-radius:24px;color:#fff;background:linear-gradient(125deg,#1d4ed8,#0ea5e9);box-shadow:0 20px 50px #2563eb38}.cube-hero span{font-size:11px;letter-spacing:.18em}.cube-hero h1{margin:10px 0 6px;font-size:30px}.cube-hero p{margin:0;color:#e0f2fe}.cube-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.cube-stats .el-card{display:grid;gap:8px}.cube-stats strong{font-size:30px;color:#1d4ed8}.cube-stats span{color:#64748b}.setting-head{display:flex;align-items:center;justify-content:space-between}@media(max-width:700px){.cube-stats{grid-template-columns:1fr}}
</style>
