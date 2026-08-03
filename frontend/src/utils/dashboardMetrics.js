const TYPE_LABELS = {
  gps: 'GPS签到',
  gps_photo: 'GPS拍照签到',
  password: '密码签到',
  qr: '二维码签到',
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function numberOrZero(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0
}

function typeLabel(mode) {
  return TYPE_LABELS[String(mode || '').toLowerCase()] || '其他签到'
}

export function buildDashboardMetrics(input = {}) {
  const xxqd = input.xxqd || {}
  const cubeAccounts = asArray(input.cubeAccounts)
  const cubeTasks = asArray(input.cubeTasks)
  const cubeRuns = asArray(input.cubeRuns)
  const statusCounts = { success: 0, failed: 0, running: 0, pending: 0 }

  for (const run of cubeRuns) {
    const status = String(run?.status || '').toLowerCase()
    if (status === 'success' || status === 'already_signed') statusCounts.success += 1
    else if (status === 'failed' || status === 'error') statusCounts.failed += 1
    else if (status === 'running' || status === 'submitting') statusCounts.running += 1
    else statusCounts.pending += 1
  }

  const typeCounts = new Map()
  for (const task of cubeTasks) {
    const label = typeLabel(task?.mode)
    typeCounts.set(label, (typeCounts.get(label) || 0) + 1)
  }
  for (const run of cubeRuns) {
    if (!run?.mode) continue
    const label = typeLabel(run.mode)
    if (!typeCounts.has(label)) typeCounts.set(label, 0)
  }

  const rankingCounts = new Map()
  for (const run of cubeRuns) {
    const status = String(run?.status || '').toLowerCase()
    if (status !== 'success' && status !== 'already_signed') continue
    const name = String(run?.account_name || run?.account || '未知账号')
    rankingCounts.set(name, (rankingCounts.get(name) || 0) + 1)
  }

  return {
    cards: [
      { label: '小小签到账号', value: numberOrZero(xxqd.account_count), tone: 'blue' },
      { label: '小小签到任务', value: numberOrZero(xxqd.task_count), tone: 'violet' },
      { label: '启用任务', value: numberOrZero(xxqd.enabled_task_count), tone: 'green' },
      { label: '班级魔方账号', value: cubeAccounts.length, tone: 'cyan' },
      { label: '班级魔方任务', value: cubeTasks.length, tone: 'orange' },
      { label: '运行记录', value: cubeRuns.length, tone: 'slate' },
    ],
    statuses: statusCounts,
    typeDistribution: [...typeCounts.entries()]
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value),
    ranking: [...rankingCounts.entries()]
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value || a.name.localeCompare(b.name))
      .slice(0, 5),
    recentRuns: [...cubeRuns]
      .sort((a, b) => String(b?.started_at || b?.created_at || '').localeCompare(String(a?.started_at || a?.created_at || '')))
      .slice(0, 8),
  }
}

export const dashboardTypeLabel = typeLabel
