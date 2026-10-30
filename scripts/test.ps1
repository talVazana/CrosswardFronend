$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$failed = $false

$python = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }
$pythonArgs = if ($python -eq 'py') { @('-3', '-m', 'pytest') } else { @('-m', 'pytest') }
$pythonArgs += @(
    '-q',
    '-p', 'no:cacheprovider',
    '--basetemp', (Join-Path $env:TEMP 'crossword-pytest')
)

Push-Location (Join-Path $root 'backend')
Write-Host "Running backend tests: $python $($pythonArgs -join ' ')"
& $python @pythonArgs
if ($LASTEXITCODE -ne 0) { $failed = $true }
Pop-Location

Push-Location (Join-Path $root 'frontend')
Write-Host "Running frontend tests: npx vitest run"
npx vitest run
if ($LASTEXITCODE -ne 0) { $failed = $true }
Pop-Location

if ($failed) { exit 1 } else { exit 0 }
