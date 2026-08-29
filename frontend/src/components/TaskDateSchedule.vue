<template>
  <div class="date-schedule">
    <div class="date-schedule__controls">
      <el-radio-group
        :model-value="dateMode"
        size="small"
        @change="emit('update:dateMode', $event)"
      >
        <el-radio-button value="daily">每天执行</el-radio-button>
        <el-radio-button value="specific">指定日期</el-radio-button>
      </el-radio-group>
      <el-checkbox
        :model-value="skipWeekends"
        @change="emit('update:skipWeekends', Boolean($event))"
      >周末跳过</el-checkbox>
    </div>

    <div class="date-schedule__calendar">
      <div
        :key="monthViewKey"
        class="calendar-month-view"
        :class="[
          monthAnimationClass,
          { 'is-swiping': isSwiping, 'is-resetting': isSwipeResetting },
        ]"
        :style="monthSwipeStyle"
        @pointerdown="onMonthPointerDown"
        @pointermove="onMonthPointerMove"
        @pointerup="onMonthPointerUp"
        @pointercancel="onMonthPointerCancel"
        @lostpointercapture="onMonthPointerCancel"
        @click.capture="onMonthClickCapture"
      >
        <div class="calendar-head">
          <el-button circle plain size="small" :icon="ArrowLeft" aria-label="上个月" @click="moveMonth(-1)" />
          <div class="calendar-title">
            <strong aria-live="polite">{{ visibleYear }} 年 {{ visibleMonthNumber }} 月</strong>
            <button type="button" @click="goToday">回到本月</button>
          </div>
          <el-button circle plain size="small" :icon="ArrowRight" aria-label="下个月" @click="moveMonth(1)" />
        </div>

        <div class="weekday-grid">
          <button
            v-for="(label, index) in weekdays"
            :key="label"
            type="button"
            class="weekday-button"
            :class="columnClass(index)"
            :disabled="skipWeekends && index >= 5"
            @click="toggleWeekday(index)"
          >
            <span>{{ label }}</span>
            <i></i>
          </button>
        </div>

        <div class="date-grid">
          <span v-for="cell in calendarCells" :key="cell.id" class="date-cell-wrap">
            <button
              v-if="!cell.blank"
              type="button"
              class="date-cell"
              :class="dateCellClass(cell)"
              :disabled="skipWeekends && isWeekend(cell.date)"
              :aria-pressed="isBaseSelected(cell.key)"
              @click="toggleDate(cell.key)"
            >
              <span>{{ cell.day }}</span>
              <small>{{ dateCellStatus(cell) }}</small>
            </button>
          </span>
        </div>
      </div>

      <div class="calendar-actions">
        <el-button size="small" plain @click="applyWorkdays">{{ workdayActionLabel }}</el-button>
        <el-button size="small" plain @click="applyWholeMonth">{{ monthActionLabel }}</el-button>
        <el-button size="small" plain type="danger" @click="clearMonth">{{ clearActionLabel }}</el-button>
        <el-button
          v-if="dateMode === 'specific'"
          size="small"
          type="danger"
          :disabled="!runDates.length"
          @click="clearAllDates"
        >清空全部</el-button>
      </div>

      <div class="date-summary">
        <span class="date-summary__mark"></span>
        <span v-if="dateMode === 'daily'">
          全部计划：每天执行，单独排除 {{ planSummary.explicitSkip }} 天，
          {{ skipWeekends ? '周末不执行' : '周末正常执行' }}
        </span>
        <span v-else>
          全部计划已选 {{ planSummary.base }} 天，
          单独排除 {{ planSummary.explicitSkip }} 天，
          <template v-if="skipWeekends">周末规则跳过 {{ planSummary.weekendSkip }} 天，</template>
          实际执行 <strong>{{ planSummary.effective }}</strong> 天
        </span>
      </div>
    </div>

    <div v-if="dateMode === 'specific'" class="date-schedule__completion">
      <el-checkbox
        :model-value="autoDisableAfterFinish"
        @change="emit('update:autoDisableAfterFinish', Boolean($event))"
      >最后一次计划执行完成后自动关闭任务</el-checkbox>
      <span>
        最后一次计划：<strong>{{ lastOccurrenceText }}</strong>
      </span>
    </div>

  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const props = defineProps({
  dateMode: { type: String, default: 'daily' },
  runDates: { type: Array, default: () => [] },
  skipDates: { type: Array, default: () => [] },
  skipWeekends: { type: Boolean, default: false },
  times: { type: Array, default: () => [] },
  autoDisableAfterFinish: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:dateMode',
  'update:runDates',
  'update:skipDates',
  'update:skipWeekends',
  'update:autoDisableAfterFinish',
])

const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const today = new Date()
const visibleMonth = ref(new Date(today.getFullYear(), today.getMonth(), 1))

const visibleYear = computed(() => visibleMonth.value.getFullYear())
const visibleMonthIndex = computed(() => visibleMonth.value.getMonth())
const visibleMonthNumber = computed(() => visibleMonthIndex.value + 1)
const monthViewKey = computed(() => `${visibleYear.value}-${visibleMonthIndex.value}`)
const runDateSet = computed(() => new Set(props.runDates || []))
const skipDateSet = computed(() => new Set(props.skipDates || []))

const SWIPE_AXIS_LOCK = 8
const SWIPE_MIN_DISTANCE = 44
const SWIPE_MAX_DRAG_RATIO = 0.42
const monthAnimationClass = ref('')
const swipeOffset = ref(0)
const isSwiping = ref(false)
const isSwipeResetting = ref(false)
const monthSwipeStyle = computed(() => ({
  transform: `translate3d(${swipeOffset.value}px, 0, 0)`,
}))

let activePointerId = null
let pointerStartX = 0
let pointerStartY = 0
let pointerStartTime = 0
let pointerAxis = ''
let swipeAnimationTimer = null
let swipeResetTimer = null
let suppressClickUntil = 0

function dateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function sortDates(values) {
  return [...new Set(values)].sort()
}

function updateRunDates(values) {
  emit('update:runDates', sortDates(values))
}

function updateSkipDates(values) {
  emit('update:skipDates', sortDates(values))
}

function isWeekend(date) {
  return date.getDay() === 0 || date.getDay() === 6
}

const monthDates = computed(() => {
  const lastDay = new Date(
    visibleYear.value,
    visibleMonthIndex.value + 1,
    0,
  ).getDate()
  return Array.from({ length: lastDay }, (_, index) => {
    const date = new Date(visibleYear.value, visibleMonthIndex.value, index + 1)
    return {
      date,
      key: dateKey(date),
      day: index + 1,
      weekday: (date.getDay() + 6) % 7,
    }
  })
})

const calendarCells = computed(() => {
  const leading = monthDates.value[0]?.weekday || 0
  const cells = Array.from({ length: leading }, (_, index) => ({
    id: `blank-leading-${index}`,
    blank: true,
  }))
  cells.push(...monthDates.value.map(item => ({ ...item, id: item.key, blank: false })))
  while (cells.length % 7 !== 0) {
    cells.push({ id: `blank-trailing-${cells.length}`, blank: true })
  }
  return cells
})

function isBaseSelected(key) {
  if (props.dateMode === 'specific') return runDateSet.value.has(key)
  return !skipDateSet.value.has(key)
}

function isEffective(item) {
  if (!isBaseSelected(item.key)) return false
  if (skipDateSet.value.has(item.key)) return false
  return !(props.skipWeekends && isWeekend(item.date))
}

function isExplicitSkip(key) {
  return skipDateSet.value.has(key)
    && (props.dateMode === 'daily' || runDateSet.value.has(key))
}

function isToday(item) {
  return item.key === dateKey(today)
}

function toggleDate(key) {
  if (props.dateMode === 'specific') {
    const nextRunDates = new Set(props.runDates || [])
    if (nextRunDates.has(key)) {
      nextRunDates.delete(key)
    } else {
      nextRunDates.add(key)
      if (skipDateSet.value.has(key)) {
        updateSkipDates((props.skipDates || []).filter(value => value !== key))
      }
    }
    updateRunDates([...nextRunDates])
    return
  }

  const nextSkipDates = new Set(props.skipDates || [])
  if (nextSkipDates.has(key)) nextSkipDates.delete(key)
  else nextSkipDates.add(key)
  updateSkipDates([...nextSkipDates])
}

function datesInColumn(index) {
  return monthDates.value.filter(item => item.weekday === index)
}

function columnSelection(index) {
  const dates = datesInColumn(index)
  const selectedCount = dates.filter(item => isBaseSelected(item.key)).length
  return {
    all: dates.length > 0 && selectedCount === dates.length,
    partial: selectedCount > 0 && selectedCount < dates.length,
  }
}

function columnClass(index) {
  const state = columnSelection(index)
  return {
    'is-all': state.all,
    'is-partial': state.partial,
    'is-weekend-disabled': props.skipWeekends && index >= 5,
  }
}

function toggleWeekday(index) {
  if (props.skipWeekends && index >= 5) return
  const keys = datesInColumn(index).map(item => item.key)
  if (!keys.length) return

  if (props.dateMode === 'specific') {
    const nextRunDates = new Set(props.runDates || [])
    const allSelected = keys.every(key => nextRunDates.has(key))
    keys.forEach(key => {
      if (allSelected) nextRunDates.delete(key)
      else nextRunDates.add(key)
    })
    if (!allSelected) {
      const keySet = new Set(keys)
      updateSkipDates((props.skipDates || []).filter(value => !keySet.has(value)))
    }
    updateRunDates([...nextRunDates])
    return
  }

  const nextSkipDates = new Set(props.skipDates || [])
  const allSkipped = keys.every(key => nextSkipDates.has(key))
  keys.forEach(key => {
    if (allSkipped) nextSkipDates.delete(key)
    else nextSkipDates.add(key)
  })
  updateSkipDates([...nextSkipDates])
}

function setSpecificDates(keys, selected) {
  const next = new Set(props.runDates || [])
  keys.forEach(key => {
    if (selected) next.add(key)
    else next.delete(key)
  })
  updateRunDates([...next])
}

function restoreDailyDates(keys) {
  const keySet = new Set(keys)
  updateSkipDates((props.skipDates || []).filter(value => !keySet.has(value)))
}

function applyWorkdays() {
  const keys = monthDates.value
    .filter(item => item.weekday < 5)
    .map(item => item.key)
  if (props.dateMode === 'specific') {
    setSpecificDates(keys, true)
    restoreDailyDates(keys)
  } else {
    restoreDailyDates(keys)
  }
}

function applyWholeMonth() {
  const keys = monthDates.value
    .filter(item => !(props.skipWeekends && isWeekend(item.date)))
    .map(item => item.key)
  if (props.dateMode === 'specific') {
    setSpecificDates(keys, true)
    restoreDailyDates(keys)
  } else {
    restoreDailyDates(keys)
  }
}

function clearMonth() {
  const keys = monthDates.value.map(item => item.key)
  if (props.dateMode === 'specific') {
    setSpecificDates(keys, false)
    return
  }
  const next = new Set(props.skipDates || [])
  keys.forEach(key => next.add(key))
  updateSkipDates([...next])
}

async function clearAllDates() {
  const count = props.runDates.length
  if (!count) return
  try {
    await ElMessageBox.confirm(
      `将清空全部 ${count} 个指定执行日期，是否继续？`,
      '清空全部指定日期',
      {
        type: 'warning',
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
      },
    )
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    throw error
  }
  updateRunDates([])
}

function clearSwipeResetTimer() {
  if (swipeResetTimer) clearTimeout(swipeResetTimer)
  swipeResetTimer = null
}

function releasePointer(event) {
  const target = event?.currentTarget
  if (!target || activePointerId == null) return
  try {
    if (target.hasPointerCapture?.(activePointerId)) {
      target.releasePointerCapture(activePointerId)
    }
  } catch {
    // The browser may have released capture automatically after pointercancel.
  }
}

function resetPointerTracking() {
  activePointerId = null
  pointerAxis = ''
  pointerStartX = 0
  pointerStartY = 0
  pointerStartTime = 0
}

function settleSwipe() {
  clearSwipeResetTimer()
  isSwiping.value = false
  isSwipeResetting.value = true
  swipeOffset.value = 0
  swipeResetTimer = setTimeout(() => {
    isSwipeResetting.value = false
    swipeResetTimer = null
  }, 190)
}

function moveMonth(offset) {
  if (!offset) return
  clearSwipeResetTimer()
  if (swipeAnimationTimer) clearTimeout(swipeAnimationTimer)
  isSwiping.value = false
  isSwipeResetting.value = false
  swipeOffset.value = 0
  monthAnimationClass.value = offset > 0 ? 'is-entering-next' : 'is-entering-previous'
  visibleMonth.value = new Date(
    visibleYear.value,
    visibleMonthIndex.value + offset,
    1,
  )
  swipeAnimationTimer = setTimeout(() => {
    monthAnimationClass.value = ''
    swipeAnimationTimer = null
  }, 260)
}

function goToday() {
  const monthOffset = (
    (today.getFullYear() - visibleYear.value) * 12
    + today.getMonth()
    - visibleMonthIndex.value
  )
  if (monthOffset) moveMonth(monthOffset)
}

function onMonthPointerDown(event) {
  if (!['touch', 'pen'].includes(event.pointerType) || event.isPrimary === false) return
  clearSwipeResetTimer()
  activePointerId = event.pointerId
  pointerStartX = event.clientX
  pointerStartY = event.clientY
  pointerStartTime = performance.now()
  pointerAxis = ''
  isSwiping.value = false
  isSwipeResetting.value = false
  swipeOffset.value = 0
}

function onMonthPointerMove(event) {
  if (event.pointerId !== activePointerId) return
  const deltaX = event.clientX - pointerStartX
  const deltaY = event.clientY - pointerStartY
  const absX = Math.abs(deltaX)
  const absY = Math.abs(deltaY)

  if (!pointerAxis) {
    if (Math.max(absX, absY) < SWIPE_AXIS_LOCK) return
    pointerAxis = absX > absY * 1.1 ? 'horizontal' : 'vertical'
    if (pointerAxis === 'vertical') {
      resetPointerTracking()
      return
    }
    try {
      event.currentTarget.setPointerCapture?.(event.pointerId)
    } catch {
      // Pointer capture is an enhancement; the gesture still works without it.
    }
  }

  if (pointerAxis !== 'horizontal') return
  if (event.cancelable) event.preventDefault()
  isSwiping.value = true
  const maxDrag = event.currentTarget.clientWidth * SWIPE_MAX_DRAG_RATIO
  swipeOffset.value = Math.max(-maxDrag, Math.min(maxDrag, deltaX))
}

function onMonthPointerUp(event) {
  if (event.pointerId !== activePointerId) return
  const deltaX = event.clientX - pointerStartX
  const elapsed = Math.max(performance.now() - pointerStartTime, 1)
  const velocity = Math.abs(deltaX) / elapsed
  const threshold = Math.min(
    64,
    Math.max(SWIPE_MIN_DISTANCE, event.currentTarget.clientWidth * 0.13),
  )
  const wasHorizontal = pointerAxis === 'horizontal'
  const shouldChangeMonth = wasHorizontal && (
    Math.abs(deltaX) >= threshold
    || (Math.abs(deltaX) >= 28 && velocity >= 0.45)
  )

  if (wasHorizontal) {
    suppressClickUntil = Date.now() + 350
    if (event.cancelable) event.preventDefault()
  }
  releasePointer(event)
  resetPointerTracking()

  if (shouldChangeMonth) {
    moveMonth(deltaX < 0 ? 1 : -1)
  } else if (wasHorizontal) {
    settleSwipe()
  } else {
    swipeOffset.value = 0
    isSwiping.value = false
  }
}

function onMonthPointerCancel(event) {
  if (event.pointerId !== activePointerId) return
  releasePointer(event)
  resetPointerTracking()
  settleSwipe()
}

function onMonthClickCapture(event) {
  if (Date.now() >= suppressClickUntil) return
  event.preventDefault()
  event.stopPropagation()
}

onUnmounted(() => {
  if (swipeAnimationTimer) clearTimeout(swipeAnimationTimer)
  clearSwipeResetTimer()
})

function dateCellStatus(item) {
  if (isExplicitSkip(item.key)) return '不签到'
  if (props.skipWeekends && isWeekend(item.date) && isBaseSelected(item.key)) return '周末跳过'
  return isBaseSelected(item.key) ? '执行' : ''
}

function dateCellClass(item) {
  return {
    'is-selected': isEffective(item),
    'is-explicit-skip': isExplicitSkip(item.key),
    'is-weekend-suppressed': props.skipWeekends && isWeekend(item.date) && isBaseSelected(item.key),
    'is-today': isToday(item),
    'is-weekend': isWeekend(item.date),
    'is-disabled': props.skipWeekends && isWeekend(item.date),
  }
}

function dateFromKey(key) {
  const [year, month, day] = key.split('-').map(Number)
  return new Date(year, month - 1, day)
}

const planSummary = computed(() => {
  if (props.dateMode === 'daily') {
    return {
      base: null,
      explicitSkip: skipDateSet.value.size,
      weekendSkip: null,
      effective: null,
    }
  }

  const allRunDates = sortDates(props.runDates || [])
  const explicitSkip = allRunDates.filter(key => skipDateSet.value.has(key)).length
  const weekendSkip = props.skipWeekends
    ? allRunDates.filter(key => (
      !skipDateSet.value.has(key) && isWeekend(dateFromKey(key))
    )).length
    : 0
  const base = allRunDates.length
  const effective = base - explicitSkip - weekendSkip
  return { base, explicitSkip, weekendSkip, effective }
})

const workdayActionLabel = computed(() => (
  props.dateMode === 'specific' ? '选择工作日' : '恢复工作日'
))
const monthActionLabel = computed(() => (
  props.dateMode === 'specific' ? '选择整月' : '恢复整月'
))
const clearActionLabel = computed(() => (
  props.dateMode === 'specific' ? '清空本月' : '本月全不签到'
))

function normalizePreviewTime(value) {
  const match = String(value || '').trim().match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/)
  if (!match) return null
  const hour = Number(match[1])
  const minute = Number(match[2])
  const second = Number(match[3] || 0)
  if (hour > 23 || minute > 59 || second > 59) return null
  return [hour, minute, second].map(part => String(part).padStart(2, '0')).join(':')
}

const lastOccurrenceText = computed(() => {
  const effectiveDates = sortDates(props.runDates || []).filter(key => {
    if (skipDateSet.value.has(key)) return false
    return !(props.skipWeekends && isWeekend(dateFromKey(key)))
  })
  const validTimes = (props.times || []).map(normalizePreviewTime).filter(Boolean).sort()
  if (!effectiveDates.length || !validTimes.length) return '请先设置有效日期和时间'
  return `${effectiveDates[effectiveDates.length - 1]} ${validTimes[validTimes.length - 1]}`
})
</script>

<style scoped>
.date-schedule { width: 100%; min-width: 0; max-width: 100%; }
.date-schedule__controls { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-width: 0; max-width: 100%; margin-bottom: 12px; }
.date-schedule__controls :deep(.el-radio-group) { flex-wrap: nowrap; }
.date-schedule__controls :deep(.el-checkbox) { flex: none; white-space: nowrap; }
.date-schedule__calendar { min-width: 0; max-width: 100%; overflow: hidden; border: 1px solid #dbeafe; border-radius: 16px; background: linear-gradient(160deg, #fff, #f8fbff); box-shadow: 0 12px 30px rgb(37 99 235 / 7%); }
.calendar-month-view { position: relative; touch-action: pan-y; user-select: none; will-change: transform, opacity; }
.calendar-month-view.is-swiping { transition: none; }
.calendar-month-view.is-resetting { transition: transform .19s cubic-bezier(.22, 1, .36, 1); }
.calendar-month-view.is-entering-next { animation: calendar-enter-next .24s cubic-bezier(.22, 1, .36, 1); }
.calendar-month-view.is-entering-previous { animation: calendar-enter-previous .24s cubic-bezier(.22, 1, .36, 1); }
.calendar-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 12px 14px 10px; border-bottom: 1px solid #eaf1fb; }
.calendar-title { display: flex; align-items: baseline; justify-content: center; gap: 10px; min-width: 0; color: #1e293b; }
.calendar-title strong { font-size: 14px; white-space: nowrap; }
.calendar-title button { padding: 0; border: 0; color: #3b82f6; background: transparent; cursor: pointer; font-size: 11px; white-space: nowrap; }
.weekday-grid, .date-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); }
.weekday-grid { padding: 8px 8px 3px; }
.weekday-button { display: grid; min-width: 0; padding: 5px 1px 4px; place-items: center; gap: 3px; border: 0; color: #64748b; background: transparent; cursor: pointer; font-size: 11px; }
.weekday-button i { width: 15px; height: 3px; border-radius: 99px; background: #dbe3ef; transition: all .2s ease; }
.weekday-button.is-all { color: #2563eb; font-weight: 700; }
.weekday-button.is-all i { width: 22px; background: #3b82f6; }
.weekday-button.is-partial i { background: linear-gradient(90deg, #3b82f6 50%, #dbe3ef 50%); }
.weekday-button.is-weekend-disabled { color: #b8c2d0; cursor: not-allowed; }
.date-grid { padding: 3px 8px 9px; gap: 4px 2px; }
.date-cell-wrap { min-width: 0; }
.date-cell { position: relative; display: flex; width: 100%; min-height: 45px; padding: 5px 1px 4px; align-items: center; justify-content: center; flex-direction: column; gap: 1px; border: 1px solid transparent; border-radius: 10px; color: #64748b; background: transparent; cursor: pointer; transition: transform .16s ease, box-shadow .16s ease, background .16s ease, border-color .16s ease; }
.date-cell:hover { z-index: 1; border-color: #93c5fd; transform: translateY(-1px); }
.date-cell:disabled { cursor: not-allowed; }
.date-cell:disabled:hover { border-color: transparent; transform: none; }
.date-cell > span { font-size: 12px; font-variant-numeric: tabular-nums; }
.date-cell small { min-height: 12px; color: inherit; font-size: 8px; line-height: 1; white-space: nowrap; }
.date-cell.is-selected { border-color: #60a5fa; color: #fff; background: linear-gradient(145deg, #3b82f6, #2563eb); box-shadow: 0 5px 11px rgb(37 99 235 / 20%); }
.date-cell.is-weekend { color: #8b5cf6; }
.date-cell.is-selected.is-weekend { color: #fff; background: linear-gradient(145deg, #6366f1, #4f46e5); }
.date-cell.is-explicit-skip { border-color: #fecaca; color: #dc2626; background: #fff1f2; }
.date-cell.is-weekend-suppressed { border-color: #d8dee8; color: #8b95a5; background: repeating-linear-gradient(135deg, #f8fafc, #f8fafc 5px, #eef2f7 5px, #eef2f7 10px); box-shadow: none; }
.date-cell.is-today::after { position: absolute; inset: 2px; border: 1px solid #0ea5e9; border-radius: 8px; content: ''; pointer-events: none; }
.calendar-actions { display: flex; flex-wrap: wrap; gap: 6px; padding: 10px 12px; border-top: 1px solid #eaf1fb; }
.calendar-actions :deep(.el-button + .el-button) { margin-left: 0; }
.date-summary { display: flex; align-items: flex-start; gap: 8px; padding: 9px 12px 11px; color: #64748b; background: #eff6ff; font-size: 11px; line-height: 1.55; }
.date-summary strong { color: #1d4ed8; }
.date-summary__mark { width: 7px; height: 7px; flex: none; margin-top: 5px; border-radius: 50%; background: #3b82f6; box-shadow: 0 0 0 4px rgb(59 130 246 / 12%); }
.date-schedule__completion { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 9px; padding: 10px 12px; border: 1px solid #dbeafe; border-radius: 12px; color: #64748b; background: #f8fbff; font-size: 11px; }
.date-schedule__completion :deep(.el-checkbox) { height: auto; min-width: 0; }
.date-schedule__completion :deep(.el-checkbox__label) { padding-left: 7px; color: #334155; font-size: 12px; white-space: normal; }
.date-schedule__completion > span { flex: none; text-align: right; }
.date-schedule__completion strong { color: #2563eb; font-variant-numeric: tabular-nums; }

@keyframes calendar-enter-next {
  from { opacity: .42; transform: translate3d(18%, 0, 0); }
  to { opacity: 1; transform: translate3d(0, 0, 0); }
}

@keyframes calendar-enter-previous {
  from { opacity: .42; transform: translate3d(-18%, 0, 0); }
  to { opacity: 1; transform: translate3d(0, 0, 0); }
}

@media (prefers-reduced-motion: reduce) {
  .calendar-month-view.is-resetting,
  .calendar-month-view.is-entering-next,
  .calendar-month-view.is-entering-previous {
    animation: none;
    transition: none;
  }
}

@media (max-width: 520px) {
  .date-schedule__controls { align-items: flex-start; flex-direction: column; }
  .date-cell { min-height: 40px; border-radius: 8px; }
  .date-cell small { display: none; }
  .calendar-actions :deep(.el-button) { flex: 1; padding-right: 7px; padding-left: 7px; }
  .date-schedule__completion { align-items: flex-start; flex-direction: column; }
  .date-schedule__completion > span { text-align: left; }
}
</style>
