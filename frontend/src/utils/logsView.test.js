import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

test('log updates do not automatically scroll the viewer to the bottom', async () => {
  const source = await readFile(new URL('../views/Logs.vue', import.meta.url), 'utf8')

  assert.doesNotMatch(source, /watch\(logs/)
  assert.doesNotMatch(source, /nextTick\(scrollToBottom\)/)
  assert.match(source, /@click="scrollToBottom"/)
})
