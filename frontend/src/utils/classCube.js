export function normalizeQrSession(data = {}, nowMs = Date.now()) {
  const rawLifetime = Number(data.expires_in_seconds)
  const expiresInSeconds = Number.isFinite(rawLifetime)
    ? Math.max(0, Math.floor(rawLifetime))
    : 0

  return {
    token: data.token || '',
    qrImage: data.qr_image || '',
    status: data.status || 'pending',
    retryable: Boolean(data.retryable),
    expiresInSeconds,
    deadlineMs: nowMs + expiresInSeconds * 1000,
  }
}

export function reconcileSelection(items, selectedId) {
  if (!Array.isArray(items) || selectedId === null || selectedId === undefined) {
    return null
  }
  return items.find(item => item?.id === selectedId) || null
}
