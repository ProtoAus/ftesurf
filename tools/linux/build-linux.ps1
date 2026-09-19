# Build the Linux x86_64 engine in WSL's bullseye chroot (tools/linux/build.sh) and check its BUILDINFO.
#   pwsh -NoProfile -File tools\linux\build-linux.ps1 [-Commit <sha>] [-ExpectSonames]
# -Commit defaults to ENGINE.txt's pin.  Output: dist\linux-build\.
param(
    [string] $Commit,
    [switch] $ExpectSonames,
    [string] $Distro  = 'Ubuntu-22.04',
    [string] $FteRoot = 'C:\msys64\home\Lex\fteqw',
    [string] $OutName = 'linux-build'   # the drop, under dist\
)
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot)
if (-not $Commit) {
    $m = Select-String -Path (Join-Path $root 'ENGINE.txt') -Pattern '^commit\s+([0-9a-f]{40})' | Select-Object -First 1
    if (-not $m) { throw 'ENGINE.txt has no commit line' }
    $Commit = $m.Matches[0].Groups[1].Value
}
$full = git -C $FteRoot rev-parse --verify "$Commit^{commit}"
if ($LASTEXITCODE) { throw "unknown engine commit $Commit" }
if (-not (git -C $FteRoot branch -r --contains $full)) { Write-Warning "$full is not on any pushed branch" }

# --exec: without it wsl.exe hands the joined line to a shell, which expands $vars on the way.
$wslArgs = @('-d', $Distro, '-u', 'root', '--cd', '/mnt/c/FTESurf', '--exec', '/usr/bin/env', "FTESURF_LINUX_OUT=/mnt/c/FTESurf/dist/$OutName", '/bin/bash', 'tools/linux/build.sh', $full)
if ($ExpectSonames) { $wslArgs += '--expect-sonames' }
& wsl.exe @wslArgs
$rc = $LASTEXITCODE

$bi = Join-Path $root "dist\$OutName\BUILDINFO.txt"
if (-not (Test-Path $bi)) { throw "build.sh exited $rc and wrote no BUILDINFO.txt" }
$text = Get-Content $bi -Raw
if ($text -notmatch "(?m)^commit\s+$full\s*$") { throw "BUILDINFO commit is not $full" }
if ($text -notmatch '(?m)^gates\s+all PASS\s*$') { throw "gates failed (dist\$OutName\logs\gates.log)" }
if ($rc) { throw "build.sh exited $rc" }
Write-Host "linux build OK: $full"
