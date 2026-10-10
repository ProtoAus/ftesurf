# release_dryrun.ps1 -Tree <scratch release tree> -FteRoot <engine checkout> -OutDir <dir>
#                    [-BuildNumber <n>] [-Extra <switch names>]
#
# Runs that tree's own src\release\release.ps1 -DryRun -NoLobbyCheck with every network tool it
# calls (rclone, ssh, scp, curl) replaced by a function that does nothing and is listed at the
# end. The script's own dry run still proves R2 write access with a probe object in the
# production bucket and reads the published archive's hash; under this wrapper nothing leaves
# the machine, so its "R2 write access confirmed" line is the stub's and means nothing.
# What it does exercise: every gate, the stage, the deny tripwire, the pack, the archive check
# and the receipt. tools/release_tree.py makes the tree. Exit 0 complete, 1 the script stopped.
param(
    [Parameter(Mandatory)] [string] $Tree,
    [Parameter(Mandatory)] [string] $FteRoot,
    [Parameter(Mandatory)] [string] $OutDir,
    [int] $BuildNumber = 0,
    [string[]] $Extra = @()
)
$global:NetCalls = [System.Collections.Generic.List[string]]::new()
function rclone { $global:NetCalls.Add('rclone ' + ($args -join ' ')); $global:LASTEXITCODE = 0 }
function ssh    { $global:NetCalls.Add('ssh ' + ($args -join ' '));    $global:LASTEXITCODE = 0 }
function scp    { $global:NetCalls.Add('scp ' + ($args -join ' '));    $global:LASTEXITCODE = 0 }
function curl   { $global:NetCalls.Add('curl ' + ($args -join ' '));   $global:LASTEXITCODE = 0 }
function curl.exe { $global:NetCalls.Add('curl.exe ' + ($args -join ' ')); $global:LASTEXITCODE = 0 }

$code = 0
try {
    $params = @{ DryRun = $true; NoLobbyCheck = $true; FteRoot = $FteRoot; OutDir = $OutDir }
    if ($BuildNumber -gt 0) { $params['BuildNumber'] = $BuildNumber }
    foreach ($e in $Extra) { $params[$e] = $true }
    & (Join-Path $Tree 'src\release\release.ps1') @params
} catch {
    Write-Host "RELEASE SCRIPT STOPPED: $($_.Exception.Message)" -ForegroundColor Red
    $code = 1
}
Write-Host ("stubbed network calls: {0}" -f $global:NetCalls.Count)
$global:NetCalls | ForEach-Object { Write-Host ("  " + ($_.Substring(0, [Math]::Min(150, $_.Length)))) }
exit $code
