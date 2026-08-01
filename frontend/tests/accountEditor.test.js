import test from 'node:test'
import assert from 'node:assert/strict'

import {
  reconcileAccountSelection,
  selectedAccountIndex,
} from '../src/utils/accountEditor.js'


test('polling replacement of the same account preserves the active edit draft', () => {
  const draft = {
    name: '正在编辑的新名称',
    mobile: '13800000000',
    password: 'new-password',
    token: 'old-token',
  }
  const accounts = [
    { name: '其他账号', mobile: '13900000000', password: 'x', token: '' },
    { name: '服务端旧名称', mobile: '13800000000', password: 'old', token: 'new-token' },
  ]

  const result = reconcileAccountSelection({
    accounts,
    row: accounts[1],
    selectedMobile: '13800000000',
    draft,
  })

  assert.equal(result.shouldHydrateDraft, false)
  assert.equal(result.index, 1)
  assert.equal(result.draft, draft)
  assert.equal(result.draft.name, '正在编辑的新名称')
  assert.equal(result.draft.password, 'new-password')
})


test('selecting a different account hydrates its values and tracks it by mobile', () => {
  const accounts = [
    { name: '账号 A', mobile: '13800000000', password: 'a', token: 'token-a' },
    { name: '账号 B', mobile: '13900000000', password: 'b', token: 'token-b' },
  ]

  const result = reconcileAccountSelection({
    accounts,
    row: accounts[1],
    selectedMobile: '13800000000',
    draft: accounts[0],
  })

  assert.equal(result.shouldHydrateDraft, true)
  assert.equal(result.selectedMobile, '13900000000')
  assert.deepEqual(result.draft, {
    name: '账号 B',
    mobile: '13900000000',
    password: 'b',
    token: 'token-b',
  })
  assert.equal(selectedAccountIndex(accounts, result.selectedMobile), 1)
})
