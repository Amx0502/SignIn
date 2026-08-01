const SYNC_STATUSES = new Set(['success', 'already_signed'])

export async function syncAfterManualCheckin(result, syncItems) {
  if (SYNC_STATUSES.has(result?.status)) await syncItems()
  return result
}

