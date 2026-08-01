import test from 'node:test'
import assert from 'node:assert/strict'

import { syncAfterManualCheckin } from '../src/utils/classCubeCheckin.js'

test('syncAfterManualCheckin syncs once after a successful check-in', async () => {
  let calls = 0
  const result = { status: 'success', message: '签到成功' }

  const returned = await syncAfterManualCheckin(result, async () => {
    calls += 1
  })

  assert.equal(calls, 1)
  assert.deepEqual(returned, result)
})

test('syncAfterManualCheckin does not sync failed check-ins', async () => {
  let calls = 0

  await syncAfterManualCheckin(
    { status: 'failed' },
    async () => { calls += 1 },
  )

  assert.equal(calls, 0)
})

