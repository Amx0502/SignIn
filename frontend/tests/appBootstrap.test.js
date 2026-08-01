import test from 'node:test'
import assert from 'node:assert/strict'

import { mountAppWhenRouterReady } from '../src/appBootstrap.js'


test('mountAppWhenRouterReady waits for the initial router navigation', async () => {
  const calls = []
  const app = {
    mount(root) {
      calls.push(`mount:${root}`)
      return 'mounted'
    },
  }
  let resolveReady
  const router = {
    isReady() {
      calls.push('router-ready')
      return new Promise(resolve => { resolveReady = resolve })
    },
  }

  const mounting = mountAppWhenRouterReady({ app, router, root: '#app' })
  await Promise.resolve()
  assert.deepEqual(calls, ['router-ready'])

  resolveReady()
  assert.equal(await mounting, 'mounted')
  assert.deepEqual(calls, ['router-ready', 'mount:#app'])
})
