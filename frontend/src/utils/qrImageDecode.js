import jsQR from 'jsqr'

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const image = new Image()
    const objectUrl = URL.createObjectURL(file)
    image.onload = () => {
      URL.revokeObjectURL(objectUrl)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      reject(new Error('二维码图片读取失败，请重新选择清晰图片'))
    }
    image.src = objectUrl
  })
}

export async function decodeQrImage(file) {
  if (!file) throw new Error('请选择二维码图片')
  if (typeof Image !== 'function' || typeof document === 'undefined') {
    throw new Error('当前环境不支持图片解析，请手动粘贴签到地址')
  }

  const image = await loadImage(file)
  const canvas = document.createElement('canvas')
  const width = image.naturalWidth || image.width
  const height = image.naturalHeight || image.height
  if (!width || !height) throw new Error('二维码图片尺寸无效，请重新选择图片')

  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) throw new Error('当前浏览器无法读取图片像素，请手动粘贴签到地址')

  context.drawImage(image, 0, 0, width, height)
  const imageData = context.getImageData(0, 0, width, height)
  const code = jsQR(imageData.data, width, height, {
    inversionAttempts: 'attemptBoth',
  })
  const value = String(code?.data || '').trim()
  if (!value) throw new Error('未识别到二维码，请上传清晰的签到二维码图片')
  return value
}
