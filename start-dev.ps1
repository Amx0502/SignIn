param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = $PSScriptRoot
$backendDirectory = Join-Path $repositoryRoot 'backend'
$frontendDirectory = Join-Path $repositoryRoot 'frontend'

if ($DryRun) {
    Write-Output 'FastAPI: python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload'
    Write-Output 'Vite: http://127.0.0.1:5173 (npm.cmd run dev)'
    Write-Output '开发访问地址: http://localhost:5173'
    exit 0
}

$backendProcess = $null
$frontendProcess = $null

try {
    $backendProcess = Start-Process `
        -FilePath 'python' `
        -ArgumentList @(
            '-m',
            'uvicorn',
            'app.main:app',
            '--host',
            '127.0.0.1',
            '--port',
            '8765',
            '--reload'
        ) `
        -WorkingDirectory $backendDirectory `
        -WindowStyle Hidden `
        -PassThru
    $frontendProcess = Start-Process `
        -FilePath 'npm.cmd' `
        -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173') `
        -WorkingDirectory $frontendDirectory `
        -WindowStyle Hidden `
        -PassThru

    Write-Host '开发服务已启动，保存前端源码后页面会自动热更新。'
    Write-Host '访问地址: http://localhost:5173'
    Write-Host '按 Ctrl+C 可同时停止前后端开发服务。'

    while (
        -not $backendProcess.HasExited -and
        -not $frontendProcess.HasExited
    ) {
        Start-Sleep -Milliseconds 500
        $backendProcess.Refresh()
        $frontendProcess.Refresh()
    }

    if ($backendProcess.HasExited) {
        throw "FastAPI 开发服务已退出，退出码：$($backendProcess.ExitCode)"
    }
    throw "Vite 开发服务已退出，退出码：$($frontendProcess.ExitCode)"
}
finally {
    foreach ($process in @($backendProcess, $frontendProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id
        }
    }
}
