const SCRIPT_ID = 'signin-tencent-map-sdk'

let sdkPromise = null
let sdkIdentity = ''

function sdkError(message) {
  const error = new Error(message)
  error.code = 'TENCENT_MAP_SDK_ERROR'
  return error
}

export function loadTencentMapSdk({ key, url }) {
  if (window.TMap?.Map && window.TMap?.LatLng) {
    return Promise.resolve(window.TMap)
  }

  const normalizedKey = String(key || '').trim()
  const normalizedUrl = String(url || 'https://map.qq.com/api/gljs').trim()
  if (!normalizedKey) {
    return Promise.reject(sdkError('尚未配置腾讯地图 JavaScript API GL Key'))
  }

  const identity = `${normalizedUrl}|${normalizedKey}`
  if (sdkPromise && sdkIdentity === identity) return sdkPromise

  const staleScript = document.getElementById(SCRIPT_ID)
  if (staleScript && sdkIdentity !== identity) staleScript.remove()
  sdkIdentity = identity

  sdkPromise = new Promise((resolve, reject) => {
    let settled = false
    const finish = (error = null) => {
      if (settled) return
      settled = true
      window.clearTimeout(timeoutId)
      if (error) {
        sdkPromise = null
        document.getElementById(SCRIPT_ID)?.remove()
        reject(error)
        return
      }
      if (!window.TMap?.Map || !window.TMap?.LatLng) {
        sdkPromise = null
        reject(sdkError('腾讯地图 SDK 已响应，但未提供地图 API'))
        return
      }
      resolve(window.TMap)
    }

    const timeoutId = window.setTimeout(() => {
      finish(sdkError('腾讯地图 SDK 加载超时，请检查网络、Key 与域名白名单'))
    }, 20_000)

    const existing = document.getElementById(SCRIPT_ID)
    if (existing) {
      existing.addEventListener('load', () => finish(), { once: true })
      existing.addEventListener(
        'error',
        () => finish(sdkError('腾讯地图 SDK 加载失败，请检查网络与 Key 配置')),
        { once: true },
      )
      return
    }

    let source
    try {
      source = new URL(normalizedUrl, window.location.href)
    } catch {
      finish(sdkError('腾讯地图 SDK 地址配置无效'))
      return
    }
    source.searchParams.set('v', '1.exp')
    source.searchParams.set('key', normalizedKey)

    const script = document.createElement('script')
    script.id = SCRIPT_ID
    script.charset = 'utf-8'
    script.async = true
    script.src = source.toString()
    script.addEventListener('load', () => finish(), { once: true })
    script.addEventListener(
      'error',
      () => finish(sdkError('腾讯地图 SDK 加载失败，请检查网络、Key 与域名白名单')),
      { once: true },
    )
    document.head.appendChild(script)
  })

  return sdkPromise
}
