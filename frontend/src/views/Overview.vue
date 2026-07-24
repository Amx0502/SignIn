<template>
  <div class="page-container">
    <section class="page-hero">
      <p class="hero-eyebrow">Operations Dashboard</p>
      <h1 class="hero-title">自动签到运行中枢</h1>
      <p class="hero-desc">集中监控账号、任务、调度与 Token 刷新状态，提供清晰的数据视图与一键运维操作。</p>
    </section>

    <el-row :gutter="18">
      <el-col v-for="item in metrics" :key="item.label" :xs="24" :sm="12" :md="8">
        <el-card>
          <div class="metric-card">
            <div class="metric-top">
              <div>
                <div class="metric-value">{{ item.value }}</div>
                <div class="metric-label">{{ item.label }}</div>
              </div>
              <div class="metric-icon"><el-icon>
                  <component :is="item.icon" />
                </el-icon></div>
            </div>
            <div class="metric-trend">{{ item.trend }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>



    <el-card class="form-section" shadow="hover">
      <template #header>
        <div class="card-header"><span class="card-title">调度设置</span><el-tag
            :type="state.auto_enabled ? 'success' : 'danger'">{{ state.auto_enabled ? '自动调度已开启' : '自动调度未开启' }}</el-tag>
        </div>
      </template>
      <el-form :model="settingsForm" label-width="120px" class="settings-form">
        <el-form-item label="Token 刷新时间"><el-input v-model="settingsForm.refresh_times"
            placeholder="07:30:00,11:30:00,14:00:00" /></el-form-item>
        <el-form-item label="企业微信机器人"><el-input v-model="settingsForm.webhook_url"
            placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" /></el-form-item>
        <el-form-item><el-button type="primary" @click="toggleAuto">{{ state.auto_enabled ? '关闭自动调度' : '开启自动调度'
        }}</el-button><el-button @click="saveSettings">保存设置</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover">
      <template #header>
        <div class="card-header"><span class="card-title">全局操作</span><el-tag type="info">高频运维</el-tag></div>
      </template>
      <el-space wrap><el-button type="warning" :icon="Refresh" @click="refreshAllTokens">刷新全部
          Token</el-button><el-button type="success" :icon="VideoPlay"
          @click="runAllEnabledTasks">执行全部启用任务</el-button></el-space>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, watch, computed } from 'vue'
import { Refresh, VideoPlay, User, Tickets, CircleCheck } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAppState } from '../composables/useAppState'
import api from '../api'

const { state, refreshState, refreshLogs } = useAppState()
const settingsForm = reactive({ refresh_times: '', webhook_url: '' })
const metrics = computed(() => [
  { label: '账号总数', value: state.value.account_count, icon: User, trend: '账号资产集中管理' },
  { label: '任务总数', value: state.value.task_count, icon: Tickets, trend: '覆盖普通与图片签到' },
  { label: '启用任务', value: state.value.enabled_task_count, icon: CircleCheck, trend: '已启用的定时任务' }
])
watch(() => state.value.refresh_times, (val) => { settingsForm.refresh_times = (val || []).join(', ') }, { immediate: true })
watch(() => state.value.webhook_url, (val) => { settingsForm.webhook_url = val || '' }, { immediate: true })
async function toggleAuto() { await saveSettingsCore(!state.value.auto_enabled) }
async function saveSettings() { await saveSettingsCore(state.value.auto_enabled) }
async function saveSettingsCore(autoEnabled) { try { await api.setSettings({ auto_enabled: autoEnabled, refresh_times: settingsForm.refresh_times.split(',').map(s => s.trim()).filter(Boolean), webhook_url: settingsForm.webhook_url }); ElMessage.success('设置已保存'); await refreshState(); await refreshLogs() } catch (err) { ElMessage.error(err.message) } }
async function refreshAllTokens() { try { await api.refreshAllTokens(); ElMessage.success('已发起全部 Token 刷新'); await refreshLogs() } catch (err) { ElMessage.error(err.message) } }
async function runAllEnabledTasks() { try { await api.runAllEnabledTasks(); ElMessage.success('已将全部启用任务加入队列'); await refreshLogs() } catch (err) { ElMessage.error(err.message) } }
</script>

<style scoped>
</style>
