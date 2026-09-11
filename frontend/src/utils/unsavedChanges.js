export function serializeSnapshot(value) {
  return JSON.stringify(value)
}

export function hasUnsavedChanges(cleanSnapshot, currentValue, visible = true) {
  return Boolean(visible && cleanSnapshot !== serializeSnapshot(currentValue))
}
