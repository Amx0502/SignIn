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
