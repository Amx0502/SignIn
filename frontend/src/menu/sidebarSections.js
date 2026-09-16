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
    {
      key: 'system.checkin-delay-settings',
      title: '签到时间设置',
      path: '/checkin-delay-settings',
      icon: 'Timer',
      children: [],
    },
    {
      key: 'system.purchase-link-settings',
      title: '购买链接设置',
      path: '/purchase-link-settings',
      icon: 'Link',
      children: [],
    },
  ],
}

export function buildSidebarSections(businessMenus, isAdmin) {
  if (!isAdmin) return businessMenus
  return [SYSTEM_SECTION, ...businessMenus]
}
