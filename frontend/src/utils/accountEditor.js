function accountDraft(row) {
  return {
    name: row?.name || '',
    mobile: row?.mobile || '',
    password: row?.password || '',
    token: row?.token || '',
  }
}

export function selectedAccountIndex(accounts, selectedMobile) {
  if (!selectedMobile) return -1
  return accounts.findIndex(account => account.mobile === selectedMobile)
}

export function reconcileAccountSelection({
  accounts,
  row,
  selectedMobile,
  draft,
}) {
  const nextMobile = row?.mobile || ''
  const index = selectedAccountIndex(accounts, nextMobile)
  const shouldHydrateDraft = !selectedMobile || selectedMobile !== nextMobile

  return {
    selectedMobile: nextMobile,
    index,
    shouldHydrateDraft,
    draft: shouldHydrateDraft ? accountDraft(row) : draft,
  }
}
