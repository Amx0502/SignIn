import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { formatCurrentTime } from './currentTime.js'

test('formats the current time as YYYY-MM-DD HH:mm:ss', () => {
  const value = new Date(2026, 6, 24, 9, 5, 7)

  assert.equal(formatCurrentTime(value), '2026-07-24 09:05:07')
})

test('renders the themed current-time structure in the application header', async () => {
  const appSource = await readFile(new URL('../App.vue', import.meta.url), 'utf8')

  assert.match(appSource, /<Clock\s*\/>/)
  assert.match(appSource, /header-current-time__indicator/)
  assert.match(appSource, /header-current-time__date/)
  assert.match(appSource, /header-current-time__clock/)
})
