export function visibleMenuKeys(menus = []) {
  const keys = new Set()
  const visit = items => {
    for (const item of items || []) {
      if (item?.key) keys.add(item.key)
      visit(item?.children || [])
    }
  }
  visit(menus)
  return keys
}

export function menuKeyIsVisible(menus, menuKey) {
  if (!menuKey) return true
  return visibleMenuKeys(menus).has(menuKey)
}

export function firstVisiblePath(menus = []) {
  for (const item of menus) {
    if (item.path) return item.path
    const childPath = firstVisiblePath(item.children || [])
    if (childPath !== '/no-access') return childPath
  }
  return '/no-access'
}

export function resolveMenuRedirect({ menus, menuKey, currentPath }) {
  if (!menuKey || menuKeyIsVisible(menus, menuKey)) return null
  const fallback = firstVisiblePath(menus)
  return fallback === currentPath ? '/no-access' : fallback
}

export function flattenMenuCatalog(menus = [], depth = 0, parentKey = null) {
  const rows = []
  for (const item of menus) {
    rows.push({
      key: item.key,
      title: item.title,
      path: item.path || null,
      depth,
      parentKey,
    })
    rows.push(...flattenMenuCatalog(item.children || [], depth + 1, item.key))
  }
  return rows
}
