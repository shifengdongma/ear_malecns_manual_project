param([int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pythonExecutable = Join-Path $env:USERPROFILE '.virtualenvs/ear-malecns/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) { throw 'Existing ear-malecns Python environment not found.' }
$url = "http://127.0.0.1:$Port"
$logDirectory = Join-Path $projectDirectory 'outputs/workbench'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
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
if (-not $NoBrowser) {
    $edgeExecutable = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
    $profileDirectory = Join-Path $projectDirectory 'downloads/workbench-browser'
    Start-Process -FilePath $edgeExecutable -ArgumentList @(( '--user-data-dir="' + $profileDirectory + '"'), '--no-first-run', '--new-window', $url)
}
