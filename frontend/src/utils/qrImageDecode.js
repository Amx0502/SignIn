export async function decodeQrImage(file, options = {}) {
  if (!file) throw new Error('请选择二维码图片')
  const Detector = globalThis.BarcodeDetector
  const detectorFactory = options.detectorFactory || (() => {
    if (typeof Detector !== 'function') {
      throw new Error('当前浏览器不支持二维码图片解析，请改用 Chrome 或手动粘贴签到地址')
    }
    return new Detector({ formats: ['qr_code'] })
  })
  const imageBitmapFactory = options.imageBitmapFactory || globalThis.createImageBitmap
  if (typeof imageBitmapFactory !== 'function') {
    throw new Error('当前浏览器不支持图片解析，请改用 Chrome 或手动粘贴签到地址')
  }

  const bitmap = await imageBitmapFactory(file)
  try {
    const codes = await detectorFactory().detect(bitmap)
    const value = codes.find(code => String(code?.rawValue || '').trim())?.rawValue?.trim()
    if (!value) throw new Error('未识别到二维码，请上传清晰的签到二维码图片')
    return value
  } finally {
    bitmap.close?.()
  }
}
