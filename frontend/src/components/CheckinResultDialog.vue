<template>
  <el-dialog
    class="checkin-result-dialog"
    :model-value="modelValue"
    width="620px"
    align-center
    append-to-body
    :show-close="false"
    @close="close"
  >
    <div v-if="result" class="checkin-result">
      <header class="checkin-result__hero">
        <div class="checkin-result__success-icon">
          <el-icon><CircleCheckFilled /></el-icon>
        </div>
        <div class="checkin-result__heading">
          <span class="checkin-result__eyebrow">CHECK-IN COMPLETED</span>
          <h2>签到成功</h2>
          <p>任务已执行完成，以下是本次签到信息</p>
        </div>
        <button class="checkin-result__close" type="button" aria-label="关闭" @click="close">
          <el-icon><Close /></el-icon>
        </button>
      </header>

      <main class="checkin-result__content">
        <div class="checkin-result__grid">
          <article class="result-detail">
            <span class="result-detail__icon"><el-icon><Document /></el-icon></span>
            <div>
              <span class="result-detail__label">任务标题</span>
              <strong>{{ result.title }}</strong>
            </div>
          </article>

          <article class="result-detail">
            <span class="result-detail__icon"><el-icon><OfficeBuilding /></el-icon></span>
            <div>
              <span class="result-detail__label">实际项目</span>
              <strong>{{ result.realTitle }}</strong>
            </div>
          </article>

          <article v-if="result.text" class="result-detail result-detail--wide">
            <span class="result-detail__icon"><el-icon><ChatLineSquare /></el-icon></span>
            <div>
              <span class="result-detail__label">文本内容</span>
              <strong>{{ result.text }}</strong>
            </div>
          </article>

          <article v-if="result.location" class="result-detail result-detail--wide">
            <span class="result-detail__icon"><el-icon><Location /></el-icon></span>
            <div>
              <span class="result-detail__label">签到位置</span>
              <strong>{{ result.location }}</strong>
            </div>
          </article>
        </div>

        <section v-if="result.imageUrls.length" class="checkin-result__images">
          <div class="checkin-result__section-title">
            <span><el-icon><Picture /></el-icon>签到图片</span>
            <small>{{ result.imageUrls.length }} 张</small>
          </div>
          <div class="checkin-result__image-grid">
            <el-image
              v-for="(url, index) in result.imageUrls"
              :key="`${url}-${index}`"
              :src="url"
              :preview-src-list="result.imageUrls"
              :initial-index="index"
              fit="cover"
              preview-teleported
            />
          </div>
        </section>

        <footer class="checkin-result__footer">
          <span class="checkin-result__time">
            <el-icon><Clock /></el-icon>
            完成于 {{ result.completedAt }}
          </span>
          <el-button type="primary" size="large" @click="close">完成</el-button>
        </footer>
      </main>
    </div>
  </el-dialog>
</template>

<script setup>
import {
  ChatLineSquare,
  CircleCheckFilled,
  Clock,
  Close,
  Document,
  Location,
  OfficeBuilding,
  Picture,
} from '@element-plus/icons-vue'

defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  result: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue'])

function close() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
:global(.checkin-result-dialog.el-dialog) {
  max-width: calc(100vw - 32px);
  padding: 0;
  overflow: hidden;
  border: 1px solid rgba(186, 230, 253, 0.78);
  border-radius: 24px;
  background: #f8fbff;
  box-shadow: 0 30px 80px rgba(15, 23, 42, 0.24);
}

:global(.checkin-result-dialog .el-dialog__header),
:global(.checkin-result-dialog .el-dialog__body) {
  margin: 0;
  padding: 0;
}

.checkin-result__hero {
  position: relative;
  display: flex;
  align-items: center;
  gap: 18px;
  min-height: 150px;
  padding: 28px 30px;
  overflow: hidden;
  color: #fff;
  background:
    radial-gradient(circle at 88% 10%, rgba(255, 255, 255, 0.28), transparent 28%),
    linear-gradient(135deg, #2563eb 0%, #0ea5e9 48%, #10b981 100%);
}

.checkin-result__hero::after {
  content: "";
  position: absolute;
  width: 170px;
  height: 170px;
  right: -70px;
  bottom: -110px;
  border: 28px solid rgba(255, 255, 255, 0.1);
  border-radius: 50%;
}

.checkin-result__success-icon {
  position: relative;
  z-index: 1;
  width: 62px;
  height: 62px;
  display: grid;
  flex: none;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.36);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.34);
  backdrop-filter: blur(12px);
}

.checkin-result__success-icon .el-icon { font-size: 34px; }
.checkin-result__heading { position: relative; z-index: 1; min-width: 0; }
.checkin-result__eyebrow { font-size: 10px; font-weight: 800; letter-spacing: 0.16em; opacity: 0.74; }
.checkin-result__heading h2 { margin: 5px 0 4px; color: #fff; font-size: 26px; letter-spacing: -0.04em; }
.checkin-result__heading p { margin: 0; color: rgba(255, 255, 255, 0.82); font-size: 13px; }

.checkin-result__close {
  position: absolute;
  z-index: 2;
  top: 18px;
  right: 18px;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.12);
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}

.checkin-result__close:hover { background: rgba(15, 23, 42, 0.24); transform: scale(1.04); }
.checkin-result__content { padding: 24px; }
.checkin-result__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }

.result-detail {
  display: flex;
  gap: 12px;
  min-width: 0;
  padding: 16px;
  border: 1px solid rgba(191, 219, 254, 0.72);
  border-radius: 16px;
  background: linear-gradient(145deg, #fff, #f0f7ff);
}

.result-detail--wide { grid-column: 1 / -1; }
.result-detail__icon {
  width: 36px;
  height: 36px;
  display: grid;
  flex: none;
  place-items: center;
  color: #2563eb;
  border-radius: 11px;
  background: #dbeafe;
}

.result-detail > div { min-width: 0; }
.result-detail__label { display: block; margin-bottom: 6px; color: #64748b; font-size: 11px; font-weight: 700; }
.result-detail strong { display: block; color: #172033; font-size: 14px; line-height: 1.55; overflow-wrap: anywhere; }

.checkin-result__images { margin-top: 18px; }
.checkin-result__section-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; color: #334155; }
.checkin-result__section-title span { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 750; }
.checkin-result__section-title small { color: #64748b; }
.checkin-result__image-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.checkin-result__image-grid .el-image {
  width: 100%;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: #eff6ff;
  cursor: zoom-in;
}

.checkin-result__footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 22px; padding-top: 18px; border-top: 1px solid #e2e8f0; }
.checkin-result__time { display: flex; align-items: center; gap: 7px; color: #64748b; font-size: 12px; font-variant-numeric: tabular-nums; }
.checkin-result__footer .el-button { min-width: 138px; }

@media (max-width: 560px) {
  .checkin-result__hero { min-height: 132px; padding: 22px 20px; }
  .checkin-result__success-icon { width: 52px; height: 52px; border-radius: 17px; }
  .checkin-result__heading h2 { font-size: 22px; }
  .checkin-result__heading p { max-width: 220px; font-size: 12px; }
  .checkin-result__content { padding: 16px; }
  .checkin-result__grid { grid-template-columns: 1fr; }
  .result-detail--wide { grid-column: auto; }
  .checkin-result__image-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .checkin-result__footer { align-items: stretch; flex-direction: column; }
  .checkin-result__footer .el-button { width: 100%; }
}
</style>
