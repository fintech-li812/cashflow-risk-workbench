param(
    [Parameter(Mandatory=$true)][string]$KeyPath,
    [string]$SshExecutable='C:\Program Files\Git\usr\bin\ssh.exe'
)
$ErrorActionPreference='Stop'
# Explicit manual launch only. Never terminate or replace an existing listener.
if (-not (Test-Path -LiteralPath $KeyPath -PathType Leaf)) { throw 'SSH key file path is unavailable; no credential content was read.' }
if (-not (Test-Path -LiteralPath $SshExecutable -PathType Leaf)) { throw 'SSH executable path is unavailable.' }
$listener=Get-NetTCPConnection -LocalPort 13317 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    [pscustomobject]@{status='not_started';reason='port_already_in_use';port=13317;owning_pid=@($listener.OwningProcess)} | ConvertTo-Json
    exit 2
}
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$recordDir=Join-Path $PSScriptRoot ('manual_runs\'+$stamp)
New-Item -ItemType Directory -Path $recordDir -ErrorAction Stop | Out-Null
# Start-Process argument strings require quoting paths containing spaces.
if ($KeyPath.Contains('"')) { throw 'Invalid quote in key path.' }
$quotedKey='"'+$KeyPath+'"'
$sshArguments=@('-N','-i',$quotedKey,'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
    '-o','StrictHostKeyChecking=yes','-o','HostKeyAlgorithms=ssh-ed25519',
    '-o','ConnectTimeout=10','-o','ExitOnForwardFailure=yes',
    '-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3',
    '-L','127.0.0.1:13317:/var/run/mysqld/mysqld.sock','root@39.104.201.10')
$tunnel=Start-Process -FilePath $SshExecutable -ArgumentList $sshArguments -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $recordDir 'ssh_stdout.txt') `
    -RedirectStandardError (Join-Path $recordDir 'ssh_stderr.txt') -PassThru
$record=[pscustomobject]@{status='started_not_yet_verified';pid=$tunnel.Id;port=13317;
    local_address='127.0.0.1';scope='existing isolated QA forwarding';
    database_authenticated=$false;credentials_copied=$false;production_changed=$false}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $recordDir 'launch.json') -Encoding UTF8
$record | ConvertTo-Json
# No retries, scheduling, DDL, process termination or automatic cleanup.
