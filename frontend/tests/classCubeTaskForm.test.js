import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import * as taskForm from '../src/utils/classCubeTaskForm.js'


test('editing sends the visible password and empty value clears it', () => {
  const request = taskForm.taskRequest?.(
    {
      owner_user_id: 9,
      account_id: 3,
      course_id: 7,
      name: '密码签到',
      password: '',
      clear_password: true,
      coordinateInput: '119.38, 26.09',
    },
    true,
  )

  assert.deepEqual(request, {
    account_id: 3,
    course_id: 7,
    name: '密码签到',
    password: '',
  })
})


test('task editor shows saved password without clear-password controls', async () => {
  const source = await readFile(
    new URL(
      '../src/components/class-cube/AutoTaskPanel.vue',
      import.meta.url,
    ),
    'utf8',
  )

  assert.match(
    source,
    /v-model="draft\.password"\s+type="text"/,
  )
  assert.doesNotMatch(source, /clear_password/)
  assert.doesNotMatch(source, /留空保持不变/)
})
