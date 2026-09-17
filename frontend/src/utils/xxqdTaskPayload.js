export function buildXxqdTaskPayload(form, locationMode, mapLocation = null) {
  const payload = {
    ...form,
    location_mode: locationMode,
  }
  if (locationMode === 'map') {
    if (mapLocation) Object.assign(payload, mapLocation)
    payload.use_location = true
    return payload
  }
  payload.use_location = locationMode === 'auto'
  return payload
}
