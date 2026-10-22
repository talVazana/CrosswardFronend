$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

$backend = Start-Process -FilePath 'uvicorn' -ArgumentList 'app.main:app', '--reload' -WorkingDirectory (Join-Path $root 'backend') -PassThru
Write-Host "Backend started (PID $($backend.Id)): uvicorn app.main:app --reload"

$frontend = Start-Process -FilePath 'npm' -ArgumentList 'run', 'dev' -WorkingDirectory (Join-Path $root 'frontend') -PassThru
Write-Host "Frontend started (PID $($frontend.Id)): npm run dev"

$pidFile = Join-Path $PSScriptRoot 'dev-pids.json'
[ordered]@{ Backend = $backend.Id; Frontend = $frontend.Id } | ConvertTo-Json | Set-Content -LiteralPath $pidFile
Write-Host "PIDs saved to $pidFile"
