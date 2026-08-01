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

test('bootstrapMenuSync does not start realtime sync after an unauthorized catalog request', async () => {
  const calls = []

  const result = await bootstrapMenuSync({
    hydrate: () => calls.push('hydrate'),
    refresh: async () => {
      const error = new Error('登录已过期')
      error.status = 401
      throw error
    },
    ensureAllowed: async () => calls.push('ensureAllowed'),
    startStream: () => calls.push('startStream'),
  })

  assert.deepEqual(calls, ['hydrate'])
  assert.equal(result.initialLoadFailed, true)
  assert.equal(result.unauthorized, true)
})
