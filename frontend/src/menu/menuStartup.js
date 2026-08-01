export async function bootstrapMenuSync({
  hydrate,
  refresh,
  ensureAllowed,
  startStream,
}) {
  hydrate()
  let initialLoadFailed = false

  try {
    await refresh()
  } catch (error) {
    initialLoadFailed = true
    // A 401 means the API client has already invalidated the session. Do not
    // start an SSE reconnect loop with the now-removed token.
    if (error?.status === 401) {
      return { initialLoadFailed, unauthorized: true }
    }
  }

  try {
    await ensureAllowed()
  } finally {
    startStream()
  }

  return { initialLoadFailed }
}
