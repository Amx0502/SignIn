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
  } catch {
    initialLoadFailed = true
  }

  try {
    await ensureAllowed()
  } finally {
    startStream()
  }

  return { initialLoadFailed }
}
