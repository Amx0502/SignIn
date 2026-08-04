const LOG_PATTERN = /^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+\[([A-Z]+)\]\s+(.*)$/

export function parseLogLine(line) {
  const text = String(line ?? '')
  const match = text.match(LOG_PATTERN)
  return match
    ? { time: match[1], level: match[2], message: match[3] }
    : { time: '', level: 'INFO', message: text }
}

export function filterLogEntries(lines, level = 'ALL') {
  const entries = (Array.isArray(lines) ? lines : []).map(parseLogLine)
  return level === 'ALL'
    ? entries
    : entries.filter(entry => entry.level === level)
}
