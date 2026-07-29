import assert from 'node:assert/strict'
import test from 'node:test'

import {
  normalizeScheduleTimes,
  parseCoordinates,
} from './classCubeTaskForm.js'

test('parses BJMF coordinate separators', () => {
  for (const value of [
    '20.656756 119.196135',
    '20.656756,119.196135',
    '20.656756，119.196135',
    '20.656756|119.196135',
  ]) {
    assert.deepEqual(parseCoordinates(value), {
      latitude: 20.656756,
      longitude: 119.196135,
    })
  }
})

test('sorts and deduplicates execution times', () => {
  assert.deepEqual(
    normalizeScheduleTimes(['18:00:00', '08:00:00', '08:00:00']),
    ['08:00:00', '18:00:00'],
  )
})

