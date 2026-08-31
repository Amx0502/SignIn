const PI = Math.PI
const SEMI_MAJOR_AXIS = 6378245
const ECCENTRICITY_SQUARED = 0.006693421622965943

function isGcj02Applicable(latitude, longitude) {
  if (
    latitude < 0.8293 || latitude > 55.8271
    || longitude < 72.004 || longitude > 137.8347
  ) return false
  return !(
    latitude >= 21.5 && latitude <= 25.5
    && longitude >= 119 && longitude <= 124.5
  )
}

function latitudeOffset(longitude, latitude) {
  let value = -100 + 2 * longitude + 3 * latitude
    + 0.2 * latitude * latitude + 0.1 * longitude * latitude
    + 0.2 * Math.sqrt(Math.abs(longitude))
  value += (20 * Math.sin(6 * longitude * PI) + 20 * Math.sin(2 * longitude * PI)) * 2 / 3
  value += (20 * Math.sin(latitude * PI) + 40 * Math.sin(latitude / 3 * PI)) * 2 / 3
  value += (160 * Math.sin(latitude / 12 * PI) + 320 * Math.sin(latitude * PI / 30)) * 2 / 3
  return value
}

function longitudeOffset(longitude, latitude) {
  let value = 300 + longitude + 2 * latitude
    + 0.1 * longitude * longitude + 0.1 * longitude * latitude
    + 0.1 * Math.sqrt(Math.abs(longitude))
  value += (20 * Math.sin(6 * longitude * PI) + 20 * Math.sin(2 * longitude * PI)) * 2 / 3
  value += (20 * Math.sin(longitude * PI) + 40 * Math.sin(longitude / 3 * PI)) * 2 / 3
  value += (150 * Math.sin(longitude / 12 * PI) + 300 * Math.sin(longitude / 30 * PI)) * 2 / 3
  return value
}

export function wgs84ToGcj02(latitude, longitude) {
  const sourceLatitude = Number(latitude)
  const sourceLongitude = Number(longitude)
  if (!isGcj02Applicable(sourceLatitude, sourceLongitude)) {
    return { latitude: sourceLatitude, longitude: sourceLongitude }
  }

  let latitudeDelta = latitudeOffset(sourceLongitude - 105, sourceLatitude - 35)
  let longitudeDelta = longitudeOffset(sourceLongitude - 105, sourceLatitude - 35)
  const radians = sourceLatitude / 180 * PI
  const sine = Math.sin(radians)
  const magic = 1 - ECCENTRICITY_SQUARED * sine * sine
  const squareRoot = Math.sqrt(magic)
  latitudeDelta = latitudeDelta * 180 / (
    SEMI_MAJOR_AXIS * (1 - ECCENTRICITY_SQUARED)
    / (magic * squareRoot) * PI
  )
  longitudeDelta = longitudeDelta * 180 / (
    SEMI_MAJOR_AXIS / squareRoot * Math.cos(radians) * PI
  )
  return {
    latitude: sourceLatitude + latitudeDelta,
    longitude: sourceLongitude + longitudeDelta,
  }
}

export function gcj02ToWgs84(latitude, longitude) {
  const source = { latitude: Number(latitude), longitude: Number(longitude) }
  if (!isGcj02Applicable(source.latitude, source.longitude)) return source

  const estimate = { ...source }
  for (let index = 0; index < 4; index += 1) {
    const shifted = wgs84ToGcj02(estimate.latitude, estimate.longitude)
    estimate.latitude -= shifted.latitude - source.latitude
    estimate.longitude -= shifted.longitude - source.longitude
  }
  return estimate
}
