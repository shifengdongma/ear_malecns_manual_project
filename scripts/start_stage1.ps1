param(
    [ValidateSet('offline', 'live', 'public', 'cached')][string]$Mode = 'offline',
    [string]$Snapshot = '',
    [string]$RunId = ''
)
$ErrorActionPreference = 'Stop'
$env:EAR_MALECNS_ROOT = 'H:\ear-malecns'
$env:EAR_MALECNS_PROJECT = Join-Path $env:EAR_MALECNS_ROOT 'project\ear_malecns_manual_project'
if (-not (Test-Path -LiteralPath $env:EAR_MALECNS_PROJECT)) { throw 'H-drive project is unavailable.' }
$env:PIP_CACHE_DIR = Join-Path $env:EAR_MALECNS_PROJECT 'downloads\pip-cache'
$env:TEMP = Join-Path $env:EAR_MALECNS_PROJECT 'downloads\tmp'
$env:TMP = $env:TEMP
$env:MPLCONFIGDIR = Join-Path $env:EAR_MALECNS_PROJECT 'downloads\matplotlib'
$pythonExe = Join-Path $env:USERPROFILE '.virtualenvs\ear-malecns\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create the ear-malecns environment first; see README.md.' }
$runArguments = @((Join-Path $env:EAR_MALECNS_PROJECT 'scripts\06_stage1.py'), '--mode', $Mode)
if ($Snapshot) { $runArguments += @('--snapshot', $Snapshot) }
if ($RunId) { $runArguments += @('--run-id', $RunId) }
& $pythonExe @runArguments
exit $LASTEXITCODE
