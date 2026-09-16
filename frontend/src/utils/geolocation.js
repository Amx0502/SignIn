/**
 * Browser Geolocation API wrapper with WGS-84 → GCJ-02 coordinate conversion.
 *
 * Tencent Maps (腾讯地图) uses GCJ-02 coordinates. The browser Geolocation API
 * returns WGS-84 on most platforms, so we must convert to avoid a ~500m offset.
 *
 * Exception: Android WeChat's X5 WebView uses Tencent's own location service
 * and already returns GCJ-02, so we skip the conversion there to avoid
 * double-offsetting.
 */

// ── WGS-84 → GCJ-02 conversion ──────────────────────────────────────────────

const PI = Math.PI
const A = 6378245.0
const EE = 0.00669342162296594323
const X_PI = PI * 3000.0 / 180.0

function outOfChina(lng, lat) {
  return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271
}

function transformLat(x, y) {
  let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x))
  ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0
  ret += (20.0 * Math.sin(y * PI) + 40.0 * Math.sin(y / 3.0 * PI)) * 2.0 / 3.0
  ret += (160.0 * Math.sin(y / 12.0 * PI) + 320 * Math.sin(y * PI / 30.0)) * 2.0 / 3.0
  return ret
}

function transformLng(x, y) {
  let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x))
  ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0
  ret += (20.0 * Math.sin(x * PI) + 40.0 * Math.sin(x / 3.0 * PI)) * 2.0 / 3.0
  ret += (150.0 * Math.sin(x / 12.0 * PI) + 150.0 * Math.sin(x / 30.0 * PI)) * 2.0 / 3.0
  return ret
}

/**
 * Convert WGS-84 coordinates to GCJ-02 (Mars coordinates).
 * Returns the original coordinates if the point is outside China.
 *
 * @param {number} wgsLat - WGS-84 latitude
 * @param {number} wgsLng - WGS-84 longitude
 * @returns {{ latitude: number, longitude: number }} GCJ-02 coordinates
 */
export function wgs84ToGcj02(wgsLat, wgsLng) {
  const lat = Number(wgsLat)
  const lng = Number(wgsLng)
  if (outOfChina(lng, lat)) return { latitude: lat, longitude: lng }

  let dLat = transformLat(lng - 105.0, lat - 35.0)
  let dLng = transformLng(lng - 105.0, lat - 35.0)
  const radLat = lat / 180.0 * PI
  let magic = Math.sin(radLat)
  magic = 1 - EE * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  dLat = (dLat * 180.0) / ((A * (1 - EE)) / (magic * sqrtMagic) * PI)
  dLng = (dLng * 180.0) / (A / sqrtMagic * Math.cos(radLat) * PI)

  return {
    latitude: lat + dLat,
    longitude: lng + dLng,
  }
}

// ── Environment detection ────────────────────────────────────────────────────

const UA = typeof navigator !== 'undefined' ? navigator.userAgent : ''

/** True if running inside the WeChat built-in browser (not a Mini Program). */
export function isWeChatBrowser() {
  return /MicroMessenger/i.test(UA) && !/miniProgram/i.test(UA)
}

/** True if running inside the Android WeChat X5 WebView. */
export function isAndroidWeChat() {
  return isWeChatBrowser() && /Android/i.test(UA)
}

/**
 * Determine whether the Geolocation API on this platform already returns
 * GCJ-02 coordinates (so we should skip the WGS-84 → GCJ-02 conversion).
 *
 * Currently only Android WeChat (X5 kernel + Tencent location service) is known
 * to return GCJ-02 directly.
 */
export function isGeolocationReturningGcj02() {
  return isAndroidWeChat()
}

// ── Geolocation wrapper ──────────────────────────────────────────────────────

const ERROR_MESSAGES = {
  1: '用户拒绝了定位请求',
  2: '定位不可用，请检查设备或网络',
  3: '定位超时，请重试',
}

/**
 * Call the browser Geolocation API and return a Promise.
 *
 * @param {PositionOptions} [options]
 * @returns {Promise<GeolocationPosition>}
 */
export function getCurrentPosition(options = {}) {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      reject(new Error('当前浏览器不支持定位功能'))
      return
    }

    navigator.geolocation.getCurrentPosition(resolve, (err) => {
      reject(new Error(ERROR_MESSAGES[err.code] || err.message || '定位失败'))
    }, {
      enableHighAccuracy: true,
      timeout: 15_000,
      maximumAge: 60_000,
      ...options,
    })
  })
}

/**
 * Get the current position as GCJ-02 coordinates, automatically handling the
 * WGS-84 → GCJ-02 conversion when needed.
 *
 * @param {PositionOptions} [options]
 * @returns {Promise<{ latitude: number, longitude: number, accuracy: number }>}
 */
export async function getCurrentGcj02Position(options) {
  const pos = await getCurrentPosition(options)
  const { latitude, longitude, accuracy } = pos.coords

  if (isGeolocationReturningGcj02()) {
    return { latitude, longitude, accuracy }
  }

  const gcj = wgs84ToGcj02(latitude, longitude)
  return { latitude: gcj.latitude, longitude: gcj.longitude, accuracy }
}
