$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$failed = $false

Push-Location (Join-Path $root 'backend')
Write-Host "Running backend tests: python -m pytest"
python -m pytest
if ($LASTEXITCODE -ne 0) { $failed = $true }
Pop-Location

Push-Location (Join-Path $root 'frontend')
Write-Host "Running frontend tests: npx vitest run"
npx vitest run
if ($LASTEXITCODE -ne 0) { $failed = $true }
Pop-Location

if ($failed) { exit 1 } else { exit 0 }
