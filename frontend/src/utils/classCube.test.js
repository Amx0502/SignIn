import test from 'node:test'
import assert from 'node:assert/strict'

import {
  normalizeQrSession,
  reconcileSelection,
  requiredFieldsForMode,
} from './classCube.js'

test('returns fields required by each check-in mode', () => {
  assert.deepEqual(requiredFieldsForMode('qr'), [])
  assert.deepEqual(requiredFieldsForMode('gps'), ['latitude', 'longitude', 'accuracy'])
  assert.deepEqual(
    requiredFieldsForMode('gps_photo'),
    ['latitude', 'longitude', 'accuracy', 'photoPath'],
  )
  assert.deepEqual(requiredFieldsForMode('password'), ['password'])
  assert.deepEqual(requiredFieldsForMode('unknown'), [])
})

test('normalizes QR lifetime from expires_in_seconds only', () => {
  const session = normalizeQrSession(
    {
      token: 'qr-token',
      qr_image: 'data:image/png;base64,AA==',
      expires_in_seconds: 120,
      expires_at: 1,
    },
    5_000,
  )

  assert.deepEqual(session, {
    token: 'qr-token',
    qrImage: 'data:image/png;base64,AA==',
    status: 'pending',
    retryable: false,
    expiresInSeconds: 120,
    deadlineMs: 125_000,
  })
})

test('clamps invalid QR lifetime instead of trusting remote timestamps', () => {
  const session = normalizeQrSession(
    { expires_in_seconds: -10, expires_at: 999_999_999 },
    2_000,
  )

  assert.equal(session.expiresInSeconds, 0)
  assert.equal(session.deadlineMs, 2_000)
})

test('keeps selected item by stable id after refresh', () => {
  const refreshed = [{ id: 1 }, { id: 2, name: 'fresh' }]
  assert.deepEqual(reconcileSelection(refreshed, 2), { id: 2, name: 'fresh' })
})

test('clears selection when the stable id no longer exists', () => {
  assert.equal(reconcileSelection([{ id: 1 }], 2), null)
  assert.equal(reconcileSelection(null, 1), null)
})
