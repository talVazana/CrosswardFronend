$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root '.firebase\emulator-data'
if (-not (Test-Path -LiteralPath $dataDir)) {
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
}

$arguments = @('emulators:start', '--only', 'firestore')
$metadataFile = Join-Path $dataDir 'firebase-export-metadata.json'
if (Test-Path -LiteralPath $metadataFile) {
    $arguments += @('--import', $dataDir)
}
$arguments += @('--export-on-exit', $dataDir)

Push-Location -LiteralPath $root
try {
    Write-Host "Starting Firestore emulator (project: demo-crossword-arena)"
    Write-Host "Firestore: http://127.0.0.1:8080"
    Write-Host "Emulator UI: http://127.0.0.1:4000"
    Write-Host "Local data: $dataDir"
    Write-Host "Press Ctrl+C to stop."

    firebase @arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
