import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

async function source(relativePath) {
  return readFile(new URL(relativePath, import.meta.url), 'utf8')
}

test('class cube page owns state and exposes all three workflows', async () => {
  const page = await source('../views/ClassCube.vue')
  assert.match(page, /useClassCube/)
  assert.match(page, /账号与签到/)
  assert.match(page, /自动任务/)
  assert.match(page, /运行记录/)
  assert.match(page, /QrLoginDialog/)
  assert.match(page, /AccountCheckinPanel/)
  assert.match(page, /AutoTaskPanel/)
  assert.match(page, /RunHistoryPanel/)
})

test('qr dialog exposes countdown and every session state', async () => {
  const dialog = await source('../components/class-cube/QrLoginDialog.vue')
  assert.match(dialog, /qrRemainingSeconds/)
  assert.match(dialog, /pending/)
  assert.match(dialog, /success/)
  assert.match(dialog, /expired/)
  assert.match(dialog, /error/)
  assert.match(dialog, /重新生成/)
  assert.doesNotMatch(dialog, /v-html/)
})

test('manual check-in panel renders every mode and sync action', async () => {
  const panel = await source('../components/class-cube/AccountCheckinPanel.vue')
  assert.match(panel, /二维码签到/)
  assert.match(panel, /GPS 签到/)
  assert.match(panel, /GPS\+拍照签到/)
  assert.match(panel, /密码签到/)
  assert.match(panel, /gps_photo/)
  assert.match(panel, /同步签到项/)
  assert.match(panel, /photo_path/)
  assert.doesNotMatch(panel, /v-html/)
})

test('automatic task table keeps stable selection and password semantics', async () => {
  const panel = await source('../components/class-cube/AutoTaskPanel.vue')
  assert.match(panel, /row-key="id"/)
  assert.match(panel, /reserve-selection/)
  assert.match(panel, /批量删除\(\{\{\s*selectedTaskIds\.size\s*\}\}\)/)
  assert.match(panel, /has_password/)
  assert.match(panel, /clear_password/)
  assert.match(panel, /立即执行/)
  assert.doesNotMatch(panel, /v-html/)
})

test('run history supports complete filters and unknown confirmation', async () => {
  const panel = await source('../components/class-cube/RunHistoryPanel.vue')
  assert.match(panel, /owner_user_id/)
  assert.match(panel, /account_id/)
  assert.match(panel, /course_id/)
  assert.match(panel, /task_id/)
  assert.match(panel, /waiting_parameter/)
  assert.match(panel, /unknown_result/)
  assert.match(panel, /确认重试/)
  assert.doesNotMatch(panel, /v-html/)
})

test('class cube route uses the correct first and second level breadcrumb', async () => {
  const router = await source('../router/index.js')
  assert.match(
    router,
    /path:\s*['"]\/class-cube['"][\s\S]*title:\s*['"]签到管理['"][\s\S]*parentTitle:\s*['"]班级魔方['"]/,
  )
})
