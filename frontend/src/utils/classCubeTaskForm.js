export function parseCoordinates(value) {
  const parts = String(value ?? '')
    .trim()
    .split(/[\s,，|]+/)
    .filter(Boolean)
  if (parts.length !== 2) throw new Error('请输入纬度和经度')
  const [latitude, longitude] = parts.map(Number)
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
    throw new Error('纬度必须在 -90 到 90 之间')
  }
  if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
    throw new Error('经度必须在 -180 到 180 之间')
  }
  return { latitude, longitude }
}

export function normalizeScheduleTimes(values) {
  const pattern = /^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$/
  const result = [...new Set(
    (values || []).map(value => String(value).trim()),
  )]
  if (result.some(value => !pattern.test(value))) {
    throw new Error('执行时间必须使用 HH:mm:ss 格式')
  }
  return result.sort()
}

export function coordinateText(task) {
  if (task?.latitude == null || task?.longitude == null) return ''
  return `${task.latitude}, ${task.longitude}`
}

