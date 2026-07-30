import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import viteConfig from '../../vite.config.js'

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../..'
)

test('开发模式使用 Vite 热更新并代理到本机后端', () => {
  assert.equal(
    viteConfig.server.proxy['/api'].target,
    'http://127.0.0.1:8765'
  )
  assert.equal(
    viteConfig.server.proxy['/uploads'].target,
    'http://127.0.0.1:8765'
  )

  const output = execFileSync(
    'powershell.exe',
    [
      '-NoProfile',
      '-ExecutionPolicy',
      'Bypass',
      '-File',
      path.join(repositoryRoot, 'start-dev.ps1'),
      '-DryRun'
    ],
    {
      cwd: repositoryRoot,
      encoding: 'utf8'
    }
  )

  assert.match(
    output,
    /FastAPI: python -m uvicorn app\.main:app --host 127\.0\.0\.1 --port 8765 --reload/
  )
  assert.match(output, /Vite: .*127\.0\.0\.1:5173/)
  assert.match(output, /http:\/\/localhost:5173/)
})
