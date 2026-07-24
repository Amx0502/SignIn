import test from 'node:test'
import assert from 'node:assert/strict'
import {
  getAccountDeleteIndexes,
  getTaskDeleteTargets,
} from './batchDelete.js'

test('sorts selected account indexes from highest to lowest', () => {
  const accounts = [{ id: 0 }, { id: 1 }, { id: 2 }, { id: 3 }]

  assert.deepEqual(
    getAccountDeleteIndexes(accounts, [accounts[1], accounts[3]]),
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
