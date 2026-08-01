import test from 'node:test'
import assert from 'node:assert/strict'

import {
  firstVisiblePath,
  flattenMenuCatalog,
  menuKeyIsVisible,
  resolveMenuRedirect,
  visibleMenuKeys,
} from '../src/menu/menuPermissions.js'
import { consumeSseChunk, watchMenuVersions } from '../src/menu/menuEvents.js'


const menus = [
  {
    key: 'xxqd',
    title: '小小签到',
    path: null,
    children: [
      { key: 'xxqd.accounts', title: '账号管理', path: '/accounts', children: [] },
      { key: 'xxqd.tasks', title: '任务管理', path: '/tasks', children: [] },
    ],
  },
  {
    key: 'class_cube',
    title: '班级魔方',
    path: null,
    children: [
      {
        key: 'class_cube.overview',
        title: '系统概览',
        path: '/class-cube/overview',
        children: [],
      },
    ],
  },
]


test('visibleMenuKeys includes parents and visible descendants', () => {
  assert.deepEqual(
    [...visibleMenuKeys(menus)],
    ['xxqd', 'xxqd.accounts', 'xxqd.tasks', 'class_cube', 'class_cube.overview'],
  )
  assert.equal(menuKeyIsVisible(menus, 'xxqd.overview'), false)
  assert.equal(menuKeyIsVisible(menus, 'xxqd.tasks'), true)
})


test('firstVisiblePath selects the first available child route', () => {
  assert.equal(firstVisiblePath(menus), '/accounts')
  assert.equal(firstVisiblePath([]), '/no-access')
})


test('hidden current route redirects immediately while visible route stays', () => {
  assert.equal(
    resolveMenuRedirect({
      menus,
      menuKey: 'xxqd.overview',
      currentPath: '/overview',
    }),
    '/accounts',
  )
  assert.equal(
    resolveMenuRedirect({
      menus,
      menuKey: 'xxqd.tasks',
      currentPath: '/tasks',
    }),
    null,
  )
})


test('SSE parser handles events split across network chunks', () => {
  const first = consumeSseChunk('', 'event: version\ndata: {"ver')
  assert.deepEqual(first.events, [])

  const second = consumeSseChunk(first.buffer, 'sion":8}\n\n: keep-alive\n\n')
  assert.deepEqual(second.events, [{ event: 'version', data: { version: 8 } }])
  assert.equal(second.buffer, '')
})


test('flattenMenuCatalog preserves hierarchy without parent-child coupling', () => {
  assert.deepEqual(flattenMenuCatalog(menus), [
    { key: 'xxqd', title: '小小签到', path: null, depth: 0, parentKey: null },
    { key: 'xxqd.accounts', title: '账号管理', path: '/accounts', depth: 1, parentKey: 'xxqd' },
    { key: 'xxqd.tasks', title: '任务管理', path: '/tasks', depth: 1, parentKey: 'xxqd' },
    { key: 'class_cube', title: '班级魔方', path: null, depth: 0, parentKey: null },
    {
      key: 'class_cube.overview',
      title: '系统概览',
      path: '/class-cube/overview',
      depth: 1,
      parentKey: 'class_cube',
    },
  ])
})


test('watchMenuVersions authenticates and delivers version changes', async () => {
  const originalStorage = globalThis.localStorage
  globalThis.localStorage = { getItem: key => key === 'access_token' ? 'token-123' : null }
  const chunks = [
    new TextEncoder().encode('event: version\ndata: {"version":'),
    new TextEncoder().encode('9}\n\n'),
  ]
  const requests = []
  const versions = []
  const fetchImpl = async (url, options) => {
    requests.push({ url, options })
    return {
      ok: true,
      status: 200,
      body: {
        getReader() {
          return {
            async read() {
              return chunks.length
                ? { done: false, value: chunks.shift() }
                : { done: true, value: undefined }
            },
          }
        },
      },
    }
  }

  try {
    await watchMenuVersions({
      lastVersion: 4,
      onVersion: version => versions.push(version),
      signal: new AbortController().signal,
      fetchImpl,
    })
  } finally {
    globalThis.localStorage = originalStorage
  }

  assert.equal(requests[0].url, '/api/menu/events?last_version=4')
  assert.equal(requests[0].options.headers.Authorization, 'Bearer token-123')
  assert.deepEqual(versions, [9])
})
