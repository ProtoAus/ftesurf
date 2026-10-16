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
# A worktree commit need not be pushed just to compile/test it. Export exactly
# that inspected object through an owned temporary ref, not whichever local
# branch the canonical checkout happens to have.
$common = (& git -C $FteRoot rev-parse --path-format=absolute --git-common-dir).Trim()
if ($LASTEXITCODE) { throw 'cannot resolve engine common Git directory' }
function WslDrivePath ([string]$Path) {
    $Path = [IO.Path]::GetFullPath($Path)
    if ($Path -notmatch '^[A-Za-z]:[\\/]') { throw 'Linux build requires a local-drive engine path' }
    '/mnt/' + $Path.Substring(0, 1).ToLowerInvariant() + ($Path.Substring(2) -replace '\\', '/')
}
$wslEngine = WslDrivePath $FteRoot
$wslGit = WslDrivePath $common
$sourceRef = "refs/ftesurf-build/$PID-$($full.Substring(0, 12))"
& git -C $FteRoot update-ref $sourceRef $full ('0' * 40)
if ($LASTEXITCODE) { throw 'cannot create owned temporary source ref' }

# --exec: without it wsl.exe hands the joined line to a shell, which expands $vars on the way.
# This checkout, not C:\FTESurf: a worktree's build.sh and dist\ are its own.
$wslRoot = '/mnt/' + $root.Substring(0, 1).ToLower() + ($root.Substring(2) -replace '\\', '/')
$wslArgs = @('-d', $Distro, '-u', 'root', '--cd', $wslRoot, '--exec', '/usr/bin/env', "FTESURF_LINUX_OUT=$wslRoot/dist/$OutName",
    "FTESURF_ENGINE_SOURCE=$wslEngine", "FTESURF_ENGINE_GIT_DIR=$wslGit", "FTESURF_ENGINE_REF=$sourceRef", '/bin/bash', 'tools/linux/build.sh', $full)
if ($ExpectSonames) { $wslArgs += '--expect-sonames' }
try {
    & wsl.exe @wslArgs
    $rc = $LASTEXITCODE
} finally {
    & git -C $FteRoot update-ref -d $sourceRef $full
    if ($LASTEXITCODE) { throw "temporary source ref cleanup blocked: $sourceRef at $full" }
}

$bi = Join-Path $root "dist\$OutName\BUILDINFO.txt"
if (-not (Test-Path $bi)) { throw "build.sh exited $rc and wrote no BUILDINFO.txt" }
$text = Get-Content $bi -Raw
if ($text -notmatch "(?m)^commit\s+$full\s*$") { throw "BUILDINFO commit is not $full" }
if ($text -notmatch '(?m)^gates\s+all PASS\s*$') { throw "gates failed (dist\$OutName\logs\gates.log)" }
if ($rc) { throw "build.sh exited $rc" }
Write-Host "linux build OK: $full"
