import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { useClassCube } from '../src/composables/useClassCube.js'
import { latestSyncedDayItems } from '../src/utils/classCubeItems.js'


test('latestSyncedDayItems keeps only items from the most recent synced day', () => {
  const items = [
    { id: 1, synced_at: '2026-08-01T09:00:00' },
    { id: 2, synced_at: '2026-08-02T09:00:00' },
    { id: 3, synced_at: '2026-08-02T10:00:00' },
    { id: 4, synced_at: '' },
  ]
  assert.deepEqual(
    latestSyncedDayItems(items).map(item => item.id),
    [2, 3],
  )
})


test('latestSyncedDayItems returns empty for empty input', () => {
  assert.deepEqual(latestSyncedDayItems([]), [])
  assert.deepEqual(latestSyncedDayItems(null), [])
  assert.deepEqual(latestSyncedDayItems(undefined), [])
})


test('latestSyncedDayItems returns all items when no synced date exists', () => {
  const items = [{ id: 1, synced_at: null }, { id: 2 }]
  assert.equal(latestSyncedDayItems(items).length, 2)
})


test('syncItems reuses the sync response instead of a second list request', async () => {
  const calls = []
  const fresh = [
    { id: 1, synced_at: '2026-08-01T09:00:00' },
    { id: 2, synced_at: '2026-08-02T09:00:00' },
  ]
  const api = {
    syncItems: async courseId => {
      calls.push(['sync', courseId])
      return { ok: true, data: fresh }
    },
    listItems: async () => {
      calls.push(['list'])
      return { ok: true, data: [] }
    },
  }
  const cube = useClassCube(api)
  const result = await cube.syncItems(7)

  assert.deepEqual(calls, [['sync', 7]])
  assert.deepEqual(result.map(item => item.id), [2])
  assert.equal(cube.itemsSyncing.value, false)
})


test('loadItems requests latest-only items from the backend', async () => {
  const calls = []
  const api = {
    listItems: async (courseId, params) => {
      calls.push([courseId, params])
      return {
        ok: true,
        data: [{ id: 1, synced_at: '2026-08-02T09:00:00' }],
      }
    },
  }
  const cube = useClassCube(api)
  cube.selectedCourseId.value = 5
  const result = await cube.loadItems(5)

  assert.deepEqual(calls, [[5, { latest_only: 1 }]])
  assert.deepEqual(result.map(item => item.id), [1])
})


test('checkin panel keeps the list visible and uses a light sync button state', async () => {
  const source = await readFile(
    new URL(
      '../src/components/class-cube/AccountCheckinPanel.vue',
      import.meta.url,
    ),
    'utf8',
  )

  assert.match(source, /itemsSyncing \|\| itemsLoading/)
  assert.match(source, /el-skeleton v-if="itemsLoading && !items\.length"/)
  assert.match(source, /itemsSyncing: \{ type: Boolean, default: false \}/)
  assert.match(source, /v-if="itemsSyncing"/)
  assert.match(source, /class="sync-tag"/)
})


test('composable exports itemsSyncing so the button loading is wired', async () => {
  const source = await readFile(
    new URL('../src/composables/useClassCube.js', import.meta.url),
    'utf8',
  )

  assert.match(source, /const itemsSyncing = ref\(false\)/)
  assert.match(source, /itemsSyncing,\r?\n    error,/)
  assert.doesNotMatch(source, /syncingItems/)
})


test('account page shows a light toast after syncing items', async () => {
  const source = await readFile(
    new URL('../src/views/ClassCubeAccounts.vue', import.meta.url),
    'utf8',
  )

  assert.match(source, /handleSyncItems/)
  assert.match(source, /items-syncing="itemsSyncing"/)
  assert.match(source, /ElMessage\.success/)
})
