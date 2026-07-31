function syncedDay(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T\s]|$)/.exec(
    String(value ?? '').trim(),
  )
  if (!match) return ''

  const [, yearText, monthText, dayText] = match
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  const parsed = new Date(Date.UTC(year, month - 1, day))
  if (
    parsed.getUTCFullYear() !== year
    || parsed.getUTCMonth() !== month - 1
    || parsed.getUTCDate() !== day
  ) return ''

  return `${yearText}-${monthText}-${dayText}`
}

export function latestSyncedDayItems(items) {
  if (!Array.isArray(items) || !items.length) return []

  const rows = items.map(item => ({
    item,
    day: syncedDay(item?.synced_at),
  }))
  const latestDay = rows.reduce(
    (latest, row) => row.day > latest ? row.day : latest,
    '',
  )

  if (!latestDay) return items
  return rows
    .filter(row => row.day === latestDay)
    .map(row => row.item)
}
