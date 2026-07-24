import test from 'node:test'
import assert from 'node:assert/strict'
import {
  getAccountDeleteIndexes,
  getTaskDeleteTargets,
} from './batchDelete.js'

test('sorts selected account indexes from highest to lowest', () => {
  const previousAccounts = [
    { mobile: '13000000000' },
    { mobile: '13100000000' },
    { mobile: '13200000000' },
    { mobile: '13300000000' },
  ]
  const refreshedAccounts = previousAccounts.map(account => ({ ...account }))

  assert.deepEqual(
    getAccountDeleteIndexes(
      refreshedAccounts,
      [previousAccounts[1], previousAccounts[3]],
    ),
    [3, 1],
  )
})

test('groups task targets and sorts task indexes descending per account', () => {
  assert.deepEqual(
    getTaskDeleteTargets(new Set(['0-1', '2-0', '0-3'])),
    [
      { accountIndex: 0, taskIndex: 3 },
      { accountIndex: 0, taskIndex: 1 },
      { accountIndex: 2, taskIndex: 0 },
    ],
  )
})
