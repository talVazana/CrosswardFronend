$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot   # scripts\ -> code\
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'

$BackendPort = 8001
$FrontendPort = 3000
$RoomId = 'Room1'
$RoomTitle = 'My Crossword'
$BackendUrl = "http://localhost:$BackendPort"

Write-Host ""
Write-Host "== Crossword Arena local launcher =="
Write-Host "Backend : $BackendUrl"
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host "Room    : $RoomId"
Write-Host ""

# 1. Point the frontend at the backend (persistent, so `npm run dev` picks it up)
$envLocal = Join-Path $frontendDir '.env.local'
Set-Content -LiteralPath $envLocal -Value "NEXT_PUBLIC_BACKEND_URL=$BackendUrl" -Encoding Ascii

# 2. Start the backend (uvicorn is not on PATH on Windows; use the py launcher)
Write-Host "Starting backend (port $BackendPort) ..."
$backend = Start-Process -FilePath 'py' -ArgumentList '-3','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$BackendPort" -WorkingDirectory $backendDir -PassThru

# 3. Wait for the backend to become healthy
$healthy = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $h = Invoke-RestMethod -Uri "$BackendUrl/health" -TimeoutSec 2
        if ($h.status -eq 'ok') { $healthy = $true; break }
    } catch { }
}
if (-not $healthy) {
    Write-Host "Backend did not become healthy on $BackendUrl - is the port free?" -ForegroundColor Red
    exit 1
}
Write-Host "Backend healthy."

# 4. Seed a playable room from the sample fixture (in-memory DB, so this is required every start)
Write-Host "Seeding room '$RoomId' ..."
$seedBody = @{ roomId = $RoomId; title = $RoomTitle; status = 'active' } | ConvertTo-Json
$seed = Invoke-RestMethod -Method Post -Uri "$BackendUrl/e2e/seed" -ContentType 'application/json' -Body $seedBody
Write-Host "Room '$RoomId' seeded (puzzle + admin created)."
Write-Host "Admin session token: $($seed.adminSessionToken)"

# 5. Start the frontend
Write-Host "Starting frontend (port $FrontendPort) ..."
$frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev' -WorkingDirectory $frontendDir -PassThru

# 6. Save PIDs for stop-dev.ps1
$pidFile = Join-Path $PSScriptRoot 'dev-pids.json'
[ordered]@{ Backend = $backend.Id; Frontend = $frontend.Id } | ConvertTo-Json | Set-Content -LiteralPath $pidFile

# 7. Give Next.js a moment to boot, then open the browser
Start-Sleep -Seconds 4
$joinUrl = "http://localhost:$FrontendPort/rooms/$RoomId/join"
Start-Process $joinUrl

Write-Host ""
Write-Host "Done."
Write-Host "  Play : $joinUrl"
Write-Host "  Admin: http://localhost:$FrontendPort/admin/rooms/$RoomId"
Write-Host "  Stop : .\scripts\stop-dev.ps1"
Write-Host ""
