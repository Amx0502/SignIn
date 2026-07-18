<template>
  <div class="page-container">
    <section class="page-hero">
      <p class="hero-eyebrow">Operations Dashboard</p>
      <h1 class="hero-title">自动签到运行中枢</h1>
      <p class="hero-desc">集中监控账号、任务、调度与 Token 刷新状态，提供清晰的数据视图与一键运维操作。</p>
    </section>

    <el-row :gutter="18">
      <el-col v-for="item in metrics" :key="item.label" :xs="24" :sm="12" :md="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-top">
              <div>
                <div class="metric-value" :style="item.small ? 'font-size: 19px; letter-spacing: -0.02em;' : ''">{{ item.value }}</div>
                <div class="metric-label">{{ item.label }}</div>
              </div>
              <div class="metric-icon"><el-icon><component :is="item.icon" /></el-icon></div>
            </div>
            <div class="metric-trend">{{ item.trend }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="18" class="analytics-grid">
      <el-col :xs="24" :lg="14">
        <el-card class="chart-card" shadow="hover">
          <template #header><div class="card-header"><span class="card-title">任务健康度</span><el-tag type="success">{{ completionRate }}%</el-tag></div></template>
          <div class="progress-list">
            <div class="progress-row"><div class="progress-meta"><span>启用任务占比</span><strong>{{ completionRate }}%</strong></div><div class="progress-track"><div class="progress-fill" :style="{ width: `${completionRate}%` }"></div></div></div>
            <div class="progress-row"><div class="progress-meta"><span>账号任务覆盖</span><strong>{{ coverageRate }}%</strong></div><div class="progress-track"><div class="progress-fill" :style="{ width: `${coverageRate}%` }"></div></div></div>
            <div class="progress-row"><div class="progress-meta"><span>调度可用性</span><strong>{{ state.auto_enabled ? 100 : 35 }}%</strong></div><div class="progress-track"><div class="progress-fill" :style="{ width: `${state.auto_enabled ? 100 : 35}%` }"></div></div></div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card class="chart-card" shadow="hover">
          <template #header><div class="card-header"><span class="card-title">运行状态</span><el-tag :type="state.auto_enabled ? 'success' : 'danger'">{{ state.auto_enabled ? '自动调度已开启' : '自动调度未开启' }}</el-tag></div></template>
          <div class="status-orbit">
            <div class="orbit-core">{{ state.enabled_task_count || 0 }}<span>启用任务</span></div>
          </div>
          <div class="status-grid">
            <div><span>刷新计划</span><strong>{{ refreshTimeCount }} 个</strong></div>
            <div><span>服务时间</span><strong>{{ state.server_time }}</strong></div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="form-section" shadow="hover">
      <template #header><div class="card-header"><span class="card-title">调度设置</span><el-tag :type="state.auto_enabled ? 'success' : 'danger'">{{ state.auto_enabled ? '自动调度已开启' : '自动调度未开启' }}</el-tag></div></template>
      <el-form :model="settingsForm" label-width="120px" class="settings-form">
        <el-form-item label="Token 刷新时间"><el-input v-model="settingsForm.refresh_times" placeholder="07:30:00,11:30:00,14:00:00" /></el-form-item>
        <el-form-item><el-button type="primary" @click="toggleAuto">{{ state.auto_enabled ? '关闭自动调度' : '开启自动调度' }}</el-button><el-button @click="saveSettings">保存设置</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover">
      <template #header><div class="card-header"><span class="card-title">全局操作</span><el-tag type="info">高频运维</el-tag></div></template>
      <el-space wrap><el-button type="warning" :icon="Refresh" @click="refreshAllTokens">刷新全部 Token</el-button><el-button type="success" :icon="VideoPlay" @click="runAllEnabledTasks">执行全部启用任务</el-button></el-space>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, watch, computed } from 'vue'
import { Refresh, VideoPlay, User, Tickets, CircleCheck, Clock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAppState } from '../composables/useAppState'
import api from '../api'

const { state, refreshState, refreshLogs } = useAppState()
const settingsForm = reactive({ refresh_times: '' })
const refreshTimeCount = computed(() => (state.value.refresh_times || []).length)
const completionRate = computed(() => state.value.task_count ? Math.round((state.value.enabled_task_count / state.value.task_count) * 100) : 0)
const coverageRate = computed(() => state.value.account_count ? Math.min(100, Math.round((state.value.task_count / state.value.account_count) * 35)) : 0)
const metrics = computed(() => [
  { label: '账号总数', value: state.value.account_count, icon: User, trend: '账号资产集中管理' },
  { label: '任务总数', value: state.value.task_count, icon: Tickets, trend: '覆盖普通与图片签到' },
  { label: '启用任务', value: state.value.enabled_task_count, icon: CircleCheck, trend: `启用率 ${completionRate.value}%` },
  { label: '当前时间', value: state.value.server_time, icon: Clock, trend: '服务端时间同步', small: true }
])
watch(() => state.value.refresh_times, (val) => { settingsForm.refresh_times = (val || []).join(', ') }, { immediate: true })
async function toggleAuto() { await saveSettingsCore(!state.value.auto_enabled) }
async function saveSettings() { await saveSettingsCore(state.value.auto_enabled) }
async function saveSettingsCore(autoEnabled) { try { await api.setSettings({ auto_enabled: autoEnabled, refresh_times: settingsForm.refresh_times }); ElMessage.success('设置已保存'); await refreshState(); await refreshLogs() } catch (err) { ElMessage.error(err.message) } }
async function refreshAllTokens() { try { await api.refreshAllTokens(); ElMessage.success('已发起全部 Token 刷新'); await refreshLogs() } catch (err) { ElMessage.error(err.message) } }
async function runAllEnabledTasks() { try { await api.runAllEnabledTasks(); ElMessage.success('已将全部启用任务加入队列'); await refreshLogs() } catch (err) { ElMessage.error(err.message) } }
</script>

<style scoped>
.status-orbit { height: 150px; display: grid; place-items: center; background: radial-gradient(circle, #dbeafe 0 32%, transparent 33%), conic-gradient(from 110deg, #2563eb, #06b6d4, #93c5fd, #2563eb); border-radius: 22px; padding: 10px; }
.orbit-core { width: 118px; height: 118px; display: grid; place-items: center; align-content: center; border-radius: 50%; background: #fff; color: #1d4ed8; font-size: 34px; font-weight: 900; box-shadow: inset 0 0 0 1px #dbeafe; }
.orbit-core span { display: block; font-size: 12px; color: #64748b; font-weight: 700; }
.status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.status-grid div { padding: 14px; border-radius: 16px; background: #f8fafc; border: 1px solid #e2e8f0; }
.status-grid span { display: block; color: #64748b; font-size: 12px; margin-bottom: 6px; }
.status-grid strong { color: #0f172a; font-size: 14px; }
</style>
