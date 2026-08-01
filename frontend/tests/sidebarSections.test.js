import test from 'node:test'
import assert from 'node:assert/strict'

import { buildSidebarSections } from '../src/menu/sidebarSections.js'


test('admin system settings section is placed before business menus', () => {
  const businessMenus = [
    { key: 'xxqd', title: '小小签到', path: null, children: [] },
    { key: 'class_cube', title: '班级魔方', path: null, children: [] },
  ]

  const sections = buildSidebarSections(businessMenus, true)

  assert.deepEqual(sections.map(section => section.key), [
    'system',
    'xxqd',
    'class_cube',
  ])
  assert.deepEqual(
    sections[0].children.map(item => item.path),
    ['/users', '/menu-management'],
  )
})


test('ordinary users receive only their permitted business menus', () => {
  const businessMenus = [
    { key: 'xxqd', title: '小小签到', path: null, children: [] },
  ]

  assert.deepEqual(buildSidebarSections(businessMenus, false), businessMenus)
})
