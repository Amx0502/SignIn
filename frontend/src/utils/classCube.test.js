import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createUploadGenerationGuard,
  normalizeQrSession,
  reconcileSelection,
  requiredFieldsForMode,
} from './classCube.js'
import { useClassCube } from '../composables/useClassCube.js'

test('returns fields required by each check-in mode', () => {
  assert.deepEqual(requiredFieldsForMode('qr'), [])
  assert.deepEqual(requiredFieldsForMode('gps'), ['latitude', 'longitude', 'accuracy'])
  assert.deepEqual(
    requiredFieldsForMode('gps_photo'),
    ['latitude', 'longitude', 'accuracy', 'photoPath'],
  )
  assert.deepEqual(requiredFieldsForMode('password'), ['password'])
  assert.deepEqual(requiredFieldsForMode('unknown'), [])
})

test('normalizes QR lifetime from expires_in_seconds only', () => {
  const session = normalizeQrSession(
    {
      token: 'qr-token',
      qr_image: 'data:image/png;base64,AA==',
      expires_in_seconds: 120,
      expires_at: 1,
    },
    5_000,
  )

  assert.deepEqual(session, {
    token: 'qr-token',
    qrImage: 'data:image/png;base64,AA==',
    status: 'pending',
    retryable: false,
    expiresInSeconds: 120,
    deadlineMs: 125_000,
  })
})

test('clamps invalid QR lifetime instead of trusting remote timestamps', () => {
  const session = normalizeQrSession(
    { expires_in_seconds: -10, expires_at: 999_999_999 },
    2_000,
  )

  assert.equal(session.expiresInSeconds, 0)
  assert.equal(session.deadlineMs, 2_000)
})

test('keeps selected item by stable id after refresh', () => {
  const refreshed = [{ id: 1 }, { id: 2, name: 'fresh' }]
  assert.deepEqual(reconcileSelection(refreshed, 2), { id: 2, name: 'fresh' })
})

test('clears selection when the stable id no longer exists', () => {
  assert.equal(reconcileSelection([{ id: 1 }], 2), null)
  assert.equal(reconcileSelection(null, 1), null)
})

function createComposableApi(overrides = {}) {
  const response = { ok: true, data: [] }
  return {
    listAccounts: async () => response,
    listCourses: async () => response,
    listItems: async () => response,
    listTasks: async () => response,
    listRuns: async () => response,
    ...overrides,
  }
}

test('unwraps direct action responses to their data contract', async () => {
  const calls = []
  const api = createComposableApi({
    uploadPhoto: async (...args) => {
      calls.push(['uploadPhoto', ...args])
      return { ok: true, data: { photo_path: 'owner/photo.jpg' } }
    },
    manualCheckin: async (...args) => {
      calls.push(['manualCheckin', ...args])
      return { ok: true, data: { status: 'success' } }
    },
    updateAccount: async (...args) => {
      calls.push(['updateAccount', ...args])
      return { ok: true, data: { id: 3, name: '新备注' } }
    },
    deleteAccount: async (...args) => {
      calls.push(['deleteAccount', ...args])
      return { ok: true, data: true }
    },
    deleteTask: async (...args) => {
      calls.push(['deleteTask', ...args])
      return { ok: true, data: true }
    },
    runTask: async (...args) => {
      calls.push(['runTask', ...args])
      return { ok: true, data: { accepted: true } }
    },
    retryClaim: async (...args) => {
      calls.push(['retryClaim', ...args])
      return { ok: true, data: { state: 'retryable' } }
    },
  })
  const state = useClassCube(api)

  assert.deepEqual(await state.uploadPhoto('file', 3), {
    photo_path: 'owner/photo.jpg',
  })
  assert.deepEqual(await state.manualCheckin(9, {
    latitude: 1,
    longitude: 2,
    accuracy: 3,
    photoPath: 'owner/photo.jpg',
  }), { status: 'success' })
  assert.deepEqual(await state.updateAccount(3, { name: '新备注' }), {
    id: 3,
    name: '新备注',
  })
  assert.equal(await state.deleteAccount(3), true)
  assert.equal(await state.deleteTask(8), true)
  assert.deepEqual(await state.runTask(8), { accepted: true })
  assert.deepEqual(await state.retryClaim(7), { state: 'retryable' })
  assert.deepEqual(calls[1], [
    'manualCheckin',
    9,
    {
      latitude: 1,
      longitude: 2,
      accuracy: 3,
      photo_path: 'owner/photo.jpg',
    },
  ])
  assert.equal(calls.length, 7)
})

test('preserves stored task password when an edit payload is blank', async () => {
  const updates = []
  const api = createComposableApi({
    updateTask: async (id, payload) => {
      updates.push([id, payload])
      return { ok: true, data: { id } }
    },
  })
  const state = useClassCube(api)

  await state.saveTask({
    id: 5,
    name: '任务',
    has_password: true,
    password: '',
  }, 5)
  await state.saveTask({
    name: '任务',
    password: '',
    clear_password: true,
  }, 5)

  assert.deepEqual(updates[0], [
    5,
    { name: '任务' },
  ])
  assert.deepEqual(updates[1], [
    5,
    { name: '任务', clear_password: true },
  ])
})

test('persists run filters for background refreshes', async () => {
  const runParams = []
  const api = createComposableApi({
    listRuns: async params => {
      runParams.push({ ...params })
      return { ok: true, data: [] }
    },
  })
  const state = useClassCube(api)

  await state.loadRuns({
    owner_user_id: 2,
    status: 'failed',
    limit: 50,
    offset: 100,
  })
  await state.refreshBackground()

  assert.deepEqual(runParams, [
    { owner_user_id: 2, status: 'failed', limit: 50, offset: 100 },
    { owner_user_id: 2, status: 'failed', limit: 50, offset: 100 },
  ])
})

test('keeps only the latest account course response and clears stale children immediately', async () => {
  const pending = new Map()
  const api = createComposableApi({
    listCourses: accountId => new Promise(resolve => pending.set(accountId, resolve)),
  })
  const state = useClassCube(api)
  state.courses.value = [{ id: 99, account_id: 99 }]
  state.items.value = [{ id: 88, course_id: 99 }]
  state.selectedCourseId.value = 99
  state.selectedItemId.value = 88

  const first = state.selectAccount(1)
  assert.deepEqual(state.courses.value, [])
  assert.deepEqual(state.items.value, [])
  assert.equal(state.selectedCourseId.value, null)
  assert.equal(state.selectedItemId.value, null)
  assert.equal(state.coursesLoading.value, true)

  const second = state.selectAccount(2)
  pending.get(2)({ ok: true, data: [{ id: 22, account_id: 2 }] })
  await second
  pending.get(1)({ ok: true, data: [{ id: 11, account_id: 1 }] })
  await first

  assert.deepEqual(state.courses.value, [{ id: 22, account_id: 2 }])
  assert.equal(state.selectedCourseId.value, 22)
  assert.equal(state.coursesLoading.value, false)
})

test('keeps only the latest course item response and clears stale items immediately', async () => {
  const pending = new Map()
  const api = createComposableApi({
    listItems: courseId => new Promise(resolve => pending.set(courseId, resolve)),
  })
  const state = useClassCube(api)
  state.items.value = [{ id: 88, course_id: 8 }]
  state.selectedItemId.value = 88

  const first = state.selectCourse(1)
  assert.deepEqual(state.items.value, [])
  assert.equal(state.selectedItemId.value, null)
  assert.equal(state.itemsLoading.value, true)

  const second = state.selectCourse(2)
  pending.get(2)({ ok: true, data: [{ id: 202, course_id: 2 }] })
  await second
  pending.get(1)({ ok: true, data: [{ id: 101, course_id: 1 }] })
  await first

  assert.deepEqual(state.items.value, [{ id: 202, course_id: 2 }])
  assert.equal(state.selectedItemId.value, 202)
  assert.equal(state.itemsLoading.value, false)
})

test('exposes an error QR session when session creation fails', async () => {
  const api = createComposableApi({
    createQrSession: async () => {
      throw new Error('二维码服务不可用')
    },
  })
  const state = useClassCube(api)

  await assert.rejects(state.startQrLogin(), /二维码服务不可用/)
  assert.equal(state.qrSession.value.status, 'error')
  assert.equal(state.qrSession.value.retryable, true)
  assert.equal(state.qrRemainingSeconds.value, 0)
})

test('rejects a deferred photo upload after its form identity is invalidated', async () => {
  let resolveUpload
  const upload = new Promise(resolve => { resolveUpload = resolve })
  const guard = createUploadGenerationGuard()
  const ticket = guard.begin('account:1/course:2/item:3/gps_photo')
  let applied = null
  const completion = upload.then(result => {
    if (guard.isCurrent(ticket, 'account:1/course:2/item:3/gps_photo')) {
      applied = result
    }
  })

  guard.invalidate()
  resolveUpload({ path: 'class-cube/1/old.jpg' })
  await completion

  assert.equal(applied, null)
  assert.equal(
    guard.isCurrent(ticket, 'account:1/course:2/item:3/gps_photo'),
    false,
  )
})
