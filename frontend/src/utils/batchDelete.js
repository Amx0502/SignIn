export function getAccountDeleteIndexes(accounts, selectedAccounts) {
  const selectedMobiles = new Set(
    selectedAccounts.map(account => account.mobile),
  )

  return accounts
    .map((account, index) => (
      selectedMobiles.has(account.mobile) ? index : -1
    ))
    .filter(index => index >= 0)
    .sort((a, b) => b - a)
}

export function getTaskDeleteTargets(selectedKeys) {
  return [...selectedKeys]
    .map(key => key.split('-').map(Number))
    .filter(([accountIndex, taskIndex]) => (
      Number.isInteger(accountIndex) && Number.isInteger(taskIndex)
    ))
    .map(([accountIndex, taskIndex]) => ({ accountIndex, taskIndex }))
    .sort((a, b) => (
      a.accountIndex - b.accountIndex || b.taskIndex - a.taskIndex
    ))
}
