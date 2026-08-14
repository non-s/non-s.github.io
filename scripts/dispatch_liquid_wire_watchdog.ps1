$ErrorActionPreference = "Stop"

$repository = "non-s/non-s.github.io"
$workflow = "liquid-wire-watchdog.yml"
$logDirectory = Join-Path $env:LOCALAPPDATA "LiquidWire"
$logFile = Join-Path $logDirectory "scheduler.log"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

try {
    $gh = (Get-Command gh -ErrorAction Stop).Source
    & $gh workflow run $workflow --repo $repository 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        throw "gh workflow run exited with code $LASTEXITCODE"
    }
    "$(Get-Date -Format o) watchdog dispatch accepted" | Add-Content -LiteralPath $logFile
}
catch {
    "$(Get-Date -Format o) watchdog dispatch failed: $($_.Exception.Message)" | Add-Content -LiteralPath $logFile
    throw
}
