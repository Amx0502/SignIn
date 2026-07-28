<template>
  <el-dialog
    :model-value="modelValue"
    class="cube-qr-dialog"
    width="430px"
    align-center
    append-to-body
    @close="emit('update:modelValue', false)"
  >
    <template #header>
      <div class="qr-title">
        <span class="qr-title__icon"><el-icon><Cellphone /></el-icon></span>
        <div><strong>微信扫码登录</strong><small>使用班级魔方绑定的微信扫码</small></div>
      </div>
    </template>
    <div class="qr-body" :class="`is-${session?.status || 'pending'}`">
      <div class="qr-stage">
        <img v-if="session?.qrImage" :src="session.qrImage" alt="班级魔方微信登录二维码" />
        <el-skeleton v-else animated><template #template><el-skeleton-item variant="image" class="qr-skeleton" /></template></el-skeleton>
        <div v-if="session?.status === 'success'" class="qr-overlay"><el-icon><CircleCheckFilled /></el-icon><strong>登录成功</strong></div>
      </div>
      <div class="qr-state">
        <el-tag :type="statusMeta.type" effect="light">{{ statusMeta.label }}</el-tag>
        <span v-if="session?.status === 'pending'">二维码将在 <b>{{ qrRemainingSeconds }}</b> 秒后失效</span>
        <span v-else>{{ statusMeta.tip }}</span>
      </div>
      <el-progress
        v-if="session?.status === 'pending'"
        :percentage="countdownPercent"
        :show-text="false"
        :stroke-width="6"
      />
    </div>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">关闭</el-button>
      <el-button
        v-if="session?.status !== 'success'"
        type="primary"
        :loading="loading"
        @click="emit('regenerate')"
      >重新生成</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { Cellphone, CircleCheckFilled } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  session: { type: Object, default: null },
  qrRemainingSeconds: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'regenerate'])

const statusMap = {
  pending: { label: '等待扫码', type: 'primary', tip: '请在微信中确认登录' },
  success: { label: '登录成功', type: 'success', tip: '账号与课程已同步' },
  expired: { label: '二维码已过期', type: 'warning', tip: '请重新生成二维码' },
  error: { label: '生成失败', type: 'danger', tip: '请稍后重新生成' },
}
const statusMeta = computed(() => statusMap[props.session?.status] || statusMap.pending)
const countdownPercent = computed(() =>
  Math.max(0, Math.min(100, Math.round(props.qrRemainingSeconds / 120 * 100))),
)
</script>

<style scoped>
.qr-title { display: flex; align-items: center; gap: 12px; }
.qr-title__icon { display: grid; width: 42px; height: 42px; place-items: center; color: #fff; border-radius: 14px; background: linear-gradient(135deg, #2563eb, #0ea5e9); box-shadow: 0 10px 24px rgb(37 99 235 / 24%); }
.qr-title strong, .qr-title small { display: block; }
.qr-title strong { color: #172033; font-size: 17px; }
.qr-title small { margin-top: 3px; color: #64748b; font-size: 12px; }
.qr-body { display: grid; justify-items: center; gap: 18px; padding: 10px 0 4px; }
.qr-stage { position: relative; width: 248px; height: 248px; display: grid; place-items: center; padding: 13px; overflow: hidden; border: 1px solid #bfdbfe; border-radius: 24px; background: linear-gradient(145deg, #fff, #eff6ff); box-shadow: 0 18px 44px rgb(37 99 235 / 15%); }
.qr-stage img, .qr-skeleton { width: 220px; height: 220px; border-radius: 14px; object-fit: contain; }
.qr-overlay { position: absolute; inset: 0; display: grid; place-content: center; justify-items: center; gap: 10px; color: #fff; background: rgb(5 150 105 / 88%); backdrop-filter: blur(5px); }
.qr-overlay .el-icon { font-size: 52px; }
.qr-state { display: flex; align-items: center; gap: 10px; color: #64748b; font-size: 13px; }
.qr-state b { color: #2563eb; font-size: 18px; font-variant-numeric: tabular-nums; }
.el-progress { width: 248px; }
</style>

<style>
.cube-qr-dialog.el-dialog { max-width: calc(100vw - 28px); overflow: hidden; border: 1px solid rgb(191 219 254 / 80%); border-radius: 24px; background: rgb(255 255 255 / 96%); box-shadow: 0 30px 80px rgb(15 23 42 / 22%); }
</style>
