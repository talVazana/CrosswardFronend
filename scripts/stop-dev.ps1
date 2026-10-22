$ErrorActionPreference = 'Stop'

$pidFile = Join-Path $PSScriptRoot 'dev-pids.json'
if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "No dev-pids.json found; nothing to stop."
    exit 0
}

$pids = Get-Content -LiteralPath $pidFile | ConvertFrom-Json
foreach ($entry in @(@($pids.Backend), @($pids.Frontend))) {
    foreach ($pid in $entry) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $pid -Force
            Write-Host "Stopped process $pid"
        }
    }
}
Remove-Item -LiteralPath $pidFile -Force
