export const MOBILE_PLATFORM_DEFINITIONS = {
  xxqd: {
    title: '小小签到',
    paths: ['/overview', '/accounts', '/checkin/auto', '/tasks', '/logs'],
    primary: [
      ['xxqd.overview', '总览', 'Odometer'],
      ['xxqd.accounts', '账号', 'User'],
      ['xxqd.auto', '签到', 'Timer'],
      ['xxqd.tasks', '任务', 'List'],
    ],
  },
  class_cube: {
    title: '班级魔方',
    prefix: '/class-cube',
    primary: [
      ['class_cube.overview', '总览', 'Odometer'],
      ['class_cube.accounts', '账号', 'User'],
      ['class_cube.tasks', '任务', 'Timer'],
      ['class_cube.runs', '记录', 'Document'],
    ],
  },
  miaoying: {
    title: '秒应',
    prefix: '/miaoying',
    primary: [
      ['miaoying.overview', '总览', 'Odometer'],
      ['miaoying.accounts', '账号', 'User'],
      ['miaoying.auto', '任务', 'Timer'],
      ['miaoying.runs', '记录', 'Document'],
    ],
  },
}

export function detectMobilePlatform(path) {
  return Object.entries(MOBILE_PLATFORM_DEFINITIONS).find(([, definition]) => (
    definition.paths?.includes(path) || (definition.prefix && path.startsWith(definition.prefix))
  ))?.[0] || ''
}

export function findMenuByKey(sections, key) {
  for (const section of sections) {
    if (section.key === key) return section
    const child = section.children?.find(item => item.key === key)
    if (child) return child
  }
  return null
}

export function resolveMobilePlatformKey(sections, path, remembered = '') {
  const available = sections.filter(section => MOBILE_PLATFORM_DEFINITIONS[section.key])
  const detected = detectMobilePlatform(path)
  if (detected && available.some(section => section.key === detected)) return detected
  if (remembered && available.some(section => section.key === remembered)) return remembered
  return available[0]?.key || ''
}

export function buildMobilePrimaryItems(sections, platformKey) {
  const definition = MOBILE_PLATFORM_DEFINITIONS[platformKey]
  if (!definition) return []
  return definition.primary.flatMap(([key, label, icon]) => {
    const item = findMenuByKey(sections, key)
    return item?.path ? [{ ...item, label, icon }] : []
  })
}

export function buildMobileExtraItems(sections, platformKey) {
  const definition = MOBILE_PLATFORM_DEFINITIONS[platformKey]
  const section = sections.find(item => item.key === platformKey)
  if (!definition || !section) return []
  const primaryKeys = new Set(definition.primary.map(item => item[0]))
  return (section.children || []).filter(item => item.path && !primaryKeys.has(item.key))
}
