param([int]$Port = 8765, [switch]$NoBrowser, [switch]$Research, [switch]$Restart, [string]$PythonExecutable)
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
if (-not $PythonExecutable) { $PythonExecutable = Join-Path $env:USERPROFILE '.virtualenvs/ear-malecns/Scripts/python.exe' }
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
if (-not (Test-Path -LiteralPath $pythonExecutable)) { throw 'Existing ear-malecns Python environment not found.' }
$url = "http://127.0.0.1:$Port"
$logDirectory = Join-Path $projectDirectory 'outputs/workbench'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
if ($Restart) {
    $statePath = Join-Path $logDirectory 'server.json'
    if (Test-Path -LiteralPath $statePath) {
        $serverState = Get-Content -LiteralPath $statePath -Raw -Encoding utf8 | ConvertFrom-Json
        $ownedProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($serverState.pid)"
        $ownedEntry = Join-Path $projectDirectory 'scripts/18_signal_workbench.py'
        if ($ownedProcess -and $ownedProcess.CommandLine.Contains($ownedEntry)) { Stop-Process -Id $serverState.pid }
    }
}
$healthy = $false
try { $reply = Invoke-RestMethod "$url/api/bootstrap" -TimeoutSec 3; $healthy = $reply.dataset -eq 'male-cns:v1.0' } catch {}
if (-not $healthy) {
    $entry = Join-Path $projectDirectory 'scripts/18_signal_workbench.py'
    $serverProcess = Start-Process -FilePath $pythonExecutable -ArgumentList @('-u', ('"' + $entry + '"'), '--port', $Port) -WorkingDirectory $projectDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'server.stdout.log') -RedirectStandardError (Join-Path $logDirectory 'server.stderr.log') -PassThru
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 500
        if ($serverProcess.HasExited) { throw "Workbench exited. Read $logDirectory/server.stderr.log" }
        try { $reply = Invoke-RestMethod "$url/api/bootstrap" -TimeoutSec 3; $healthy = $reply.dataset -eq 'male-cns:v1.0' } catch {}
        if ($healthy) { break }
    }
    if (-not $healthy) { throw "Workbench did not become ready. Read $logDirectory/server.stderr.log" }
}
Write-Host "Ready: $url"
if ($Research) { $url += '/research' }
if (-not $NoBrowser) {
    $edgeExecutable = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
    $profileDirectory = Join-Path $projectDirectory 'downloads/workbench-browser'
    Start-Process -FilePath $edgeExecutable -ArgumentList @(( '--user-data-dir="' + $profileDirectory + '"'), '--no-first-run', '--new-window', $url)
}
