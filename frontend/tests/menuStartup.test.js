import test from 'node:test'
import assert from 'node:assert/strict'

import { bootstrapMenuSync } from '../src/menu/menuStartup.js'


test('bootstrapMenuSync keeps realtime recovery running after the initial request fails', async () => {
  const calls = []

  const result = await bootstrapMenuSync({
    hydrate: () => calls.push('hydrate'),
    refresh: async () => {
      calls.push('refresh')
      throw new Error('temporary outage')
    },
    ensureAllowed: async () => calls.push('ensureAllowed'),
    startStream: () => calls.push('startStream'),
  })

  assert.deepEqual(calls, [
    'hydrate',
    'refresh',
    'ensureAllowed',
    'startStream',
  ])
  assert.equal(result.initialLoadFailed, true)
})
