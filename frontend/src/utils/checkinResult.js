import { formatCurrentTime } from './currentTime.js'


export function createCheckinResult(data = {}, completedAt = formatCurrentTime()) {
  const location = typeof data.location === 'string'
    ? data.location
    : data.location?.address

  return {
    title: data.title || '-',
    realTitle: data.real_title || '-',
    text: data.text || '',
    location: location || '',
    imageUrls: Array.isArray(data.image_urls)
      ? data.image_urls.filter(url => typeof url === 'string' && url)
      : [],
    completedAt,
  }
}
