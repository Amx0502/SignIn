import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

test('account management exposes guarded batch deletion controls', async () => {
  const source = await readFile(
    new URL('../views/Accounts.vue', import.meta.url),
    'utf8',
  )

  assert.match(source, /type="selection"/)
  assert.match(source, /批量删除/)
  assert.match(source, /selectedAccounts/)
  assert.match(source, /batchDeleting/)
  assert.match(source, /getAccountDeleteIndexes/)
  assert.match(source, /deleteSelectedAccounts/)
})

test('task management exposes guarded batch deletion controls', async () => {
  const source = await readFile(
    new URL('../views/TaskManagement.vue', import.meta.url),
    'utf8',
  )

  assert.match(source, /<el-checkbox/)
  assert.match(source, /批量删除/)
  assert.match(source, /selectedTaskKeys/)
  assert.match(source, /batchDeleting/)
  assert.match(source, /getTaskDeleteTargets/)
  assert.match(source, /deleteSelectedTasks/)
})
