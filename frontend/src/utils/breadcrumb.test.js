import test from 'node:test'
import assert from 'node:assert/strict'
import { getBreadcrumb } from './breadcrumb.js'

test('returns declared parent and page title', () => {
  assert.deepEqual(
    getBreadcrumb({ parentTitle: '小小签到', title: '自动签到' }),
    { parentTitle: '小小签到', title: '自动签到' },
  )
})

test('falls back for standalone and missing titles', () => {
  assert.deepEqual(
    getBreadcrumb({ title: '用户管理' }),
    { parentTitle: '后台控制台', title: '用户管理' },
  )
  assert.deepEqual(
    getBreadcrumb(),
    { parentTitle: '后台控制台', title: '签到管理系统' },
  )
})
