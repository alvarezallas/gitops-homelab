$ErrorActionPreference = 'Stop'
$r = 'C:\Users\aalva\Documents\Codex\ia-workspace-runtime\speakr-pc'
$python = Join-Path $r 'venv\Scripts\python.exe'
$listener = Get-NetTCPConnection -LocalPort 18995 -State Listen -ErrorAction SilentlyContinue
if ($listener) { exit 0 }
Remove-Item -LiteralPath (Join-Path $r 'stop') -ErrorAction SilentlyContinue
while (-not (Test-Path -LiteralPath (Join-Path $r 'stop'))) {
    Start-Process -FilePath $python -ArgumentList @('-X','utf8',('"' + (Join-Path $r 'bridge.py') + '"')) -WindowStyle Hidden -Wait -RedirectStandardOutput (Join-Path $r 'bridge.log') -RedirectStandardError (Join-Path $r 'bridge-error.log')
    Start-Sleep -Seconds 10
}
