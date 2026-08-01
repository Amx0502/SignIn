import { parseCoordinates } from './classCubeTaskForm.js'

const SYNC_STATUSES = new Set(['success', 'already_signed'])

export async function syncAfterManualCheckin(result, syncItems) {
  if (SYNC_STATUSES.has(result?.status)) await syncItems()
  return result
}

export function buildManualCheckinPayload({
  mode,
  coordinateInput = '',
  accuracy,
  password = '',
  photoPath = '',
  photoRes = '',
  notifyWecom = false,
}) {
  const payload = { notify_wecom: Boolean(notifyWecom) }
  if (['gps', 'gps_photo'].includes(mode)) {
    Object.assign(payload, parseCoordinates(coordinateInput), { accuracy })
  }
  if (mode === 'password') payload.password = password
  if (mode === 'gps_photo') {
    payload.photo_path = photoPath
    const normalizedPhotoRes = String(photoRes || '').trim()
    if (normalizedPhotoRes) payload.photo_res = normalizedPhotoRes
  }
  return payload
}
