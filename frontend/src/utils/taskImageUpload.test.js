import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'


test('task image upload renders themed thumbnail cards without the default file list', async () => {
  const source = await readFile(
    new URL('../components/TaskImageUpload.vue', import.meta.url),
    'utf8',
  )

  assert.match(source, /task-image-upload__card/)
  assert.match(source, /task-image-upload__filename/)
  assert.match(source, /task-image-upload__preview/)
  assert.match(source, /预览/)
  assert.match(source, /删除/)
  assert.doesNotMatch(source, /:file-list=/)
})


test('sidebar menu button is always visible and describes its state', async () => {
  const source = await readFile(new URL('../App.vue', import.meta.url), 'utf8')

  assert.match(source, /sidebarCollapsed \? '展开菜单' : '收起菜单'/)
  assert.doesNotMatch(source, /\.menu-btn\s*\{\s*display:\s*none/)
})

test('removing an image immediately synchronizes the task thumbnail list', async () => {
  const source = await readFile(
    new URL('../components/TaskManager.vue', import.meta.url),
    'utf8',
  )
  const removeHandler = source.match(
    /function onImageRemove\(file, fileList\) \{[\s\S]*?\n\}/,
  )?.[0] || ''

  assert.match(removeHandler, /syncFileList\(\)/)
})

test('tablet uses the icon sidebar and closes nested menu poppers', async () => {
  const source = await readFile(new URL('../App.vue', import.meta.url), 'utf8')
  const mobileHandler = source.match(
    /function checkMobile\(\) \{[\s\S]*?\n\}/,
  )?.[0] || ''
  const closeHandler = source.match(
    /function closeSidebar\(\) \{[\s\S]*?\n\}/,
  )?.[0] || ''

  assert.match(source, /ref="sidebarMenuRef"/)
  assert.match(source, /:key="sidebarMenuRenderKey"/)
  assert.match(source, /:persistent="false"/)
  assert.match(mobileHandler, /isMobile\.value = window\.innerWidth <= 768/)
  assert.match(
    mobileHandler,
    /sidebarCollapsed\.value = window\.innerWidth <= 1024/,
  )
  assert.match(
    closeHandler,
    /if \(isMobile\.value \|\| sidebarCollapsed\.value\) \{\s*sidebarMenuRef\.value\?\.close\('\/checkin'\)\s*sidebarMenuRenderKey\.value \+= 1\s*sidebarCollapsed\.value = true/,
  )
})
