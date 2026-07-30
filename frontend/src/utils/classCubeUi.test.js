import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

async function source(relativePath) {
  return readFile(new URL(relativePath, import.meta.url), 'utf8')
}

test('class cube exposes five independent second-level pages', async () => {
  const router = await source('../router/index.js')
  for (const path of ['/class-cube/overview', '/class-cube/accounts', '/class-cube/tasks', '/class-cube/runs', '/class-cube/logs']) {
    assert.match(router, new RegExp(`path:\\s*['"]${path}['"]`))
  }
  assert.match(router, /parentTitle:\s*['"]班级魔方['"]/)
  assert.match(await source('../views/ClassCubeAccounts.vue'), /AccountCheckinPanel/)
  assert.match(await source('../views/ClassCubeAccounts.vue'), /QrLoginDialog/)
  assert.match(await source('../views/ClassCubeTasks.vue'), /AutoTaskPanel/)
  assert.match(await source('../views/ClassCubeRuns.vue'), /RunHistoryPanel/)
  assert.match(await source('../views/ClassCubeLogs.vue'), /classCubeApi\.listLogs/)
})

test('class cube logs are separate from structured run records', async () => {
  const runs = await source('../views/ClassCubeRuns.vue')
  assert.doesNotMatch(runs, /loadLogs|cube-logs|setInterval/)
  const logs = await source('../views/ClassCubeLogs.vue')
  assert.doesNotMatch(logs, /xxqd/)
})

test('immediate execution warns when task parameters are missing', async () => {
  const panel = await source('../components/class-cube/AutoTaskPanel.vue')
  assert.match(panel, /data\.status === 'waiting_parameter'/)
  assert.match(panel, /ElMessage\.warning\(message\)/)
})

test('class cube task editor uses horizontal sections and account ownership', async () => {
  const panel = await source('../components/class-cube/AutoTaskPanel.vue')
  assert.match(panel, /width="min\(960px, 94vw\)"/)
  assert.match(panel, /class="editor-layout"/)
  assert.equal((panel.match(/class="editor-section/g) || []).length, 3)
  assert.match(panel, /grid-template-columns:repeat\(3,minmax\(0,1fr\)\)/)
  assert.match(panel, /@media\(max-width:900px\).*repeat\(2,minmax\(0,1fr\)\)/s)
  assert.match(panel, /account\?\.owner_user_id \?\? null/)
  assert.match(panel, /v-model="draft\.owner_user_id".*:disabled="true"/s)
})

test('readable class cube logs show business event labels', async () => {
  const logs = await source('../views/ClassCubeLogs.vue')
  assert.match(logs, /eventName\(item\.message\)/)
  assert.match(logs, /任务开始/)
  assert.match(logs, /签到扫描/)
  assert.match(logs, /签到结果/)
  assert.match(logs, /执行汇总/)
  assert.match(logs, /企业微信/)
})

test('qr dialog exposes countdown and every session state', async () => {
  const dialog = await source('../components/class-cube/QrLoginDialog.vue')
  assert.match(dialog, /qrRemainingSeconds/)
  for (const state of ['pending', 'success', 'expired', 'error']) assert.match(dialog, new RegExp(state))
  assert.doesNotMatch(dialog, /v-html/)
})

test('class cube route redirects the legacy page to overview', async () => {
  const router = await source('../router/index.js')
  assert.match(router, /path:\s*['"]\/class-cube['"]\s*,\s*redirect:\s*['"]\/class-cube\/overview['"]/)
})
