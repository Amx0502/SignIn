import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

import { createCheckinResult } from './checkinResult.js'


test('normalizes a complete check-in result', () => {
  const result = createCheckinResult({
    title: '上午签到',
    real_title: '总部项目',
    text: '测试内容',
    location: { address: '科技园' },
    image_urls: ['/uploads/a.png'],
  }, '2026-07-24 10:30:00')

  assert.deepEqual(result, {
    title: '上午签到',
    realTitle: '总部项目',
    text: '测试内容',
    location: '科技园',
    imageUrls: ['/uploads/a.png'],
    completedAt: '2026-07-24 10:30:00',
  })
})


test('uses safe display defaults for missing result fields', () => {
  const result = createCheckinResult({}, '2026-07-24 10:30:00')

  assert.equal(result.title, '-')
  assert.equal(result.realTitle, '-')
  assert.equal(result.text, '')
  assert.equal(result.location, '')
  assert.deepEqual(result.imageUrls, [])
})


test('result dialog uses Vue rendering instead of dangerous HTML', async () => {
  const source = await readFile(
    new URL('../components/CheckinResultDialog.vue', import.meta.url),
    'utf8',
  )

  assert.match(source, /checkin-result__grid/)
  assert.match(source, /el-image/)
  assert.doesNotMatch(source, /dangerouslyUseHTMLString|v-html/)
})
