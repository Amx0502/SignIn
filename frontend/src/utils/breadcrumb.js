export function getBreadcrumb(meta = {}) {
  return {
    parentTitle: meta.parentTitle || '后台控制台',
    title: meta.title || '签到管理系统',
  }
}
