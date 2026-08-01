export function consumeSseChunk(buffer, chunk) {
  const normalized = `${buffer}${chunk}`.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const remainder = blocks.pop() ?? ''
  const events = []

  for (const block of blocks) {
    if (!block || block.startsWith(':')) continue
    let event = 'message'
    const dataLines = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (!dataLines.length) continue
    try {
      events.push({ event, data: JSON.parse(dataLines.join('\n')) })
    } catch {
      // Ignore malformed server events and continue the stream.
    }
  }
  return { events, buffer: remainder }
}

export async function watchMenuVersions({
  lastVersion = 0,
  onVersion,
  signal,
  fetchImpl = fetch,
}) {
  const token = localStorage.getItem('access_token')
  const response = await fetchImpl(
    `/api/menu/events?last_version=${encodeURIComponent(lastVersion)}`,
    {
      headers: { Authorization: `Bearer ${token}` },
      signal,
    },
  )
  if (!response.ok || !response.body) {
    throw new Error(`菜单实时连接失败（${response.status}）`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (!signal?.aborted) {
    const { done, value } = await reader.read()
    if (done) break
    const parsed = consumeSseChunk(buffer, decoder.decode(value, { stream: true }))
    buffer = parsed.buffer
    for (const item of parsed.events) {
      if (item.event === 'version' && Number.isInteger(item.data?.version)) {
        await onVersion(item.data.version)
      }
    }
  }
}
