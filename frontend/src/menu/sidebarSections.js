const SYSTEM_SECTION = {
  key: 'system',
  title: '系统设置',
  path: null,
  icon: 'Setting',
  children: [
    {
      key: 'system.users',
      title: '用户管理',
      path: '/users',
      icon: 'UserFilled',
      children: [],
    },
    {
      key: 'system.menu-management',
      title: '菜单管理',
      path: '/menu-management',
      icon: 'Menu',
      children: [],
    },
  ],
}

export function buildSidebarSections(businessMenus, isAdmin) {
  if (!isAdmin) return businessMenus
  return [SYSTEM_SECTION, ...businessMenus]
}
