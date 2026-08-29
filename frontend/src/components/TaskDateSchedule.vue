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
      <div class="calendar-head">
        <el-button circle plain size="small" :icon="ArrowLeft" aria-label="上个月" @click="moveMonth(-1)" />
        <div class="calendar-title">
          <strong>{{ visibleYear }} 年 {{ visibleMonthNumber }} 月</strong>
          <button type="button" @click="goToday">回到本月</button>
        </div>
        <el-button circle plain size="small" :icon="ArrowRight" aria-label="下个月" @click="moveMonth(1)" />
      </div>

      <div class="weekday-grid">
        <el-tooltip
          v-for="(label, index) in weekdays"
          :key="label"
          :content="weekdayTip(index)"
          placement="top"
        >
          <button
            type="button"
            class="weekday-button"
            :class="columnClass(index)"
            :disabled="skipWeekends && index >= 5"
            @click="toggleWeekday(index)"
          >
            <span>{{ label }}</span>
            <i></i>
          </button>
        </el-tooltip>
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
            :title="dateCellTitle(cell)"
            @click="toggleDate(cell.key)"
          >
            <span>{{ cell.day }}</span>
            <small>{{ dateCellStatus(cell) }}</small>
          </button>
        </span>
      </div>

      <div class="calendar-actions">
        <el-button size="small" plain @click="applyWorkdays">{{ workdayActionLabel }}</el-button>
        <el-button size="small" plain @click="applyWholeMonth">{{ monthActionLabel }}</el-button>
        <el-button size="small" plain type="danger" @click="clearMonth">{{ clearActionLabel }}</el-button>
      </div>

      <div class="date-summary">
        <span class="date-summary__mark"></span>
        <span>
          本月{{ dateMode === 'daily' ? '计划' : '已选' }} {{ monthSummary.base }} 天，
          <template v-if="monthSummary.explicitSkip">单独排除 {{ monthSummary.explicitSkip }} 天，</template>
          <template v-if="skipWeekends">周末规则跳过 {{ monthSummary.weekendSkip }} 天，</template>
          实际执行 <strong>{{ monthSummary.effective }}</strong> 天
        </span>
      </div>
    </div>

    <p class="date-schedule__hint">
      点击星期标题可批量切换本月整列；点击单个日期可单独调整。周末跳过只暂停周末计划，关闭后会恢复原选择。
    </p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({
  dateMode: { type: String, default: 'daily' },
  runDates: { type: Array, default: () => [] },
  skipDates: { type: Array, default: () => [] },
  skipWeekends: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:dateMode',
  'update:runDates',
  'update:skipDates',
  'update:skipWeekends',
])

const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const today = new Date()
const visibleMonth = ref(new Date(today.getFullYear(), today.getMonth(), 1))

const visibleYear = computed(() => visibleMonth.value.getFullYear())
const visibleMonthIndex = computed(() => visibleMonth.value.getMonth())
const visibleMonthNumber = computed(() => visibleMonthIndex.value + 1)
const runDateSet = computed(() => new Set(props.runDates || []))
const skipDateSet = computed(() => new Set(props.skipDates || []))

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

function moveMonth(offset) {
  visibleMonth.value = new Date(
    visibleYear.value,
    visibleMonthIndex.value + offset,
    1,
  )
}

function goToday() {
  visibleMonth.value = new Date(today.getFullYear(), today.getMonth(), 1)
}

function weekdayTip(index) {
  if (props.skipWeekends && index >= 5) return '当前已启用周末跳过，关闭后可安排周末日期'
  if (props.dateMode === 'specific') return `选择或取消本月全部${weekdays[index]}`
  return `批量设置或恢复本月${weekdays[index]}的签到计划`
}

function dateCellStatus(item) {
  if (isExplicitSkip(item.key)) return '不签到'
  if (props.skipWeekends && isWeekend(item.date) && isBaseSelected(item.key)) return '周末跳过'
  return isBaseSelected(item.key) ? '执行' : ''
}

function dateCellTitle(item) {
  const status = dateCellStatus(item) || '不执行'
  return `${item.key} · ${status}`
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

const monthSummary = computed(() => {
  const base = props.dateMode === 'daily'
    ? monthDates.value.length
    : monthDates.value.filter(item => isBaseSelected(item.key)).length
  const explicitSkip = monthDates.value.filter(item => (
    isExplicitSkip(item.key)
  )).length
  const weekendSkip = props.skipWeekends
    ? monthDates.value.filter(item => (
      isBaseSelected(item.key)
      && !skipDateSet.value.has(item.key)
      && isWeekend(item.date)
    )).length
    : 0
  const effective = monthDates.value.filter(isEffective).length
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
</script>

<style scoped>
.date-schedule { width: 100%; }
.date-schedule__controls { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.date-schedule__calendar { overflow: hidden; border: 1px solid #dbeafe; border-radius: 16px; background: linear-gradient(160deg, #fff, #f8fbff); box-shadow: 0 12px 30px rgb(37 99 235 / 7%); }
.calendar-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 12px 14px 10px; border-bottom: 1px solid #eaf1fb; }
.calendar-title { display: flex; align-items: baseline; gap: 8px; color: #1e293b; }
.calendar-title strong { font-size: 14px; }
.calendar-title button { padding: 0; border: 0; color: #3b82f6; background: transparent; cursor: pointer; font-size: 11px; }
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
.date-schedule__hint { margin: 7px 2px 0; color: #94a3b8; font-size: 11px; line-height: 1.5; }

@media (max-width: 520px) {
  .date-schedule__controls { align-items: flex-start; flex-direction: column; }
  .date-cell { min-height: 40px; border-radius: 8px; }
  .date-cell small { display: none; }
  .calendar-actions :deep(.el-button) { flex: 1; padding-right: 7px; padding-left: 7px; }
}
</style>
