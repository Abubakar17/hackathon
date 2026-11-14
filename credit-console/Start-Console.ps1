$ErrorActionPreference = 'Stop'
$consoleRoot = $PSScriptRoot
$consolePort = if ($env:PORT) { $env:PORT } else { '8765' }
$consoleAddress = 'http://127.0.0.1:' + $consolePort
try {
    $existingConsole = Invoke-RestMethod ($consoleAddress + '/api/bootstrap') -TimeoutSec 2
    if ($existingConsole.engine) { Start-Process $consoleAddress; exit 0 }
} catch { }
$bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$consoleNode = if (Test-Path -LiteralPath $bundledNode) { $bundledNode } else { (Get-Command node -ErrorAction Stop).Source }
if (-not (Test-Path -LiteralPath (Join-Path $consoleRoot 'node_modules\@smarthorizon-labs\dmn'))) {
    throw 'Install the app dependencies first. See README.md: pnpm install --frozen-lockfile.'
}
$consoleData = Join-Path $consoleRoot 'data'
New-Item -ItemType Directory -Path $consoleData -Force | Out-Null
$consoleProcess = Start-Process -FilePath $consoleNode -ArgumentList 'server.mjs' -WorkingDirectory $consoleRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $consoleData 'server.log') -RedirectStandardError (Join-Path $consoleData 'server-error.log') -PassThru
Set-Content -LiteralPath (Join-Path $consoleData 'server.pid') -Value $consoleProcess.Id
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 200
    try { $ready = Invoke-RestMethod ($consoleAddress + '/api/bootstrap') -TimeoutSec 1; if ($ready.engine) { Start-Process $consoleAddress; exit 0 } } catch { }
}
throw 'The console did not start. Check data/server-error.log.'
