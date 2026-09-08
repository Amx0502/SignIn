function valueOf(field, answers) {
  for (const key of [field?.key, field?.id, field?.title]) {
    if (key && Object.prototype.hasOwnProperty.call(answers || {}, key)) return answers[key]
  }
  return undefined
}

function encodedValues(field, answers) {
  const value = valueOf(field, answers)
  const values = Array.isArray(value) ? value : value == null || value === '' ? [] : [value]
  const options = field?.options || []
  return values.map(item => {
    const option = options.find(candidate =>
      [candidate.value, candidate.label, candidate.submit_value].some(value => String(value) === String(item))
    )
    return String(option?.submit_value ?? item)
  })
}

export function miaoyingFieldVisible(field, fields, answers) {
  const conditions = field?.show_conditions || []
  if (!conditions.length) return true
  const fieldsById = new Map((fields || []).filter(item => item.id).map(item => [String(item.id), item]))
  const results = conditions.map(condition => {
    const controller = fieldsById.get(String(condition.option_id || ''))
    if (!controller) return false
    const selected = new Set(encodedValues(controller, answers))
    const expected = (condition.option_indexes || []).map(String)
    let matched = expected.some(item => selected.has(item))
    if (['1', 'not', 'not_in'].includes(String(condition.option_logic ?? '').toLowerCase())) matched = !matched
    return matched
  })
  return ['1', 'or', 'any'].includes(String(field?.show_conditions_logic ?? '0').toLowerCase())
    ? results.some(Boolean)
    : results.every(Boolean)
}

export function visibleMiaoyingFields(fields, answers) {
  return (fields || []).filter(field => miaoyingFieldVisible(field, fields, answers))
}
