# =============================================================================
#  release.ps1 -- cut an FTESurf release: stage, pack, publish, page.
#
#    .\src\release\release.ps1 -SetupSite       # FIRST TIME ONLY: push the Pi-side
#                                               # files so install.sh exists to sudo
#    .\src\release\release.ps1 -DryRun          # stage + pack + verify, publish nothing
#    .\src\release\release.ps1                  # full release at the current VERSION
#    .\src\release\release.ps1 -Bump patch      # 0.1.0 -> 0.1.1, then full release
#    .\src\release\release.ps1 -Build -Bump minor
#    .\src\release\release.ps1 -Bump patch -Linux <drop>   # also ship the Linux
#                                               # x86_64 tar.xz from a tools\linux drop
#
#  It does four things in order, and refuses rather than guesses at every step:
#
#    1. MEASURE   the version, the QC build, the engine patch, and the hash of
#                 every binary that is about to ship.
#    2. STAGE     an explicit allowlist into release\stage-<ver>\, run a deny
#                 tripwire over it, and pack from inside it.
#    3. PUBLISH   the archive to Cloudflare R2 at dl.proto.bar/ftesurf/.
#    4. PAGE      render index.html from the receipt and deploy it to the Pi.
#
#  WHY THE ALLOWLIST IS NOT NEGOTIABLE.  C:\FTESurf is the LIVE INSTALL, not a
#  clean source tree.  Sitting in the repo root right now, beside the ~42 MB
#  that ships: `report` (9,410 bytes, contains a plaintext SSH password),
#  identity.pfx, qkey, and five superseded engine builds.  Under ftesurf\:
#  3.3 GB of screenshots, 1.1 GB of mapshots, 630 MB of recorded runs, a 351 MB
#  surf_fantasy.bsp, and data\consent.txt -- which, if shipped, pre-accepts the
#  terms on the player's behalf.
#
#  THE CHEAT SAMPLES MOVED OUT on 2026-09-14.  client.dll, momentum.dll,
#  Turnbind.exe and test2.cpp now live under C:\FTESurf-private\Cheats, which is
#  outside this root and is not a git repo and has no ancestor that is one.  So
#  this paragraph used to name four reasons the allowlist cannot be relaxed and
#  now names three.  THE POLICY IS UNCHANGED: the plaintext password, the
#  identity material and the consent record are all still here, and any one of
#  them is sufficient on its own.
#
#  Their deny patterns below are KEPT DELIBERATELY.  A tripwire that matches
#  nothing costs nothing, the anti-cheat work that put them here is ongoing so
#  they can come back at any time, and a pattern removed on the grounds that it
#  currently matches nothing is exactly the stale-exclude failure this whole
#  header argues against.
#
#  So: name what ships, copy it out, and inspect the copy.  An exclude list over
#  this tree is one stale pattern away from publishing a password, and 7-Zip's
#  -x! patterns are exactly the kind of thing that quietly stops matching.
#
#  WHY IT REFUSES SO OFTEN.  Three independent ways this tree can produce an
#  archive whose version string is a lie, all of which were live when this was
#  written:
#
#    * ftesurf64.exe was the PRE-317 engine while ENGINE_PATCHES.md said 320 --
#      and fteplug_hl2_x64.dll was at 318, i.e. Patch 317's .phy-winding fix
#      with its engine half missing.  A combination no A/B was ever run against.
#    * All three .dat predated their own sources.  menu.dat did not contain
#      Lob_JoinAsk; the archive would have been stamped with the build number of
#      a commit whose headline feature was not in it.
#    * ENGINE.txt's pin block claimed patch 313 / qcbuild 62.
#
#  A number scraped from a changelog is a claim about a DOCUMENT.  Only a hash
#  is a claim about the bytes in the archive.  This script records both and says
#  which is which, and every override is written into the receipt BY NAME, so a
#  compromised release is self-describing rather than indistinguishable from a
#  clean one.
#
#  RELATED FILES
#    VERSION                     one line, the only hand-edited release input
#    src\release\page.template.html   the page, @@TOKEN@@ placeholders
#    src\release\ftesurf.nginx   the nginx snippet (source of truth, in git)
#    src\release\install.sh      one-time sudo wiring on the Pi
#    src\release\publish.sh      routine no-sudo atomic swap
#    src\release\releaselib.ps1  helpers (tests: test_releaselib.ps1)
#    src\release\linux-pack.sh   the WSL half of -Linux (inspect, pack, verify)
#    dist\ftesurf-<ver>.json     the receipt; the page renders only from this
# =============================================================================
[CmdletBinding()]
param(
    [ValidateSet('patch', 'minor', 'major')]
    [string] $Bump,

    [switch] $Build,          # run src\build.ps1 -Engine first
    [int]    $BuildNumber,    # the QC build to ship, when no commit states one
    [switch] $DryRun,         # stage, pack and verify; publish nothing
    [switch] $SetupSite,      # push the Pi-side files, print the sudo line, stop
    [switch] $SkipUpload,
    [switch] $SkipSite,

    # Gate overrides. -Force is an alias for all three and nothing more.
    [switch] $AllowDirty,
    [switch] $AllowStale,
    [switch] $AllowEngineSkew,
    [switch] $Force,

    [switch] $Tag,            # local annotated tag v<ver>; never pushed
    [switch] $Prune,          # delete old archives from R2 (default off)
    [int]    $PruneKeep = 5,

    [switch] $VerifyFull,     # re-download the whole archive and re-hash it
    [switch] $NoLobbyCheck,
    [string] $BwLimit,        # overrides the lobby-derived throttle

    [int]    $MaxFileMB  = 24,
    [int]    $MaxTotalMB = 80,

    [string] $OutDir,
    [string] $FteRoot  = $(if ($env:FTESURF_FTEROOT) { $env:FTESURF_FTEROOT } else { 'C:\msys64\home\Lex\fteqw' }),
    [string] $PiHost   = $(if ($env:FTESURF_PIHOST)  { $env:FTESURF_PIHOST }  else { 'proto@192.168.1.102' }),
    [string] $SiteRoot = '/srv/nvme/ftesurf-site',
    [string] $SiteUrl  = 'https://proto.bar/ftesurf',
    [string] $Remote   = 'r2',
    [string] $Bucket   = 'quakers-dl',
    [string] $Prefix   = 'ftesurf',
    [string] $DlBase   = 'https://dl.proto.bar',

    # A tools\linux build drop: fteqw64, fteplug_hl2_amd64.so, BUILDINFO.txt.
    [string]   $Linux,
    [string]   $LinuxDistro = $(if ($env:FTESURF_WSL_DISTRO) { $env:FTESURF_WSL_DISTRO } else { 'Ubuntu-22.04' }),
    [string[]] $LinuxNeededAllow = @('libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0', 'librt.so.1', 'ld-linux-x86-64.so.2', 'libz.so.1')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# --- paths -------------------------------------------------------------------
$RelDir  = $PSScriptRoot                                  # ...\src\release
$SrcDir  = Split-Path -Parent $RelDir                     # ...\src
$SurfDir = Split-Path -Parent $SrcDir                     # C:\FTESurf
if (-not $OutDir) { $OutDir = Join-Path $SurfDir 'dist' }
$StageRoot   = Join-Path $SurfDir 'release'
$EngineRel   = Join-Path $FteRoot 'engine\release'
$PatchesMd   = Join-Path $FteRoot 'ENGINE_PATCHES.md'
$VersionFile = Join-Path $SurfDir 'VERSION'
$SevenZip    = 'C:\Program Files\7-Zip\7z.exe'

if ($Force) { $AllowDirty = $true; $AllowStale = $true; $AllowEngineSkew = $true }

# --- output ------------------------------------------------------------------
$script:StepNo = 0
function Step ($m) { $script:StepNo++; Write-Host "`n[$script:StepNo] $m" -ForegroundColor Cyan }
function Info ($m) { Write-Host "    $m" }
function Good ($m) { Write-Host "    $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "    $m" -ForegroundColor Yellow }
function Fail ($m) {
    # PowerShell's error formatter folds a thrown multi-line message onto one line
    # and then hard-wraps it, which turns a per-file gate report into an unreadable
    # run-on. Print the real message first, then throw only its first line so the
    # exception (and the exit code) stay intact.
    $lines = $m -split "`r?`n"
    Write-Host ''
    foreach ($l in $lines) { Write-Host "  $l" -ForegroundColor Red }
    Write-Host ''
    throw $lines[0]
}
function HumanSize ([long]$b) {
    if ($b -ge 1MB) { '{0:N1} MB' -f ($b / 1MB) }
    elseif ($b -ge 1KB) { '{0:N0} KB' -f ($b / 1KB) }
    else { "$b bytes" }
}
# Native tools do not set $ErrorActionPreference; check every one explicitly.
function Native ($exe, [string[]]$argv, [string]$what) {
    $out = & $exe @argv 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail "$what failed (exit $LASTEXITCODE)`n$($out -join "`n")"
    }
    return $out
}
. (Join-Path $PSScriptRoot 'releaselib.ps1')

# =============================================================================
#  THE SHIP SET
#
#  NOT derived from `git ls-files`.  git's allowlist is an allowlist for
#  SOURCE: every build output here is deliberately gitignored, so a git-derived
#  archive would be missing ftesurf64.exe, all three .dat, particles\ (7 files),
#  gfx\crosshairs\ (3, precached by name in the QC), gfx\mapthumbs\ (6 atlases,
#  29.3 MB) and data\map*.txt -- it would boot with no crosshairs, no map
#  thumbnails and no fs_automount dependency list -- while ADDING 624
#  cfg\test\ fixtures, src\, tools\ and surfd\.
#
#  ftesurf\data\ IS A NAMED LIST AND MUST STAY ONE.  consent.txt and 69
#  p3??_*.hid patch-test captures live in that directory alongside the four
#  files that ship.  `data\*.txt` would sweep consent.txt on its first run.
# =============================================================================
$ShipRootFiles = @(
    'ftesurf64.exe'          # the engine
    'fteplug_hl2_x64.dll'    # VPK/VMT/VTF/.phy -- without it no Source content loads
    'default.fmf'            # carries the 66.667 Hz / 15 ms tick constants
    'ftesurf.bat'            # sets the CWD FTE takes basedir from; seeds fs_addons.txt
    'ftesurf_debug.bat'
    'LICENSE'                # GPLv2. Required alongside a redistributed binary.
)
$ShipGameFiles = @(
    'ftesurf/csprogs.dat'
    'ftesurf/qwprogs.dat'
    'ftesurf/menu.dat'
    # The annotated master. The staging step below ALSO generates the live
    # fs_addons.txt from it -- that is the file the engine actually reads.
    'ftesurf/fs_addons.default.txt'
    'ftesurf/data/mapdeps.txt'
    'ftesurf/data/mapmeta.txt'
    'ftesurf/data/mapmeta_override.txt'
    'ftesurf/data/mapparticles.txt'
)
$ShipGlobs = @(
    # cfg\ top level only -- test\ (663 per-patch fixtures) is a subdirectory
    # and is excluded by not recursing.  build*.cfg are per-build test scripts and
    # fs_*.cfg are dev tools; lobby_local.cfg holds SURFD_KEY on the Pi and must
    # never appear here even by accident.
    @{ Path = 'ftesurf/cfg';            Filter = '*.cfg'; Deny = @('build*.cfg', 'fs_*.cfg', 'lobby_local.cfg') }
    # P330: the per-map layer lives in cfg\maps\ now (80 map_*.cfg rulesets plus
    # the render_*.cfg client layer and its render_default.cfg baseline).  It is
    # shipping content -- SV_LoadMapRuleset and CSQC_WorldLoaded both read it at
    # map load -- so the non-recursion above that keeps test\ out must not keep
    # this out too.
    @{ Path = 'ftesurf/cfg/maps';       Filter = '*.cfg'; Deny = @() }
    # P330: the lobby and mode ruleset layer (lobby.cfg, lobby1..12, mode_bhop)
    # lives in cfg\lobby\ now.  It shipped from the cfg top level before the
    # move and still must: the Pi's run.sh execs it at boot.  lobby_local.cfg
    # stays denied by the unanchored tripwire below wherever it sits.
    @{ Path = 'ftesurf/cfg/lobby';      Filter = '*.cfg'; Deny = @('lobby_local.cfg') }
    @{ Path = 'ftesurf/glsl';           Filter = '*' }
    @{ Path = 'ftesurf/models';         Filter = '*' }
    @{ Path = 'ftesurf/particles';      Filter = '*' }
    @{ Path = 'ftesurf/scripts';        Filter = '*' }
    @{ Path = 'ftesurf/gfx/fonts';      Filter = '*' }
    @{ Path = 'ftesurf/gfx/mapthumbs';  Filter = '*.png' }
    @{ Path = 'ftesurf/gfx/crosshairs'; Filter = '*.png' }
)

# =============================================================================
#  THE DENY TRIPWIRE
#
#  Defence in depth, run over the MATERIALISED stage and again over the packed
#  archive's own listing.  The allowlist above is the control; this is what
#  catches a typo in it.  Anchored where anchoring matters:
#
#    ^ftesurf/ftesurf\.cfg$   is the dev's 63 KB personal config and must not
#                             ship -- but ftesurf/particles/ftesurf.cfg is a
#                             REAL shipping file, exec'd on every map load
#                             (cl_emit.qc:1382).  An unanchored ftesurf\.cfg
#                             rule would kill the particle system.
# =============================================================================
$DenyPatterns = @(
    '(^|/)report$'                     # plaintext SSH password
    '\.pfx$'
    '(^|/)qkey$'
    '(^|/)identity\.'
    '(^|/)consent\.txt$'               # shipping it pre-accepts the terms
    '^ftesurf/ftesurf\.cfg$'           # NOT particles/ftesurf.cfg -- see above
    '(^|/)lobby_local\.cfg$'           # SURFD_KEY
    '(^|/)installed\.lst$'
    '(^|/)conhistory\.txt$'
    'core\.txt$'                       # csqccore.txt / menucore.txt
    '\.lno$'                           # fteqcc debug symbols
    '\.hid$'                           # patch-test HID captures
    '\.prev$'
    '\.pre[-0-9a-z]+$'
    '\.p[0-9]{3}$'
    '_p[0-9]{3}\.exe$'
    '(^|/)(client|momentum)\.dll$'     # cheat samples -- moved to C:\FTESurf-private
    '(^|/)Turnbind\.exe$'              #   2026-09-14; kept as a tripwire, see header
    '(^|/)config\.json$'               #   (Turnbind's, among others)
    '\.(cpp|env|bsp|log|py|pyc)$'      # py: strafepro is Python, and tools\ never ships
    '(^|/)(testrun|test)/'             # P330: cfg/testrun became cfg/test; data/testrun rec fixtures stay denied too
    '(^|/)\.git'
    '(^|/)crashaddr\.txt$'
)

# --- -Linux: a second archive, ftesurf-<ver>-linux-x86_64.tar.xz ---------------
#  Its ftesurf\ tree, default.fmf, LICENSE and SOURCE.txt are copied from the
#  Windows stage, so both archives carry the same game bytes. $LinuxDeny is
#  applied on top of $DenyPatterns, and only to the Linux tree.
$LinuxTop  = 'FTESurf'
$LinuxExec = @('ftesurf64', 'ftesurf.sh')
$LinuxRequired = @('ftesurf64', 'fteplug_hl2_amd64.so', 'ftesurf.sh', 'default.fmf', 'LICENSE',
    'INSTALL.txt', 'VERSION.txt', 'SOURCE.txt', 'ftesurf/csprogs.dat', 'ftesurf/qwprogs.dat', 'ftesurf/menu.dat',
    'ftesurf/fs_addons.default.txt', 'ftesurf/fs_addons.txt', 'ftesurf/cfg/default.cfg')
$LinuxTokenNames = @('LINUX_URL', 'LINUX_FILENAME', 'LINUX_SIZE_HUMAN', 'LINUX_SIZE_BYTES', 'LINUX_SHA256', 'LINUX_GLIBC', 'LINUX_ENGINE')
$LinuxDeny = @(
    '\.(exe|dll|bat|cmd|lnk|pdb)$'
    '\.db$'                            # symbols stay with the drop, for crash reports
    '(^|/)steam_libraries\.txt$'
    '(^|/)(crash|stderr)\.log'
    '(^|/)fteqw(-sv)?64$'              # the client ships as ftesurf64; no server
)
# The build's own gates (BUILDINFO `gates all PASS`), re-checked on the bytes that
# ship: GnuTLS compiled in, Patch 386's versioned EGL/GLESv2 names, and zstd in the
# plugin (without it img_vtf.c refuses most of Momentum's textures).
$LinuxExeMustHave   = @('libgnutls.so.30', 'gnutls_certificate_allocate_credentials', 'libEGL.so.1', 'libGLESv2.so.2', 'libXrandr.so.2', 'libXxf86vm.so.1', 'libXxf86dga.so.1')
$LinuxPluginMustNot = @('needs a build with zstd')

function Invoke-Wsl ([string[]]$argv, [string]$what) {
    $r = Invoke-WslRaw $LinuxDistro $argv
    if ($r.Rc -ne 0) { Fail "$what failed (exit $($r.Rc))`n$($r.Lines -join "`n")" }
    return $r.Lines
}
function WslPath ([string]$p) {
    try { return ConvertTo-WslPath $LinuxDistro $p } catch { Fail $_.Exception.Message }
}
# One R2 object's size and md5, or $null when absent.
function Get-R2Object ([string]$Key) {
    $j = & rclone lsjson --hash "${Remote}:$Bucket/$Key" --bind 0.0.0.0 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $j) { return $null }
    $o = @($j | Out-String | ConvertFrom-Json)
    if (-not $o.Count) { return $null }
    $md5 = if (($o[0].PSObject.Properties.Name -contains 'Hashes') -and $o[0].Hashes) { $o[0].Hashes.md5 } else { $null }
    [pscustomobject]@{ Size = [long]$o[0].Size; Md5 = $md5 }
}
# The Windows PUT's throttle policy; its $limit exists only when that PUT runs.
function Get-BwLimit {
    if ($BwLimit) { return $BwLimit }
    if ($NoLobbyCheck) { return '3M' }
    try {
        $lob = Invoke-RestMethod -Uri "http://$(($PiHost -split '@')[-1]):8084/lobbies.json" -TimeoutSec 5
        if (($lob.lobbies | Measure-Object -Property players -Sum).Sum -eq 0) { return '3M' }
    } catch { }
    return '512k'
}

# =============================================================================
#  0.  PREFLIGHT
# =============================================================================
Step 'Preflight'
foreach ($p in @($SurfDir, $SrcDir, $RelDir)) {
    if (-not (Test-Path -LiteralPath $p)) { Fail "missing directory: $p" }
}
if (-not (Test-Path -LiteralPath $SevenZip)) {
    Fail "7-Zip not found at $SevenZip. Install 7-Zip, or edit `$SevenZip at the top of this script."
}
foreach ($t in @('git', 'rclone', 'curl', 'ssh', 'scp')) {
    if (-not (Get-Command $t -ErrorAction SilentlyContinue)) { Fail "$t is not on PATH" }
}
if (-not (Test-Path -LiteralPath $VersionFile)) {
    Fail "no VERSION file at $VersionFile. Create it with a single line, e.g. 0.1.0"
}
# A VERSION that git ignores is a VERSION a fresh clone does not have -- the script
# would then restart at 0.1.0 and republish a version dl.proto.bar already serves,
# at a URL with a one-year immutable TTL and no API token to purge it.
& git -C $SurfDir check-ignore -q 'VERSION' 2>$null
if ($LASTEXITCODE -eq 0) {
    Fail @"
VERSION is ignored by .gitignore, so it is not in the repository.
.gitignore is an allowlist (`/*` then `!/name`); add this line beside `!/ENGINE.txt`:
    !/VERSION
then prove it with:  git -C $SurfDir check-ignore -v VERSION
"@
}
Good "7-Zip, git, rclone, curl, ssh, scp present; VERSION is tracked"
if ($Linux) {
    if (-not (Test-Path -LiteralPath $Linux -PathType Container)) { Fail "-Linux: no drop directory at $Linux" }
    $LinuxDrop = (Resolve-Path -LiteralPath $Linux).Path
    foreach ($f in @('fteqw64', 'fteplug_hl2_amd64.so', 'BUILDINFO.txt')) {
        if (-not (Test-Path -LiteralPath (Join-Path $LinuxDrop $f) -PathType Leaf)) {
            Fail "-Linux: the drop $LinuxDrop has no $f (tools\linux\build.sh writes all three)"
        }
    }
    $LinuxPack = Join-Path $RelDir 'linux-pack.sh'
    if (-not (Test-Path -LiteralPath $LinuxPack)) { Fail "missing $LinuxPack" }
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { Fail 'wsl.exe is not on PATH' }
    $LinuxPackWsl = WslPath $LinuxPack
    $LinuxDropWsl = WslPath $LinuxDrop
    Invoke-Wsl @('sh', $LinuxPackWsl, 'tools') "linux-pack.sh tools (WSL $LinuxDistro)" | Out-Null
    Good "WSL $LinuxDistro has the pack tools; Linux drop $LinuxDrop"
}

# =============================================================================
#  0b. -SetupSite : push the Pi-side files and stop.
#
#  The three Pi-side files are normally uploaded by the deploy step at the end of
#  a release -- which means that before the FIRST release they are not on the Pi
#  at all, and the `sudo sh .../install.sh` line printed by the setup check has
#  nothing to run. This switch exists so that chicken-and-egg has a one-command
#  answer. It needs no version, no archive and no build.
# =============================================================================
if ($SetupSite) {
    Step 'Push the Pi-side files'
    $sshOpts = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10')
    & ssh @sshOpts $PiHost "mkdir -p '$SiteRoot/releases' '$SiteRoot/.incoming'"
    if ($LASTEXITCODE -ne 0) { Fail "cannot reach $PiHost over ssh" }
    foreach ($f in @('ftesurf.nginx', 'install.sh', 'publish.sh')) {
        & scp @sshOpts -q (Join-Path $RelDir $f) "${PiHost}:$SiteRoot/$f"
        if ($LASTEXITCODE -ne 0) { Fail "scp $f failed" }
    }
    & ssh @sshOpts $PiHost "chmod +x '$SiteRoot/install.sh' '$SiteRoot/publish.sh'"
    Good "pushed ftesurf.nginx, install.sh and publish.sh to $SiteRoot"
    Write-Host "`n  Run this once. It is the only step in the pipeline that needs a password:" -ForegroundColor Yellow
    Write-Host "`n      ssh $PiHost" -ForegroundColor White
    Write-Host "      sudo sh $SiteRoot/install.sh`n" -ForegroundColor White
    return
}

# =============================================================================
#  0c. OPTIONAL BUILD
# =============================================================================
if ($Build) {
    Step 'Build (src\build.ps1 -Engine)'
    $bp = Join-Path $SrcDir 'build.ps1'
    if (-not (Test-Path -LiteralPath $bp)) { Fail "missing $bp" }
    # Called as a script, not captured: build.ps1 writes progress to the host and
    # fteqcc prints its banner on stderr, which a `2>&1` capture under
    # $ErrorActionPreference='Stop' turns into a terminating error mid-compile.
    & $bp -Engine
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { Fail "build.ps1 -Engine failed (exit $LASTEXITCODE)" }
    Good 'build.ps1 -Engine completed'
}

# =============================================================================
#  1.  VERSION
# =============================================================================
Step 'Version'
$verRaw = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
if ($verRaw -notmatch '^\d+\.\d+\.\d+$') {
    Fail "VERSION must be exactly MAJOR.MINOR.PATCH; found '$verRaw'"
}
if ($Bump) {
    $n = @($verRaw.Split('.') | ForEach-Object { [int]$_ })
    # EVERY component is parenthesised on purpose. PowerShell's comma operator
    # binds TIGHTER than `+`, so @($n[0], $n[1], $n[2] + 1) parses as
    # (@($n[0], $n[1], $n[2])) + 1 -- array concatenation, which APPENDS 1 and
    # turns 0.1.0 into "0.1.0.1". It did exactly that on the first -Bump ever run.
    switch ($Bump) {
        'major' { $n = @(($n[0] + 1), 0, 0) }
        'minor' { $n = @($n[0], ($n[1] + 1), 0) }
        'patch' { $n = @($n[0], $n[1], ($n[2] + 1)) }
    }
    $newVer = $n -join '.'
    # VALIDATE BEFORE WRITING. The first version of this wrote VERSION and then
    # validated, so a bad computation persisted a bad version to disk and every
    # later run started from it.
    if ($newVer -notmatch '^\d+\.\d+\.\d+$') {
        Fail "-Bump $Bump computed '$newVer' from '$verRaw', which is not MAJOR.MINOR.PATCH. VERSION not touched."
    }
    if (-not $DryRun) {
        [System.IO.File]::WriteAllText($VersionFile, "$newVer`n", (New-Object System.Text.UTF8Encoding $false))
        Info "VERSION $verRaw -> $newVer"
    } else {
        Info "VERSION $verRaw -> $newVer (not written: -DryRun)"
    }
    $Ver = $newVer
} else {
    $Ver = $verRaw
}
# The version crosses into a remote shell in publish.sh, where it lands beside
# rm -rf. Validate at the boundary; publish.sh re-validates on its own side.
if ($Ver -notmatch '^\d+\.\d+\.\d+$') { Fail "refusing to use version '$Ver'" }
Good "version $Ver"

$ArchiveName = "ftesurf-$Ver.7z"
$ArchivePath = Join-Path $OutDir $ArchiveName
$ObjectKey   = "$Prefix/$ArchiveName"
$ArchiveUrl  = "$DlBase/$ObjectKey"
$LinuxArchiveName = "ftesurf-$Ver-linux-x86_64.tar.xz"
$LinuxArchivePath = Join-Path $OutDir $LinuxArchiveName
$LinuxObjectKey   = "$Prefix/$LinuxArchiveName"
$LinuxArchiveUrl  = "$DlBase/$LinuxObjectKey"

# =============================================================================
#  2.  PROVENANCE
#
#  Measured now, never cached.  The one file in this repo that already caches
#  derived provenance -- ENGINE.txt's pin block -- was wrong by 7 build numbers
#  and 4 patch numbers when this script was written.
# =============================================================================
Step 'Provenance'

# HEAD is captured ONCE. Another session commits into this tree; HEAD moved
# three times during a single planning session.
$GitHead    = (& git -C $SurfDir rev-parse HEAD).Trim()
$GitHeadSub = (& git -C $SurfDir log -1 --pretty=format:'%s').Trim()
$GitShort   = $GitHead.Substring(0, 8)

# QC build: scan BACK through subjects, because HEAD is often a `surfd:` or
# `Checkpoint:` commit -- 9 of the last 32 subjects do not name a build.
# Subjects only, never bodies: a body match finds "QC builds 58-62" and returns
# 62, which is six behind and looks entirely plausible.
#
# THE `QC ` PREFIX IS NOT OPTIONAL DECORATION -- IT COST A WRONG RECEIPT ONCE.
# Build 80's subject is "QC build 80: a run may be twelve hours long", and the
# original pattern anchored straight to `Build`, so it did not match, scanned
# past it, and found "build 79: measure the journal qcrequest..." one commit
# back.  The release then measured 79 for an archive containing 80.
#
# That is a WRONG NUMBER IN A PERMANENT PUBLIC RECEIPT, which is the one class
# of defect this script cannot walk back: a published version string can never
# be replaced, only bumped.  It is also invisible at every other gate -- the
# archive is correct, the hashes are correct, every file ships as intended, and
# only the provenance line lies.
#
# WHAT ACTUALLY CAUGHT IT was the pin-drift check further down (ENGINE.txt says
# qcbuild 80, this said 79).  That check exists because these are TWO
# INDEPENDENT HAND-MAINTAINED STATEMENTS of the same fact, and it earned its
# keep here.  Keep it a Warn rather than a Fail: the legitimate case -- a
# release cut between a build commit and the ENGINE.txt bump -- is real, and a
# hard failure there would block a release for a discrepancy a human can read.
#
$qcBuild = $null; $qcCommit = $null
foreach ($line in (& git -C $SurfDir log -200 --pretty=format:'%H %s')) {
    if ($line -match '^(\S+)\s+(?:QC\s+)?Build\s+(\d+)\b') { $qcCommit = $Matches[1]; $qcBuild = [int]$Matches[2]; break }
}
# The throw is the load-bearing half. An unmatched -match leaves $null, which
# interpolates to "" and ships a receipt reading "QC build " that uploads and
# renders perfectly.
if ($null -eq $qcBuild) {
    # -BuildNumber N: the operator IS the Build NN commit.  AGENTS.md says the
    # number moves only on the user's own "Build NN" commit, and the script used to
    # read that as "there must be one in git history" -- which fails outright once
    # the last such commit is more than 200 back, blocking a release for a
    # formality nobody owed.  An explicit number is the same authority by a shorter
    # path, and it still has to agree with ENGINE.txt's `qcbuild` pin (the drift
    # check below compares them).
    #
    # THE PARAMETER IS NOT NAMED -QcBuild, AND THAT IS NOT TASTE.  PowerShell
    # variable names are case-insensitive, so `$QcBuild = $null` and the parameter
    # are ONE variable: naming the switch -QcBuild made that line reset the bound
    # argument to 0, and the run then failed with "You cannot call a method on a
    # null-valued expression" 45 lines later with no mention of the switch.  A
    # parameter may never differ from a local only by case -- `grep -in` both
    # spellings before adding one.
    if ($BuildNumber -gt 0) {
        $qcBuild = $BuildNumber
        $qcCommit = $GitHead
        Info "QC build $qcBuild from -BuildNumber (no `"Build NN:`" commit in range)"
    } else {
        Fail 'no "Build NN: ..." commit subject in the last 200 commits; cannot derive the QC build number.  Pass -BuildNumber <n> (it must match ENGINE.txt) or make the commit.'
    }
}

# Engine patch: max over the changelog headings.  The lookahead is load-bearing.
# A looser `Patch *(\d+)(?: *[-] *(\d+))?` returns 34909, from
# "## Patch 248 - 34909 sprite entities across 551 maps".
$enginePatch = 0; $headingCount = 0
if (Test-Path -LiteralPath $PatchesMd) {
    $m = Select-String -LiteralPath $PatchesMd -Pattern '^##+ Patch(?:es)? (\d+)(?:-(\d+))?(?=[\s,.:]|$)' -AllMatches
    foreach ($hit in $m) {
        foreach ($mm in $hit.Matches) {
            $headingCount++
            foreach ($g in 1, 2) {
                if ($mm.Groups[$g].Success) {
                    $v = [int]$mm.Groups[$g].Value
                    if ($v -gt $enginePatch) { $enginePatch = $v }
                }
            }
        }
    }
    # If a future heading style stops matching, max silently becomes 0.
    if ($headingCount -lt 100) { Fail "only $headingCount patch headings matched in $PatchesMd -- the regex has gone stale, refusing to stamp a number" }
} else {
    Warn "no ENGINE_PATCHES.md at $PatchesMd -- engine patch recorded as 0"
}
Info "QC build $qcBuild (commit $($qcCommit.Substring(0,8)))   HEAD $GitShort  `"$GitHeadSub`""
Info "engine patch $enginePatch (documentary: $headingCount headings in ENGINE_PATCHES.md)"

# =============================================================================
#  3.  GATES
# =============================================================================
Step 'Gates'
$Overrides = @()

# --- resolve the ship set now; two gates need it ----------------------------
$shipRel = [System.Collections.Generic.List[string]]::new()
foreach ($f in $ShipRootFiles) { $shipRel.Add($f) }
foreach ($f in $ShipGameFiles) { $shipRel.Add($f) }
foreach ($g in $ShipGlobs) {
    $dir = Join-Path $SurfDir ($g.Path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $dir)) { Fail "ship set names a directory that does not exist: $($g.Path)" }
    $deny = if ($g.ContainsKey('Deny')) { $g.Deny } else { @() }
    Get-ChildItem -LiteralPath $dir -File -Filter $g.Filter | ForEach-Object {
        $skip = $false
        foreach ($d in $deny) { if ($_.Name -like $d) { $skip = $true; break } }
        if (-not $skip) { $shipRel.Add("$($g.Path)/$($_.Name)") }
    }
}
foreach ($r in $shipRel) {
    if (-not (Test-Path -LiteralPath (Join-Path $SurfDir ($r -replace '/', '\')))) {
        Fail "ship set names a file that does not exist: $r"
    }
}
$shipSet = [System.Collections.Generic.HashSet[string]]::new([string[]]$shipRel, [System.StringComparer]::OrdinalIgnoreCase)
Info "ship set resolves to $($shipRel.Count) files"

# --- gate 1: dirty -----------------------------------------------------------
#  Scoped to the ship set on purpose. `git status --porcelain` is ~50 lines in
#  this tree and always will be -- most of it untracked cfg\test\ fixtures
#  that never ship. A blanket refusal would fail 100% of runs, -Force would
#  become reflexive, and the one line that matters would be buried in 50.
$dirtyShipping = @()
foreach ($line in (& git -C $SurfDir status --porcelain)) {
    if ($line.Length -lt 4) { continue }
    $p = $line.Substring(3).Trim()
    if ($p -match '\s->\s(.+)$') { $p = $Matches[1] }     # renames
    $p = $p.Trim('"')
    if ($shipSet.Contains($p)) { $dirtyShipping += $p }
}
if ($dirtyShipping.Count) {
    $msg = "uncommitted changes in $($dirtyShipping.Count) SHIPPING file(s):`n" + (($dirtyShipping | ForEach-Object { "      $_" }) -join "`n")
    if ($AllowDirty) { Warn "$msg`n    -> allowed by -AllowDirty"; $Overrides += 'AllowDirty' }
    else { Fail "$msg`n  Commit them, or re-run with -AllowDirty (recorded in the receipt)." }
} else { Good 'gate 1 (dirty): no shipping file is modified' }

# --- gate 2: stale progs -----------------------------------------------------
#  Per-target, not "newest file under src\ vs oldest .dat". A blanket check
#  would flag menu.dat stale because a server .qc changed; the operator reaches
#  for -AllowStale, and that one flag then blindfolds all three.
$staleReport = @()
foreach ($srcName in @('cl_progs.src', 'sv_progs.src', 'm_progs.src')) {
    $srcPath = Join-Path $SrcDir $srcName
    if (-not (Test-Path -LiteralPath $srcPath)) { Fail "missing $srcPath" }
    $lines = @(Get-Content -LiteralPath $srcPath | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('//') })
    if (-not $lines.Count) { Fail "$srcName has no content lines" }
    $datPath = Join-Path $SrcDir $lines[0]               # line 1 is the output path
    if (-not (Test-Path -LiteralPath $datPath)) { Fail "$srcName names an output that does not exist: $($lines[0])" }
    $dat = Get-Item -LiteralPath $datPath
    $newest = $null
    foreach ($qc in $lines[1..($lines.Count - 1)]) {
        $qp = Join-Path $SrcDir $qc
        if (-not (Test-Path -LiteralPath $qp)) { continue }
        $qi = Get-Item -LiteralPath $qp
        if ($null -eq $newest -or $qi.LastWriteTimeUtc -gt $newest.LastWriteTimeUtc) { $newest = $qi }
    }
    if ($newest -and $newest.LastWriteTimeUtc -gt $dat.LastWriteTimeUtc) {
        $staleReport += "$($dat.Name) ($($dat.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))) is older than $($newest.Name) ($($newest.LastWriteTime.ToString('yyyy-MM-dd HH:mm')))"
    }
}
if ($staleReport.Count) {
    $msg = "stale compiled progs:`n" + (($staleReport | ForEach-Object { "      $_" }) -join "`n")
    if ($AllowStale) { Warn "$msg`n    -> allowed by -AllowStale"; $Overrides += 'AllowStale' }
    else { Fail "$msg`n  Run .\src\build.ps1 (one pass rebuilds all three), then re-run." }
} else { Good 'gate 2 (stale): all three .dat are newer than their sources' }

# --- gate 3: engine skew -----------------------------------------------------
#  build.ps1:247-248 copies engine\release\{fteqw64.exe,fteplug_hl2_x64.dll} into
#  the install, so that pair is the definitional oracle for "what the engine tree
#  currently builds". Check BOTH: checking only the exe passes a DLL-only skew,
#  and it was the DLL-only direction that produced a split Patch 317 on this box.
$exeLocal = Join-Path $SurfDir 'ftesurf64.exe'
$dllLocal = Join-Path $SurfDir 'fteplug_hl2_x64.dll'
$exeBuilt = Join-Path $EngineRel 'fteqw64.exe'
$dllBuilt = Join-Path $EngineRel 'fteplug_hl2_x64.dll'
$hExeLocal = (Get-FileHash -LiteralPath $exeLocal -Algorithm SHA256).Hash
$hDllLocal = (Get-FileHash -LiteralPath $dllLocal -Algorithm SHA256).Hash
$hExeBuilt = $null; $hDllBuilt = $null; $skew = @()
if ((Test-Path -LiteralPath $exeBuilt) -and (Test-Path -LiteralPath $dllBuilt)) {
    $hExeBuilt = (Get-FileHash -LiteralPath $exeBuilt -Algorithm SHA256).Hash
    $hDllBuilt = (Get-FileHash -LiteralPath $dllBuilt -Algorithm SHA256).Hash
    if ($hExeLocal -ne $hExeBuilt) { $skew += "ftesurf64.exe        $($hExeLocal.Substring(0,12)) != engine\release  $($hExeBuilt.Substring(0,12))" }
    if ($hDllLocal -ne $hDllBuilt) { $skew += "fteplug_hl2_x64.dll  $($hDllLocal.Substring(0,12)) != engine\release  $($hDllBuilt.Substring(0,12))" }
} else {
    Warn "no engine\release\ build at $EngineRel -- cannot check engine skew"
}
$patchAppliesToBinary = ($skew.Count -eq 0 -and $null -ne $hExeBuilt)
if ($skew.Count) {
    $msg = "the installed engine is not what the engine tree builds:`n" + (($skew | ForEach-Object { "      $_" }) -join "`n")
    $msg += "`n      => `"engine patch $enginePatch`" would be a claim about ENGINE_PATCHES.md, not about this binary."
    if ($AllowEngineSkew) { Warn "$msg`n    -> allowed by -AllowEngineSkew; the receipt and page will say 'unverified'"; $Overrides += 'AllowEngineSkew' }
    else { Fail "$msg`n  Run .\src\build.ps1 -Engine to deploy the built pair, then re-run." }
} elseif ($patchAppliesToBinary) { Good 'gate 3 (skew): shipped exe and plugin match engine\release\' }

# ENGINE.txt is a source document about a code relationship, not a cache this
# script gets to rewrite. Report drift; never silently "fix" it.
$enginePin = Join-Path $SurfDir 'ENGINE.txt'
if (Test-Path -LiteralPath $enginePin) {
    $pinTxt = (Get-Content -LiteralPath $enginePin -TotalCount 40) -join "`n"
    if ($pinTxt -match '(?m)^\s*patch\s+(\d+)\s*$')   { $pp = [int]$Matches[1] } else { $pp = $null }
    if ($pinTxt -match '(?m)^\s*qcbuild\s+(\d+)\s*$') { $pq = [int]$Matches[1] } else { $pq = $null }
    if (($null -ne $pp -and $pp -ne $enginePatch) -or ($null -ne $pq -and $pq -ne $qcBuild)) {
        Warn "ENGINE.txt pin drift: says patch $pp / qcbuild $pq, measured $enginePatch / $qcBuild (not changed by this script)"
    }
}

# --- Linux gates (-Linux) -----------------------------------------------------
#  L1 the launcher is committed. L2 the drop is what BUILDINFO says, the build
#  passed its own gates, its stamp names BUILDINFO's commit and that commit's
#  engine code is the Windows exe's. L3 it needs only libraries every distro has.
#  Every problem is listed before failing; only the skew lines (hashes, stamp,
#  code) yield to -AllowEngineSkew.
if ($Linux) {
    $lxHard = @(); $lxSkew = @()
    $lxExe  = Join-Path $LinuxDrop 'fteqw64'
    $lxPlug = Join-Path $LinuxDrop 'fteplug_hl2_amd64.so'

    & git -C $SurfDir ls-files --error-unmatch -- ftesurf.sh 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { $lxHard += 'ftesurf.sh is not tracked by git (.gitignore needs !/ftesurf.sh)' }
    else {
        if ("$(& git -C $SurfDir ls-files -s -- ftesurf.sh)" -notmatch '^100755 ') { Warn 'ftesurf.sh is not mode 100755 in git (the archive sets 0755 regardless)' }
        if (& git -C $SurfDir status --porcelain -- ftesurf.sh) {
            if ($AllowDirty) { Warn 'ftesurf.sh has uncommitted changes -> allowed by -AllowDirty'; $Overrides += 'AllowDirty:linux' }
            else { $lxHard += 'ftesurf.sh has uncommitted changes (commit it, or -AllowDirty)' }
        }
    }

    foreach ($f in @($lxExe, $lxPlug)) { if (-not (Test-ElfX64 $f)) { $lxHard += "$(Split-Path -Leaf $f) is not an x86-64 ELF file" } }
    $lxHard += @(Test-ByteStrings $lxExe -MustHave $LinuxExeMustHave)
    $lxHard += @(Test-ByteStrings $lxPlug -MustNot $LinuxPluginMustNot)
    $hLxExe   = (Get-FileHash -LiteralPath $lxExe -Algorithm SHA256).Hash
    $hLxPlug  = (Get-FileHash -LiteralPath $lxPlug -Algorithm SHA256).Hash
    $lxBinRev = @(Get-BinaryRevisions $lxExe)
    $winRevs  = @(Get-BinaryRevisions $exeLocal)
    $lxPatch = 0; $lxCmpTo = $null; $lxPinEq = $null
    $bi = $null
    try { $bi = Read-LinuxBuildInfo (Join-Path $LinuxDrop 'BUILDINFO.txt') } catch { $lxHard += $_.Exception.Message }
    if ($bi) {
        if ($bi.Gates -cne 'all PASS') { $lxHard += "BUILDINFO gates: $($bi.Gates)" }
        foreach ($p in @(@('fteqw64', $hLxExe), @('fteplug_hl2_amd64.so', $hLxPlug))) {
            if ($bi.Sha256[$p[0]] -ne $p[1]) { $lxHard += "$($p[0]) sha256 $($p[1].Substring(0, 12)) != BUILDINFO $($bi.Sha256[$p[0]].Substring(0, 12))" }
        }
        & git -C $FteRoot cat-file -e "$($bi.Commit)^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) { $lxHard += "BUILDINFO commit $($bi.Commit) is not in $FteRoot" }
        else {
            # The stamp is make's (engine/Makefile), matched tolerantly: count + 29,
            # then any describe whose hash is a prefix of the commit, never -dirty.
            $lxCount = [int]"$(& git -C $FteRoot rev-list --count $bi.Commit)".Trim()
            $lxExpRev = "git-$($lxCount + 29)-...-g$($bi.Commit.Substring(0, 9))"
            if (-not $lxBinRev.Count -or @($lxBinRev | Where-Object { -not (Test-RevisionMatch $_ $lxCount $bi.Commit) }).Count) {
                $lxHard += "fteqw64 carries revision '$($lxBinRev -join ', ')', expected $lxExpRev"
            }
            if ($bi.Revision -and -not (Test-RevisionMatch $bi.Revision $lxCount $bi.Commit)) { $lxHard += "BUILDINFO revision $($bi.Revision) does not match $lxExpRev" }

            # The label comes from the commit's own changelog, never the working tree:
            # another session's claimed-but-uncommitted heading is not in this binary.
            $pm = Get-MaxPatchHeading ((& git -C $FteRoot show "$($bi.Commit):ENGINE_PATCHES.md") -join "`n")
            if ($pm.Count -lt 100) { $lxHard += "only $($pm.Count) patch headings in $($bi.Commit.Substring(0, 9)):ENGINE_PATCHES.md" }
            $lxPatch = $pm.Max

            $winHex = if ($winRevs.Count -eq 1 -and $winRevs[0] -cmatch '^git-\d+-(?:.+-g)?([0-9a-f]{7,40})$') { $Matches[1] } else { $null }
            $winSha = if ($winHex) { "$(& git -C $FteRoot rev-parse --verify --quiet "$winHex^{commit}" 2>$null)".Trim() } else { '' }
            if ($winSha) {
                $lxCmpTo = 'windows-exe-commit'
                $dargs = @('-C', $FteRoot, 'diff', '--quiet', $winSha, $bi.Commit, '--', 'engine', 'plugins')
            } else {
                $lxSkew += "ftesurf64.exe carries revision '$($winRevs -join ', ')', which names no clean commit in $FteRoot (compared with that tree's working copy instead)"
                $lxCmpTo = 'engine-worktree'
                $dargs = @('-C', $FteRoot, 'diff', '--quiet', $bi.Commit, '--', 'engine', 'plugins')
            }
            & git @dargs 2>$null
            $drc = $LASTEXITCODE
            if ($drc -eq 1) {
                $sargs = @($dargs); $sargs[3] = '--stat'
                $lxSkew += "engine code differs from ftesurf64.exe's ($lxCmpTo):"
                $lxSkew += @(& git @sargs | ForEach-Object { "  $_" })
            } elseif ($drc -ne 0) { $lxHard += "git $($dargs -join ' ') failed (exit $drc)" }

            if ((Test-Path -LiteralPath $enginePin) -and ((Get-Content -LiteralPath $enginePin -Raw) -match '(?m)^\s*commit\s+([0-9a-f]{40})\s*$')) {
                $lxPinEq = ($Matches[1] -eq $bi.Commit)
                if (-not $lxPinEq) { Warn "ENGINE.txt pins commit $($Matches[1].Substring(0, 9)); the Linux drop is $($bi.Commit.Substring(0, 9)) (not changed by this script)" }
            }
        }
    }

    $lxNeeded = [ordered]@{}; $lxGlibcs = @(); $lxHostGlibc = $null; $lxHostOs = $null
    foreach ($l in (Invoke-Wsl @('sh', $LinuxPackWsl, 'inspect', "$LinuxDropWsl/fteqw64", "$LinuxDropWsl/fteplug_hl2_amd64.so") 'linux-pack.sh inspect')) {
        if ($l -cmatch '^N (\S+) (\S+)$') { if (-not $lxNeeded.Contains($Matches[1])) { $lxNeeded[$Matches[1]] = @() }; $lxNeeded[$Matches[1]] += $Matches[2] }
        elseif ($l -cmatch '^G \S+ GLIBC_([0-9.]+)$') { $lxGlibcs += $Matches[1] }
        elseif ($l -cmatch '^HOST ([0-9.]+)$') { $lxHostGlibc = $Matches[1] }
        elseif ($l -cmatch '^OS (.+)$') { $lxHostOs = $Matches[1] }
    }
    foreach ($f in $lxNeeded.Keys) {
        $extra = @($lxNeeded[$f] | Where-Object { $LinuxNeededAllow -notcontains $_ })
        if ($extra.Count) { $lxHard += "$f needs $($extra -join ', ') (not in -LinuxNeededAllow)" }
    }
    $lxGlibc = if ($lxGlibcs.Count) { Get-MaxVersion $lxGlibcs } else { $null }
    if (-not $lxGlibc -or -not $lxHostGlibc) { $lxHard += 'linux-pack.sh inspect reported no GLIBC versions or no host glibc' }
    elseif ([version]$lxGlibc -gt [version]$lxHostGlibc) {
        $lxHard += "the drop needs glibc $lxGlibc and $LinuxDistro has $lxHostGlibc, so it has never run where it was tested"
    }

    $lxVerified = ($lxSkew.Count -eq 0)
    $lxLabel = if ($lxVerified) { "$lxPatch" } else { "$lxPatch (unverified against this binary)" }
    if ($lxHard.Count -or $lxSkew.Count) {
        $msg = "the Linux drop fails its gates ($LinuxDrop):"
        if ($lxHard.Count) { $msg += "`n" + (($lxHard | ForEach-Object { "      $_" }) -join "`n") }
        if ($lxSkew.Count) { $msg += "`n    skew (-AllowEngineSkew):`n" + (($lxSkew | ForEach-Object { "      $_" }) -join "`n") }
        if ($lxHard.Count -or -not $AllowEngineSkew) { Fail "$msg`n  Rebuild with tools\linux\build.sh (BUILDINFO must say 'gates all PASS'), then re-run." }
        Warn "$msg`n    -> skew allowed by -AllowEngineSkew; the receipt and page will say 'unverified'"
        $Overrides += 'AllowEngineSkew:linux'
    } else {
        Good "Linux gates: drop = BUILDINFO ($($bi.Commit.Substring(0, 9)), gates all PASS), stamp $($lxBinRev[0]), code = ftesurf64.exe's, glibc $lxGlibc <= $lxHostGlibc"
    }
}

# =============================================================================
#  4.  STAGE
# =============================================================================
Step 'Stage'
$StageDir = Join-Path $StageRoot "stage-$Ver"
# The marker lives BESIDE the stage, never inside it. Inside, it would have to
# be deleted before packing (nothing is excluded from the pack by design) -- and
# then the next run could not recognise its own directory and would refuse to
# clean it, which is exactly the deadlock this comment exists to prevent.
$Marker   = Join-Path $StageRoot ".stage-$Ver.owned"
# The parent of this delete is the live 5.7 GB install. Only ever remove a
# directory this script created, proven by its own marker file AND by the shape
# of the path -- so a mistyped path can never turn the recursive delete loose.
if (Test-Path -LiteralPath $StageDir) {
    if ((Test-Path -LiteralPath $Marker) -and ($StageDir -match '[\\/]release[\\/]stage-\d')) {
        Remove-Item -LiteralPath $StageDir -Recurse -Force
    } else {
        Fail "$StageDir exists but is not a stage directory this script made (no $Marker beside it). Refusing to delete it."
    }
}
if (-not (Test-Path -LiteralPath $StageRoot)) { New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null }
New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
Set-Content -LiteralPath $Marker -Value "ftesurf release stage $Ver" -NoNewline

$staged = 0; $stagedBytes = 0L
foreach ($rel in $shipRel) {
    $srcFile = Join-Path $SurfDir ($rel -replace '/', '\')
    $dstFile = Join-Path $StageDir ($rel -replace '/', '\')
    $dstDir  = Split-Path -Parent $dstFile
    if (-not (Test-Path -LiteralPath $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
    Copy-Item -LiteralPath $srcFile -Destination $dstFile -Force
    $staged++; $stagedBytes += (Get-Item -LiteralPath $dstFile).Length
}

# Normalise the launchers to CRLF in the STAGE (never in the working tree).
#
# .gitattributes declares `*.bat text eol=crlf`, so a fresh clone gets CRLF --
# but git will not fix a working-tree copy that is already LF: it normalises on
# add, LF normalises to LF, and `git status` stays clean. Both launchers in this
# tree are LF-only for that reason, so the archive would ship whatever this one
# machine happens to hold rather than what the repository declares.
#
# Measured on Windows 11 build 26100: cmd.exe runs the LF launcher correctly --
# multi-line if/else, goto, and nested for/if all behave -- so this is not a
# live break, and the .gitattributes warning does not reproduce here. It is
# removing a "works on mine" dependency from the shipped artifact, which is the
# reason that attribute exists at all.
foreach ($b in @(Get-ChildItem -LiteralPath $StageDir -Filter '*.bat' -File -Recurse)) {
    $t = [System.IO.File]::ReadAllText($b.FullName) -replace "`r`n", "`n" -replace "`n", "`r`n"
    [System.IO.File]::WriteAllText($b.FullName, $t, (New-Object System.Text.ASCIIEncoding))
}

# =============================================================================
#  SHIP fs_addons.txt, GENERATED FROM THE .default MASTER.
#
#  The engine reads <gamedir>/fs_addons.txt and NOTHING ELSE -- fs.c:9206-9209,
#  `#define FS_ADDONS_FILE "fs_addons.txt"`, remounted on every searchpath
#  rebuild. It never reads fs_addons.default.txt; that file is this repository's
#  annotated master and ftesurf.bat seeds from it on first run.
#
#  So a player who double-clicks ftesurf64.exe instead of ftesurf.bat -- which is
#  the obvious thing to do, the .exe being the file that looks like the game --
#  boots with NO addon list at all: no Momentum map library, no CS:S materials,
#  no HL2 base content, and a map browser that is simply empty. Shipping the file
#  the engine actually reads removes that dependency entirely.
#
#  GENERATED FROM .default, not copied from the working tree, on purpose. The
#  tree's own fs_addons.txt is mutable state: `fs_load C:\somewhere` makes the
#  engine append that absolute path to it, so copying it would eventually publish
#  the release machine's drive layout, and would hard-code one drive letter into
#  every player's install. The two files' mount lines are byte-identical today
#  (three portable `steam:` specs); this guarantees they stay that way.
$addonsDefault = Join-Path $StageDir 'ftesurf\fs_addons.default.txt'
$addonsLive    = Join-Path $StageDir 'ftesurf\fs_addons.txt'
if (-not (Test-Path -LiteralPath $addonsDefault)) { Fail 'ftesurf/fs_addons.default.txt is not in the ship set; cannot generate fs_addons.txt from it' }
Copy-Item -LiteralPath $addonsDefault -Destination $addonsLive -Force
$staged++

# An absolute path here is the failure this generation exists to prevent, so
# assert it rather than trusting the source. Drive letters and UNC both.
$absLines = @(Get-Content -LiteralPath $addonsLive |
    Where-Object { $_.Trim() -and -not $_.Trim().StartsWith('//') } |
    Where-Object { $_ -match '^\s*([A-Za-z]:[\\/]|\\\\)' })
if ($absLines.Count) {
    Fail ("fs_addons.txt would ship absolute path(s), which name one machine's drives:`n" +
        (($absLines | ForEach-Object { "      $_" }) -join "`n") +
        "`n  Fix ftesurf/fs_addons.default.txt to use portable `steam:Game/dir` specs.")
}

# Generated companions. README.md deliberately does NOT ship: it is a
# build-from-source document that opens by telling the reader to compile an
# engine, which is the wrong first instruction for someone who just downloaded
# a binary.
$nowUtc = [DateTime]::UtcNow
$stamp  = $nowUtc.ToString('yyyy-MM-dd HH:mm:ss') + ' UTC'
$engineLabel = if ($patchAppliesToBinary) { "$enginePatch" } else { "$enginePatch (unverified against this binary)" }

[System.IO.File]::WriteAllText((Join-Path $StageDir 'VERSION.txt'), @"
FTESurf $Ver
built            $stamp
QuakeC build     $qcBuild
engine patch     $engineLabel
git HEAD         $GitShort  $GitHeadSub
ftesurf64.exe        sha256 $hExeLocal
fteplug_hl2_x64.dll  sha256 $hDllLocal
csprogs.dat          sha256 $((Get-FileHash -LiteralPath (Join-Path $SurfDir 'ftesurf\csprogs.dat') -Algorithm SHA256).Hash)
qwprogs.dat          sha256 $((Get-FileHash -LiteralPath (Join-Path $SurfDir 'ftesurf\qwprogs.dat') -Algorithm SHA256).Hash)
menu.dat             sha256 $((Get-FileHash -LiteralPath (Join-Path $SurfDir 'ftesurf\menu.dat') -Algorithm SHA256).Hash)

This file cannot contain the archive's own SHA-256 -- it is inside it.
That hash is published beside the download, and in ftesurf-$Ver.json.
"@.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding $false))

[System.IO.File]::WriteAllText((Join-Path $StageDir 'INSTALL.txt'), @"
FTESurf $Ver -- install
=======================

Upgrading from 0.1.9 or earlier: delete ftesurf\ftesurf.cfg once, after
extracting and before you start the game.  Earlier builds ran Momentum Mod's
own config at every start and saved its binds into that file (R stopped
restarting your run).  This build no longer runs it, but the saved binds stay
until the file is gone.  Deleting it also resets your own settings, so note
your sensitivity first.  A fresh install has no ftesurf.cfg.

1.  Extract this archive into a folder of its own.  There is no installer and
    nothing is written outside that folder.

2.  Install these from Steam if you do not have them.  FTESurf ships NO Valve
    or Momentum content -- it reads your own installs at runtime, so without
    them the map browser is empty:

        Momentum Mod Playtest     the map library (1,308 maps)
        Counter-Strike: Source    materials and models most surf maps use
        Half-Life 2               shared Source content, skyboxes, dev textures

    Optional, mounted per map and only when a map needs them:
        Counter-Strike: Global Offensive (legacy Source 1 branch), Team Fortress 2

3.  Run ftesurf.bat.  The engine takes its game folder from the working
    directory rather than from the .exe's location, and the .bat sets it -- so
    a shortcut pointing straight at ftesurf64.exe from somewhere else stops at
    a mod list.  The mounts above are already configured in ftesurf/fs_addons.txt
    and need no first-run step.

4.  If a Steam game is not found, type  fs_steamlibs  in the console.  It prints
    where the engine looked and how each mount resolved.  To add a library:

        fs_steamlibs add D:\SteamLibrary
        fs_restart

Windows x64 only.  The build is not code-signed, so SmartScreen will warn on
first run.  This is alpha software: physics fixes between builds can invalidate
previously recorded run times.

Licence: GPLv2 or later, see LICENSE.  The three fonts in ftesurf/gfx/fonts are
SIL OFL 1.1, see ftesurf/gfx/fonts/FONTS.md.
"@.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding $false))

[System.IO.File]::WriteAllText((Join-Path $StageDir 'SOURCE.txt'), @"
FTESurf $Ver -- source
======================

FTESurf is GPLv2 or later.  See LICENSE for the full text.

  game (QuakeC)   https://github.com/ProtoAus/ftesurf
  engine fork     https://github.com/ProtoAus/ftequakers   branch engine-patches

This release was built from:
  QuakeC build $qcBuild, git $GitShort
  engine patch $engineLabel

Stock FTEQW will not run this game: the Source movement module
(engine/common/pm_source.c) and the hl2 plugin's .phy collision, VTF/VMT
material and static-prop lighting work exist only in that fork.

FTESurf contains no Valve or Momentum Mod code and ships no Source assets.
"@.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding $false))

$staged += 3
$stagedBytes = (Get-ChildItem -LiteralPath $StageDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
Good "staged $staged files, $(HumanSize $stagedBytes)"

# =============================================================================
#  5.  DENY TRIPWIRE (over the materialised stage)
# =============================================================================
Step 'Deny tripwire'
$stageFiles = Get-ChildItem -LiteralPath $StageDir -Recurse -File
$prefixLen  = $StageDir.Length + 1
$stageRel   = @($stageFiles | ForEach-Object { $_.FullName.Substring($prefixLen).Replace('\', '/') })

function Test-Deny ([string[]]$paths, [string]$where, [string[]]$extra = @()) {
    $hits = @()
    foreach ($p in $paths) {
        foreach ($rx in @($DenyPatterns) + @($extra)) {
            if ($p -match $rx) { $hits += "$p   (matched /$rx/)"; break }
        }
    }
    if ($hits.Count) {
        Fail ("DENY TRIPWIRE tripped in $where -- refusing to publish:`n" + (($hits | ForEach-Object { "      $_" }) -join "`n"))
    }
}
Test-Deny $stageRel 'the stage'

$big = $stageFiles | Where-Object { $_.Length -gt ($MaxFileMB * 1MB) }
if ($big) {
    Fail ("file(s) over ${MaxFileMB} MB in the stage -- check the ship set, then raise -MaxFileMB if intended:`n" +
        (($big | ForEach-Object { "      $($_.FullName.Substring($prefixLen)) $(HumanSize $_.Length)" }) -join "`n"))
}
if ($stagedBytes -gt ($MaxTotalMB * 1MB)) {
    Fail "stage is $(HumanSize $stagedBytes), over the ${MaxTotalMB} MB ceiling. Check the ship set, then raise -MaxTotalMB if intended."
}
Good "no denied path in $($stageRel.Count) staged files; largest $(HumanSize (($stageFiles | Measure-Object Length -Maximum).Maximum))"

# =============================================================================
#  6.  PACK
# =============================================================================
Step 'Pack'
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# THIS LINE IS LOAD-BEARING, and must stay immediately before the pack.
# `7z a` against an EXISTING archive is an UPDATE, not a replace: every entry
# the new file set does not name is carried forward. Since the archive name only
# moves on -Bump, every re-run at the same version targets the same file -- so a
# file removed from the ship set for a good reason (consent.txt, the dev's
# ftesurf.cfg) would survive in every later archive built to that name. `7z t`
# is CRC-only and passes on the result; the sha256 and Content-Length checks
# further down are computed FROM the archive and would confirm it too.
Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction SilentlyContinue

Push-Location $StageDir
try {
    # -mx=9 reproduces the reference archive's LZMA2:48m + BCJ2, Solid=+ : the
    # 48m is 7-Zip clamping its dictionary to the payload, and BCJ2 is applied
    # automatically to the two PE files in their own solid block. Do NOT
    # hand-roll the BCJ2 chain -- that forces it over 29 MB of already-compressed
    # PNG for nothing. -ms/-mmt are pinned so a future 7-Zip default cannot move
    # them underneath us. No -i!/-x! patterns anywhere: the whole point of the
    # stage is that the thing being packed is already exactly the ship set.
    Native $SevenZip @('a', '-t7z', '-mx=9', '-ms=on', '-mmt=on', '-bso0', '-bsp0', $ArchivePath, '.\*') '7z a' | Out-Null
} finally { Pop-Location }
if (-not (Test-Path -LiteralPath $ArchivePath)) { Fail '7z reported success but produced no archive' }
$ArchiveItem  = Get-Item -LiteralPath $ArchivePath
$ArchiveBytes = $ArchiveItem.Length
$ArchiveSha   = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash
$ArchiveMd5   = (Get-FileHash -LiteralPath $ArchivePath -Algorithm MD5).Hash.ToLower()
Good "$ArchiveName  $(HumanSize $ArchiveBytes)  ($('{0:N1}' -f (100 * $ArchiveBytes / $stagedBytes))% of raw)"

# =============================================================================
#  7.  VERIFY THE ARCHIVE AGAINST THE STAGE
#
#  The only check in this whole pipeline that looks at the bytes that actually
#  ship. Everything downstream (sha256, Content-Length, the page) is computed
#  FROM this archive and will happily agree with a polluted one.
# =============================================================================
Step 'Verify archive contents'
$inArchive = @()
$slt = Native $SevenZip @('l', '-ba', '-slt', $ArchivePath) '7z l'
$curPath = $null
foreach ($line in $slt) {
    $s = [string]$line
    if ($s.StartsWith('Path = ')) { $curPath = $s.Substring(7) }
    elseif ($s.StartsWith('Attributes = ') -and $curPath) {
        # -slt lists directory entries too; keep files only or the comparison
        # fires spuriously on its very first run.
        if ($s -notmatch 'D') { $inArchive += $curPath.Replace('\', '/') }
        $curPath = $null
    }
}
Test-Deny $inArchive 'the packed archive'
$setA = [System.Collections.Generic.HashSet[string]]::new([string[]]$inArchive, [System.StringComparer]::OrdinalIgnoreCase)
$setS = [System.Collections.Generic.HashSet[string]]::new([string[]]$stageRel,  [System.StringComparer]::OrdinalIgnoreCase)
$onlyArchive = @($inArchive | Where-Object { -not $setS.Contains($_) })
$onlyStage   = @($stageRel  | Where-Object { -not $setA.Contains($_) })
if ($onlyArchive.Count -or $onlyStage.Count) {
    $m = 'archive does not match the stage:'
    if ($onlyArchive.Count) { $m += "`n    in archive but NOT staged (stale entries from an earlier pack?):`n" + (($onlyArchive | ForEach-Object { "      $_" }) -join "`n") }
    if ($onlyStage.Count)   { $m += "`n    staged but NOT in archive:`n" + (($onlyStage | ForEach-Object { "      $_" }) -join "`n") }
    Fail $m
}
foreach ($must in @('ftesurf64.exe', 'fteplug_hl2_x64.dll', 'default.fmf', 'ftesurf.bat', 'LICENSE',
        'ftesurf/csprogs.dat', 'ftesurf/qwprogs.dat', 'ftesurf/menu.dat',
        'ftesurf/fs_addons.default.txt', 'ftesurf/cfg/default.cfg')) {
    if (-not $setA.Contains($must)) { Fail "archive is missing a required file: $must" }
}
Good "$($inArchive.Count) entries, identical to the stage, all required files present"

# =============================================================================
#  7b. -Linux: STAGE, PACK AND VERIFY THE tar.xz
#
#  Packed in WSL by linux-pack.sh: drvfs reports every file as 777, so modes are
#  set on an ext4 copy, owner 0/0. Its listing and an extraction come back here
#  and are compared with the stage, so the chain BUILDINFO -> drop -> stage ->
#  archive entry is checked hash by hash.
# =============================================================================
if ($Linux) {
    Step 'Linux: stage'
    $LxStageRoot = Join-Path $StageRoot "stage-linux-$Ver"
    $LxMarker    = Join-Path $StageRoot ".stage-linux-$Ver.owned"
    if (Test-Path -LiteralPath $LxStageRoot) {
        if ((Test-Path -LiteralPath $LxMarker) -and ($LxStageRoot -match '[\\/]release[\\/]stage-linux-\d')) {
            Remove-Item -LiteralPath $LxStageRoot -Recurse -Force
        } else {
            Fail "$LxStageRoot exists but is not a stage directory this script made (no $LxMarker beside it). Refusing to delete it."
        }
    }
    $LxTree = Join-Path $LxStageRoot $LinuxTop
    New-Item -ItemType Directory -Path $LxTree -Force | Out-Null
    Set-Content -LiteralPath $LxMarker -Value "ftesurf linux release stage $Ver" -NoNewline

    Copy-Item -LiteralPath (Join-Path $StageDir 'ftesurf') -Destination $LxTree -Recurse
    foreach ($f in @('default.fmf', 'LICENSE')) { Copy-Item -LiteralPath (Join-Path $StageDir $f) -Destination $LxTree }
    # SOURCE.txt names the engine patch; the Linux binary's comes from its own commit.
    $lxSrc = [System.IO.File]::ReadAllText((Join-Path $StageDir 'SOURCE.txt'))
    $lxSrcLine = "  engine patch $lxLabel (Linux engine $($bi.Commit.Substring(0, 9)))"
    $lxSrc = [regex]::Replace($lxSrc, '(?m)^  engine patch .*$', $lxSrcLine.Replace('$', '$$'))
    if (-not $lxSrc.Contains($lxSrcLine)) { Fail 'Linux SOURCE.txt: no engine patch line to replace' }
    [System.IO.File]::WriteAllText((Join-Path $LxTree 'SOURCE.txt'), $lxSrc, (New-Object System.Text.UTF8Encoding $false))
    Copy-Item -LiteralPath $lxExe  -Destination (Join-Path $LxTree 'ftesurf64')
    Copy-Item -LiteralPath $lxPlug -Destination (Join-Path $LxTree 'fteplug_hl2_amd64.so')
    # A CR after the shebang is "bad interpreter: /bin/sh^M".
    $sh = [System.IO.File]::ReadAllText((Join-Path $SurfDir 'ftesurf.sh')).Replace("`r`n", "`n")
    if (-not $sh.StartsWith('#!') -or $sh.Contains("`r")) { Fail 'ftesurf.sh must start with #! and contain no CR' }
    [System.IO.File]::WriteAllText((Join-Path $LxTree 'ftesurf.sh'), $sh, (New-Object System.Text.UTF8Encoding $false))
    foreach ($p in @(@('ftesurf64', $hLxExe), @('fteplug_hl2_amd64.so', $hLxPlug))) {
        if ((Get-FileHash -LiteralPath (Join-Path $LxTree $p[0]) -Algorithm SHA256).Hash -ne $p[1]) { Fail "staged $($p[0]) does not hash to the drop's" }
    }
    $lxDat = @{}
    foreach ($d in @('csprogs.dat', 'qwprogs.dat', 'menu.dat')) { $lxDat[$d] = (Get-FileHash -LiteralPath (Join-Path $LxTree "ftesurf\$d") -Algorithm SHA256).Hash }

    [System.IO.File]::WriteAllText((Join-Path $LxTree 'VERSION.txt'), @"
FTESurf $Ver for Linux x86_64 (beta)
built            $stamp
QuakeC build     $qcBuild
engine patch     $lxLabel
engine commit    $($bi.Commit)
engine revision  $($lxBinRev -join ' ')
engine built     $($bi.Built)  $($bi.Builder)  $($bi.Cc)
glibc needed     $lxGlibc or newer
git HEAD         $GitShort  $GitHeadSub
ftesurf64             sha256 $hLxExe
fteplug_hl2_amd64.so  sha256 $hLxPlug
csprogs.dat           sha256 $($lxDat['csprogs.dat'])
qwprogs.dat           sha256 $($lxDat['qwprogs.dat'])
menu.dat              sha256 $($lxDat['menu.dat'])

This file cannot contain the archive's own SHA-256 -- it is inside it.
That hash is published beside the download, and in ftesurf-$Ver.json.
"@.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding $false))

    [System.IO.File]::WriteAllText((Join-Path $LxTree 'INSTALL.txt'), @"
FTESurf $Ver for Linux (beta) -- install
========================================

This is the first Linux build.  It is a BETA, tested only under WSL2 on
Windows (WSLg) -- not yet on a native Linux desktop.  Runs on Linux are NOT
ranked during the beta: the leaderboard cannot yet tell injected input from a
real mouse there, so every Linux run is marked unverified.  Report problems on
Discord, in the FTESurf channel:
    https://discord.com/channels/471331861839216643/1327302504823787541

Needs: 64-bit x86 Linux with glibc $lxGlibc or newer (ldd --version shows
yours), OpenGL, and an X11 or Wayland desktop.

1.  Extract it somewhere you own:   tar xf $LinuxArchiveName
    This makes a folder called FTESurf.  Everything the game saves --
    settings, runs, screenshots, logs -- goes INSIDE that folder, so it must
    be writable: your home folder works, /opt and /usr do not.  To upgrade,
    extract a newer archive in the same place; your settings and runs stay.

2.  Install these from Steam if you do not have them.  FTESurf ships NO Valve
    or Momentum content -- it reads your own installs at runtime:
        Momentum Mod Playtest     the map library (1,308 maps)
        Counter-Strike: Source    materials and models most surf maps use
        Half-Life 2               shared Source content, skyboxes, dev textures
    Momentum Mod Playtest has no Linux version on Steam.  Install it anyway
    with Steam Play: right-click it > Properties > Compatibility, tick "Force
    the use of a specific Steam Play compatibility tool", pick a Proton
    version, then install.  FTESurf only reads its maps; you never start it.
    Optional, mounted per map only when needed: CS:GO (legacy), TF2.

3.  Run  ./ftesurf.sh  (or  ./ftesurf.sh <mapname>).  It changes to its own
    folder first, so a launcher or symlink pointing at it works from anywhere.
    Starting ftesurf64 directly from another folder stops at a mod list.

4.  If a Steam game is not found, type  fs_steamlibs  in the console: it
    prints where the engine looked and how each mount resolved.  Native,
    Flatpak and Snap Steam are found on their own.  For a library on another
    drive, add the folder that contains steamapps:
        fs_steamlibs add /mnt/games/SteamLibrary
        fs_restart

If it crashes: ftesurf.sh keeps the engine's error output in stderr.log, and a
crash writes crash.log -- both in the FTESurf folder.  Post both on the Discord
channel above, with what you were doing.  ./ftesurf.sh --debug also writes
ftesurf/logs/qconsole.log.

Alpha software: physics fixes between builds can invalidate recorded times.
Licence: GPLv2 or later, see LICENSE.  The three fonts in ftesurf/gfx/fonts are
SIL OFL 1.1, see ftesurf/gfx/fonts/FONTS.md.
"@.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding $false))

    $lxFiles = @(Get-ChildItem -LiteralPath $LxTree -Recurse -File)
    $lxRel   = @($lxFiles | ForEach-Object { $_.FullName.Substring($LxTree.Length + 1).Replace('\', '/') })
    $odd     = @($lxRel | Where-Object { $_ -cmatch '[^\x20-\x7E]' })
    if ($odd.Count) { Fail ("non-ASCII path(s) in the Linux stage:`n" + (($odd | ForEach-Object { "      $_" }) -join "`n")) }
    $lxStage = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
    foreach ($f in $lxFiles) { $lxStage[$f.FullName.Substring($LxTree.Length + 1).Replace('\', '/')] = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower() }
    $lxBytes = [long]($lxFiles | Measure-Object -Property Length -Sum).Sum
    Good "staged $($lxFiles.Count) files, $(HumanSize $lxBytes), in $LxTree"

    Step 'Linux: deny tripwire'
    Test-Deny $lxRel 'the Linux stage' $LinuxDeny
    $big = @($lxFiles | Where-Object { $_.Length -gt ($MaxFileMB * 1MB) })
    if ($big.Count) { Fail ("file(s) over ${MaxFileMB} MB in the Linux stage:`n" + (($big | ForEach-Object { "      $($_.Name) $(HumanSize $_.Length)" }) -join "`n")) }
    if ($lxBytes -gt ($MaxTotalMB * 1MB)) { Fail "the Linux stage is $(HumanSize $lxBytes), over the ${MaxTotalMB} MB ceiling." }
    Good "no denied path in $($lxRel.Count) staged files"

    Step 'Linux: pack (WSL)'
    Remove-Item -LiteralPath $LinuxArchivePath -Force -ErrorAction SilentlyContinue   # never ship a previous pack
    $LxOutWsl = "$(WslPath $OutDir)/$LinuxArchiveName"
    Invoke-Wsl (@('sh', $LinuxPackWsl, 'pack', (WslPath $LxStageRoot), $LinuxTop, $LxOutWsl) + $LinuxExec) 'linux-pack.sh pack' | Out-Null
    if (-not (Test-Path -LiteralPath $LinuxArchivePath)) { Fail 'linux-pack.sh reported success but produced no archive' }
    $LinuxArchiveBytes = (Get-Item -LiteralPath $LinuxArchivePath).Length
    $LinuxArchiveSha   = (Get-FileHash -LiteralPath $LinuxArchivePath -Algorithm SHA256).Hash
    $LinuxArchiveMd5   = (Get-FileHash -LiteralPath $LinuxArchivePath -Algorithm MD5).Hash.ToLower()
    Good "$LinuxArchiveName  $(HumanSize $LinuxArchiveBytes)  ($('{0:N1}' -f (100 * $LinuxArchiveBytes / $lxBytes))% of raw)"

    Step 'Linux: verify archive contents'
    $vr = @(Invoke-Wsl @('sh', $LinuxPackWsl, 'verify', $LxOutWsl, $LinuxTop) 'linux-pack.sh verify')
    if ($vr -cnotcontains 'VERIFIED') { Fail "linux-pack.sh verify did not finish:`n$($vr -join "`n")" }
    $lxEntries = @(ConvertFrom-TarListing @($vr | Where-Object { $_.StartsWith('T ') } | ForEach-Object { $_.Substring(2) }))
    $lxHashes  = ConvertFrom-ShaLines @($vr | Where-Object { $_.StartsWith('H ') } | ForEach-Object { $_.Substring(2) })
    $prob = @(Test-LinuxArchiveEntries $lxEntries $lxHashes $lxStage $LinuxTop $LinuxExec)
    # Relative to FTESurf/: the anchored ^ftesurf/ftesurf\.cfg$ would miss FTESurf/ftesurf/ftesurf.cfg.
    $arcRel = @($lxEntries | Where-Object { $_.Type -eq '-' -and $_.Path.StartsWith("$LinuxTop/") } | ForEach-Object { $_.Path.Substring($LinuxTop.Length + 1) })
    Test-Deny $arcRel 'the packed Linux archive' $LinuxDeny
    foreach ($must in $LinuxRequired) { if ($arcRel -cnotcontains $must) { $prob += "missing required file $LinuxTop/$must" } }
    foreach ($l in @($vr | Where-Object { $_.StartsWith('L ') })) { $prob += "ldd: $($l.Substring(2))" }
    if ($prob.Count) { Fail ("the Linux archive does not match its stage:`n" + (($prob | ForEach-Object { "      $_" }) -join "`n")) }
    Good "$($arcRel.Count) files: owner 0/0, 0755 only $($LinuxExec -join ' and '), sha256 = stage, ldd resolves both binaries"
}

# =============================================================================
#  8.  RECEIPT
# =============================================================================
Step 'Receipt'
function FileSha ($rel) { (Get-FileHash -LiteralPath (Join-Path $SurfDir $rel) -Algorithm SHA256).Hash }
$receipt = [ordered]@{
    version      = $Ver
    version_full = "$Ver+b$qcBuild.p$enginePatch"
    built_utc    = $nowUtc.ToString('yyyy-MM-ddTHH:mm:ssZ')
    archive      = [ordered]@{ name = $ArchiveName; bytes = $ArchiveBytes; sha256 = $ArchiveSha; md5 = $ArchiveMd5; url = $ArchiveUrl }
    qc           = [ordered]@{ build = $qcBuild; build_commit = $qcCommit; head = $GitHead; head_subject = $GitHeadSub; dirty_shipping = $dirtyShipping }
    engine       = [ordered]@{
        patch_doc                = $enginePatch
        patch_applies_to_binary  = $patchAppliesToBinary
        exe_sha256               = $hExeLocal
        dll_sha256               = $hDllLocal
        release_exe_sha256       = $hExeBuilt
        release_dll_sha256       = $hDllBuilt
    }
    content      = [ordered]@{
        file_count = $inArchive.Count
        # Measure-Object -Sum returns a Double; without the cast the receipt
        # records a byte count as 44096929.0, which reads as an estimate.
        raw_bytes  = [long]$stagedBytes
        hashes     = [ordered]@{
            'ftesurf64.exe'        = $hExeLocal
            'fteplug_hl2_x64.dll'  = $hDllLocal
            'ftesurf/csprogs.dat'  = (FileSha 'ftesurf\csprogs.dat')
            'ftesurf/qwprogs.dat'  = (FileSha 'ftesurf\qwprogs.dat')
            'ftesurf/menu.dat'     = (FileSha 'ftesurf\menu.dat')
        }
    }
    overrides    = $Overrides
    tool         = [ordered]@{ script = 'src/release/release.ps1'; host = $env:COMPUTERNAME }
}
if ($Linux) {
    # Appended, so every existing key keeps its place.
    $receipt['linux'] = [ordered]@{
        archive   = [ordered]@{ name = $LinuxArchiveName; bytes = $LinuxArchiveBytes; sha256 = $LinuxArchiveSha; md5 = $LinuxArchiveMd5; url = $LinuxArchiveUrl }
        platform  = 'linux-x86_64'
        beta      = $true
        glibc_min = $lxGlibc
        needed    = @($lxNeeded.Values | ForEach-Object { $_ } | Sort-Object -Unique)
        packed_on = "$lxHostOs (WSL $LinuxDistro)"
        engine    = [ordered]@{
            patch_doc            = $lxPatch
            binary_verified      = $lxVerified
            commit               = $bi.Commit
            revision             = ($lxBinRev -join ' ')
            gates                = $bi.Gates
            builder              = $bi.Builder
            cc                   = $bi.Cc
            built_utc            = $bi.Built
            code_compared_to     = $lxCmpTo
            windows_exe_revision = ($winRevs -join ' ')
            code_matches_pin     = $lxPinEq
            exe_sha256           = $hLxExe
            plugin_sha256        = $hLxPlug
        }
        content   = [ordered]@{
            file_count = $arcRel.Count
            raw_bytes  = $lxBytes
            hashes     = [ordered]@{
                'ftesurf64'            = $hLxExe
                'fteplug_hl2_amd64.so' = $hLxPlug
                'ftesurf.sh'           = $lxStage['ftesurf.sh'].ToUpper()
                'ftesurf/csprogs.dat'  = $lxDat['csprogs.dat']
                'ftesurf/qwprogs.dat'  = $lxDat['qwprogs.dat']
                'ftesurf/menu.dat'     = $lxDat['menu.dat']
            }
        }
    }
}
$ReceiptPath = Join-Path $OutDir "ftesurf-$Ver.json"
$json = ($receipt | ConvertTo-Json -Depth 8).Replace("`r`n", "`n")
[System.IO.File]::WriteAllText($ReceiptPath, $json + "`n", (New-Object System.Text.UTF8Encoding $false))
[System.IO.File]::WriteAllText((Join-Path $OutDir 'ftesurf-latest.json'), $json + "`n", (New-Object System.Text.UTF8Encoding $false))
[System.IO.File]::WriteAllText("$ArchivePath.sha256", "$($ArchiveSha.ToLower())  $ArchiveName`n", (New-Object System.Text.UTF8Encoding $false))
if ($Linux) { [System.IO.File]::WriteAllText("$LinuxArchivePath.sha256", "$($LinuxArchiveSha.ToLower())  $LinuxArchiveName`n", (New-Object System.Text.UTF8Encoding $false)) }
Good "wrote $ReceiptPath"

# --- render the page (runs in -DryRun too: it exercises the token asserts) ---
if (-not $SkipSite) {
    Step 'Render the page'
    $tpl = Join-Path $RelDir 'page.template.html'
    if (-not (Test-Path -LiteralPath $tpl)) { Fail "missing $tpl" }
    # <!--LINUX-BEGIN/END--> blocks render only with -Linux; without it the page
    # is byte-identical to the template before they existed.
    try { $pb = Split-PageBlocks (Get-Content -LiteralPath $tpl -Raw) } catch { Fail "$tpl`: $($_.Exception.Message)" }
    $html = if ($Linux) { $pb.Kept } else { $pb.Outside }

    function HtmlEsc ([string]$s) {
        $s.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;').Replace('"', '&quot;').Replace("'", '&#39;')
    }
    $tokens = [ordered]@{
        'VERSION'      = $Ver
        'FILENAME'     = $ArchiveName
        'URL'          = $ArchiveUrl
        'SIZE_HUMAN'   = (HumanSize $ArchiveBytes)
        'SIZE_BYTES'   = ('{0:N0}' -f $ArchiveBytes)
        'SHA256'       = $ArchiveSha.ToUpper()
        'DATE'         = $nowUtc.ToString('d MMMM yyyy')
        'QCBUILD'      = "$qcBuild"
        'ENGINEPATCH'  = $engineLabel
    }
    # .Replace() is ordinal and has no metacharacters on EITHER operand.
    # -replace is regex on both sides ($1, $&, $$ are live in the REPLACEMENT),
    # and -f treats { } as format metacharacters. Neither is safe for a value
    # that contains a hash or a URL.
    foreach ($k in $tokens.Keys) { $html = $html.Replace("@@$k@@", (HtmlEsc $tokens[$k])) }
    if ($Linux) {
        $lxTokens = [ordered]@{
            'LINUX_URL'        = $LinuxArchiveUrl
            'LINUX_FILENAME'   = $LinuxArchiveName
            'LINUX_SIZE_HUMAN' = (HumanSize $LinuxArchiveBytes)
            'LINUX_SIZE_BYTES' = ('{0:N0}' -f $LinuxArchiveBytes)
            'LINUX_SHA256'     = $LinuxArchiveSha.ToLower()      # sha256sum -c prints and wants lowercase
            'LINUX_GLIBC'      = $lxGlibc
            'LINUX_ENGINE'     = $lxLabel
        }
        foreach ($k in $lxTokens.Keys) { $html = $html.Replace("@@$k@@", (HtmlEsc $lxTokens[$k])) }
    }

    # Bidirectional assert: a typo'd token in the template would otherwise ship a
    # literal @@FOO@@ to production, and a stale key in the map would ship the
    # previous release's value.
    if ($html -match '@@([A-Z0-9_]+)@@') { Fail "template token @@$($Matches[1])@@ was not substituted" }
    # Checked with or without -Linux: outside the blocks exactly $tokens, inside
    # exactly $LinuxTokenNames.
    $diff = @(Compare-TokenSets (Get-TemplateTokens $pb.Outside) @($tokens.Keys))
    if ($diff.Count) { Fail ("template tokens and substitution map disagree:`n" + (($diff | ForEach-Object { "      $_" }) -join "`n")) }
    $diff = @(Compare-TokenSets (Get-TemplateTokens $pb.Inside) $LinuxTokenNames)
    if ($diff.Count) { Fail ("the template's LINUX blocks and `$LinuxTokenNames disagree:`n" + (($diff | ForEach-Object { "      $_" }) -join "`n")) }

    $pageDir = Join-Path $OutDir "site-$Ver"
    if (Test-Path -LiteralPath $pageDir) { Remove-Item -LiteralPath $pageDir -Recurse -Force }
    New-Item -ItemType Directory -Path $pageDir -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $pageDir 'index.html'), $html.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding $false))
    # Self-hosted so the page makes zero third-party requests. Bebas Neue only:
    # Roboto.ttf alone is 488 KB, and this page's body copy renders fine in the
    # system stack that every supported platform already has.
    Copy-Item -LiteralPath (Join-Path $SurfDir 'ftesurf\gfx\fonts\BebasNeueRegular.ttf') -Destination $pageDir
    Copy-Item -LiteralPath (Join-Path $SurfDir 'ftesurf\gfx\fonts\OFL.txt')              -Destination $pageDir
    Copy-Item -LiteralPath (Join-Path $SurfDir 'LICENSE')                                -Destination (Join-Path $pageDir 'LICENSE.txt')
    # THE PUBLISHED RECEIPT IS NOT A BYTE COPY OF THE dist\ ONE, and this is the
    # only field they differ in.  `tool.host` is the operator's own name for
    # their own PC; provenance-by-design is this script's ethos, but that ethos
    # is about the BYTES SHIPPED, and a Windows hostname is not one of them.
    # dist\ keeps it, because knowing which machine cut a release is genuinely
    # useful to whoever cut it.
    #
    # It is WITHHELD rather than deleted, for the same reason this tree insists
    # a skew window read UNKNOWN and not MISMATCH: an absent key and a pipeline
    # that never recorded provenance are indistinguishable from outside, and
    # anyone diffing the two receipts should see a DECLARED redaction rather
    # than two provenance documents that silently disagree.
    # NOT $receipt.Clone(): OrderedDictionary implements ICloneable EXPLICITLY, so
    # the method is invisible to PowerShell's member lookup and the call throws at
    # run time -- caught by -DryRun, which is what -DryRun is for.
    $pubReceipt = [ordered]@{}
    foreach ($k in $receipt.Keys) { $pubReceipt[$k] = $receipt[$k] }
    $pubReceipt.tool = [ordered]@{ script = 'src/release/release.ps1'; host = '(withheld)' }
    $pubReceiptJson = ($pubReceipt | ConvertTo-Json -Depth 8).Replace("`r`n", "`n")
    if ($pubReceiptJson -match [regex]::Escape($env:COMPUTERNAME)) { Fail 'the published receipt still names this machine' }
    [System.IO.File]::WriteAllText((Join-Path $pageDir 'version.json'), $pubReceiptJson + "`n", (New-Object System.Text.UTF8Encoding $false))
    $pageSha = (Get-FileHash -LiteralPath (Join-Path $pageDir 'index.html') -Algorithm SHA256).Hash
    Good "rendered index.html ($((Get-Item (Join-Path $pageDir 'index.html')).Length) bytes) + 4 companions"
}

if ($DryRun) {
    Step 'Dry run: R2 write probe'
    # The rclone token is bucket-scoped and its WRITE access is otherwise
    # unproven until the real upload. Prove it on a zero-byte object instead of
    # discovering it 34 MB into a publish.
    $probe = Join-Path $env:TEMP 'ftesurf-writetest'
    Set-Content -LiteralPath $probe -Value '' -NoNewline
    try {
        Native 'rclone' @('copyto', $probe, "${Remote}:$Bucket/$Prefix/.writetest", '--bind', '0.0.0.0') 'rclone write probe' | Out-Null
        Native 'rclone' @('deletefile', "${Remote}:$Bucket/$Prefix/.writetest", '--bind', '0.0.0.0') 'rclone delete probe' | Out-Null
        Good 'R2 write access confirmed (probe object created and deleted)'
    } finally { Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue }

    # A dry run rebuilds the .7z and rewrites the receipt at this version. If the
    # version is already published, those local files now disagree with what is
    # live -- harmless, since dist\ is scratch and the deploy guard would refuse
    # to act on them, but silence here reads as "dist\ matches production".
    $dryPub = & rclone lsjson --hash "${Remote}:$Bucket/$ObjectKey" --bind 0.0.0.0 2>$null
    if ($LASTEXITCODE -eq 0 -and $dryPub) {
        $dp = ($dryPub | Out-String | ConvertFrom-Json)
        if ($dp -and $dp.Count -gt 0 -and ($dp[0].PSObject.Properties.Name -contains 'Hashes') -and $dp[0].Hashes) {
            if ($dp[0].Hashes.md5 -eq $ArchiveMd5) { Good "$Ver is already published, byte-identical to this build" }
            else {
                Warn "$Ver is ALREADY PUBLISHED with different bytes (R2 md5 $($dp[0].Hashes.md5), this build $ArchiveMd5)."
                Warn "  The live page and the live archive still agree with each other; it is dist\ that is now scratch."
                Warn "  To publish this build, -Bump first. That URL cannot be replaced -- the edge caches it for a year."
            }
        }
    }

    if ($Linux) {
        $lo = Get-R2Object $LinuxObjectKey
        if ($lo -and $lo.Md5 -eq $LinuxArchiveMd5) { Good "$LinuxArchiveName is already published, byte-identical to this build" }
        elseif ($lo) { Warn "$LinuxArchiveName is ALREADY PUBLISHED with different bytes (R2 md5 $($lo.Md5), this build $LinuxArchiveMd5); -Bump first." }
    }

    Write-Host "`n=== DRY RUN COMPLETE ===" -ForegroundColor Cyan
    Info "archive   $ArchivePath"
    Info "receipt   $ReceiptPath"
    Info "would publish to  $ArchiveUrl"
    if ($Linux) { Info "linux     $LinuxArchivePath"; Info "would publish to  $LinuxArchiveUrl" }
    Info "would deploy page to  $SiteUrl"
    if ($Overrides.Count) { Warn "overrides in effect: $($Overrides -join ', ')" }
    return
}

# =============================================================================
#  9.  UPLOAD TO R2
# =============================================================================
if (-not $SkipUpload) {
    Step "Upload to R2 ($ObjectKey)"

    # Both keys are checked before either PUT: a refusal after the first PUT
    # would cost the version.
    $LxSkipPut = $false
    if ($Linux) {
        $lo = Get-R2Object $LinuxObjectKey
        if ($lo -and $lo.Md5 -eq $LinuxArchiveMd5) { Warn "$LinuxObjectKey already published with identical bytes -- skipping its PUT, still verifying"; $LxSkipPut = $true }
        elseif ($lo -and $Force) { Warn "$LinuxObjectKey exists with DIFFERENT bytes; -Force given, overwriting."; $Overrides += 'ForceOverwrite:linux' }
        elseif ($lo) { Fail "$LinuxObjectKey already exists in R2 with different bytes (remote md5 $($lo.Md5), local $LinuxArchiveMd5).`n  Bump the version -- there is no API token to purge the edge with." }
    }

    # Refuse to overwrite. There is no Cloudflare API token in this setup, so
    # nothing here can purge: a same-version re-upload with different bytes can
    # leave the edge serving the OLD body for up to a year at the exact URL the
    # download page links to.
    $SkipPut = $false
    $existing = & rclone lsjson --hash "${Remote}:$Bucket/$ObjectKey" --bind 0.0.0.0 2>$null
    if ($LASTEXITCODE -eq 0 -and $existing) {
        $obj = ($existing | Out-String | ConvertFrom-Json)
        if ($obj -and $obj.Count -gt 0) {
            $remoteMd5 = $null
            if ($obj[0].PSObject.Properties.Name -contains 'Hashes' -and $obj[0].Hashes) { $remoteMd5 = $obj[0].Hashes.md5 }
            if ($remoteMd5 -eq $ArchiveMd5) {
                Warn "$ObjectKey already published with identical bytes -- skipping the PUT, still verifying"
                $SkipPut = $true
            } elseif ($Force) {
                Warn "$ObjectKey exists with DIFFERENT bytes; -Force given, overwriting. The edge may serve the old body until its TTL expires."
                $Overrides += 'ForceOverwrite'
                $SkipPut = $false
            } else {
                Fail "$ObjectKey already exists in R2 with different bytes (remote md5 $remoteMd5, local $ArchiveMd5).`n  Bump the version -- there is no API token to purge the edge with."
            }
        }
    }
    if (-not $SkipPut) {
        # Bandwidth. Unlike build.ps1 -Pi, an unreadable lobby directory is NOT a
        # reason to abort: that script's next step restarts all five lobbies and
        # drops everyone, so it must be certain. An upload drops nobody -- being
        # wrong toward gentle costs about fifty seconds.
        $limit = $BwLimit
        if (-not $limit) {
            $limit = '512k'
            if ($NoLobbyCheck) { $limit = '3M' }
            else {
                try {
                    $piIp = ($PiHost -split '@')[-1]
                    $lob = Invoke-RestMethod -Uri "http://${piIp}:8084/lobbies.json" -TimeoutSec 5
                    $players = ($lob.lobbies | Measure-Object -Property players -Sum).Sum
                    if ($players -eq 0) { $limit = '3M'; Info 'all lobbies empty -> --bwlimit 3M' }
                    else { Info "$players player(s) online -> --bwlimit 512k" }
                } catch { Info "lobby directory unreadable -> --bwlimit 512k (gentle)" }
            }
        }

        # copyto, NOT copy. `copy` treats the destination as a DIRECTORY and
        # derives the key from the local leaf filename; `copyto` spells the key
        # out, so the uploaded key, the verification URL and the page's download
        # link are one string and cannot drift apart.
        #
        # Content-Type explicitly: rclone guesses from the extension via the
        # Windows registry, where HKCR\.7z is the non-standard
        # application/x-compressed. R2 stores the type at PUT and serves it forever.
        #
        # --bind 0.0.0.0 is not optional on this network: without it Go's
        # happy-eyeballs tries a dead IPv6 path and the failure surfaces as a bare
        # "tls: handshake failure" that reads exactly like a bad token.
        $rcArgs = @(
            'copyto', $ArchivePath, "${Remote}:$Bucket/$ObjectKey",
            '--bind', '0.0.0.0',
            '--s3-upload-cutoff', '200M',
            '--retries', '3', '--low-level-retries', '10',
            '--header-upload', 'Cache-Control: public, max-age=31536000, immutable',
            '--header-upload', 'Content-Type: application/x-7z-compressed',
            '--bwlimit', $limit, '--stats', '20s', '--stats-one-line', '--progress'
        )
        if ($Force) { $rcArgs += '--ignore-times' }   # a header-only change is otherwise a silent no-op
        Native 'rclone' $rcArgs 'rclone copyto' | Out-Null
        Good "uploaded $(HumanSize $ArchiveBytes) to $ObjectKey"
    }

    # sidecar: lets a player verify the download with no tooling from us
    Native 'rclone' @('copyto', "$ArchivePath.sha256", "${Remote}:$Bucket/$ObjectKey.sha256",
        '--bind', '0.0.0.0', '--header-upload', 'Cache-Control: public, max-age=31536000, immutable',
        '--header-upload', 'Content-Type: text/plain; charset=utf-8') 'rclone copyto sha256' | Out-Null

    # --- verify: origin ------------------------------------------------------
    Step 'Verify the upload'
    $ls = (& rclone lsjson --hash "${Remote}:$Bucket/$ObjectKey" --bind 0.0.0.0 | Out-String | ConvertFrom-Json)
    if (-not $ls -or $ls.Count -eq 0) { Fail "object not found at $ObjectKey after upload" }
    if ([long]$ls[0].Size -ne $ArchiveBytes) { Fail "R2 size $($ls[0].Size) != local $ArchiveBytes" }
    # 34 MB is 16% of the 200 MiB multipart cutoff, so this is a single-part PUT
    # and R2's ETag really is the whole-file MD5. (--s3-chunk-size is a red
    # herring here: it only governs PART size above the cutoff.)
    $originMd5 = $null
    if ($ls[0].PSObject.Properties.Name -contains 'Hashes' -and $ls[0].Hashes) { $originMd5 = $ls[0].Hashes.md5 }
    if (-not $originMd5) { Fail 'R2 returned no md5 for the uploaded object; cannot verify it end to end' }
    if ($originMd5 -ne $ArchiveMd5) { Fail "R2 md5 $originMd5 != local $ArchiveMd5" }
    Good "origin: size and md5 match ($ArchiveMd5)"

    # --- verify: edge --------------------------------------------------------
    # A ranged GET, twice, asserting on the second. NEVER read cf-cache-status
    # from a HEAD: measured on this zone, `curl -I` on a /objects/ key that was
    # demonstrably cached (Age: 720) reported DYNAMIC every time, while a ranged
    # GET on the same key reported HIT. Cloudflare does not serve HEAD from
    # cache, so HEAD calls every path uncached -- including the two rules that
    # provably work. Do not "optimise" this back to -I.
    $hdrFile = Join-Path $env:TEMP "ftesurf-edge-$Ver.txt"
    & curl.exe -4 -s -o NUL -r 0-99 $ArchiveUrl 2>$null | Out-Null      # priming; also warms the edge
    & curl.exe -4 -s -D $hdrFile -o NUL -r 0-99 $ArchiveUrl 2>$null | Out-Null
    $hdrs = Get-Content -LiteralPath $hdrFile -Raw
    Remove-Item -LiteralPath $hdrFile -Force -ErrorAction SilentlyContinue
    if ($hdrs -notmatch '(?m)^HTTP/[\d.]+ 206') { Fail "edge did not honour a Range request:`n$hdrs" }
    if ($hdrs -match '(?mi)^content-range:\s*bytes\s+0-99/(\d+)') {
        if ([long]$Matches[1] -ne $ArchiveBytes) { Fail "edge reports total $($Matches[1]) bytes, local is $ArchiveBytes" }
        Good "edge: 206 with Content-Range total $ArchiveBytes (range requests work, so downloads resume)"
    } else { Warn 'edge returned 206 but no parseable Content-Range' }
    if ($hdrs -match '(?mi)^etag:\s*"?([0-9a-f]{32})"?') {
        if ($Matches[1] -ne $ArchiveMd5) { Warn "edge ETag $($Matches[1]) != md5 $ArchiveMd5 (stale edge copy?)" }
    }
    if ($hdrs -match '(?mi)^cf-cache-status:\s*(\S+)') {
        $cfs = $Matches[1]
        if ($cfs -match 'HIT|REVALIDATED') { Good "edge: cf-cache-status $cfs -- Cloudflare is serving this, not R2" }
        else {
            # Advisory, never fatal: Cloudflare's cache is per edge server, the
            # filenames are immutable so nothing can go stale, and this script has
            # no API token with which to fix it anyway.
            Warn "edge: cf-cache-status $cfs on the second GET. Downloads work either way; if this persists, check the dl.proto.bar Cache Rule for /$Prefix/."
        }
    }
    if ($VerifyFull) {
        Info 'downloading the whole archive to re-hash (-VerifyFull)...'
        $tmp = Join-Path $env:TEMP $ArchiveName
        & curl.exe -4 -s -o $tmp $ArchiveUrl
        $back = (Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash
        Remove-Item -LiteralPath $tmp -Force
        if ($back -ne $ArchiveSha) { Fail "round-trip sha256 $back != $ArchiveSha" }
        Good 'full round-trip sha256 matches'
    }

    if ($Linux) {
        # Same PUT and checks as above. No Content-Encoding: the .xz is the body.
        Step "Upload to R2 ($LinuxObjectKey)"
        if (-not $LxSkipPut) {
            $rcArgs = @(
                'copyto', $LinuxArchivePath, "${Remote}:$Bucket/$LinuxObjectKey",
                '--bind', '0.0.0.0',
                '--s3-upload-cutoff', '200M',
                '--retries', '3', '--low-level-retries', '10',
                '--header-upload', 'Cache-Control: public, max-age=31536000, immutable',
                '--header-upload', 'Content-Type: application/x-xz',
                '--bwlimit', (Get-BwLimit), '--stats', '20s', '--stats-one-line', '--progress'
            )
            if ($Force) { $rcArgs += '--ignore-times' }
            Native 'rclone' $rcArgs 'rclone copyto (linux)' | Out-Null
            Good "uploaded $(HumanSize $LinuxArchiveBytes) to $LinuxObjectKey"
        }
        Native 'rclone' @('copyto', "$LinuxArchivePath.sha256", "${Remote}:$Bucket/$LinuxObjectKey.sha256",
            '--bind', '0.0.0.0', '--header-upload', 'Cache-Control: public, max-age=31536000, immutable',
            '--header-upload', 'Content-Type: text/plain; charset=utf-8') 'rclone copyto sha256 (linux)' | Out-Null
        $lo = Get-R2Object $LinuxObjectKey
        if (-not $lo) { Fail "object not found at $LinuxObjectKey after upload" }
        if ($lo.Size -ne $LinuxArchiveBytes) { Fail "R2 size $($lo.Size) != local $LinuxArchiveBytes ($LinuxObjectKey)" }
        if (-not $lo.Md5) { Fail "R2 returned no md5 for $LinuxObjectKey; cannot verify it end to end" }
        if ($lo.Md5 -ne $LinuxArchiveMd5) { Fail "R2 md5 $($lo.Md5) != local $LinuxArchiveMd5 ($LinuxObjectKey)" }
        Good "origin: size and md5 match ($LinuxArchiveMd5)"
        $hdrFile = Join-Path $env:TEMP "ftesurf-edge-linux-$Ver.txt"
        & curl.exe -4 -s -o NUL -r 0-99 $LinuxArchiveUrl 2>$null | Out-Null
        & curl.exe -4 -s -D $hdrFile -o NUL -r 0-99 $LinuxArchiveUrl 2>$null | Out-Null
        $hdrs = Get-Content -LiteralPath $hdrFile -Raw
        Remove-Item -LiteralPath $hdrFile -Force -ErrorAction SilentlyContinue
        if ($hdrs -notmatch '(?m)^HTTP/[\d.]+ 206') { Fail "edge did not honour a Range request for the Linux archive:`n$hdrs" }
        if ($hdrs -match '(?mi)^content-range:\s*bytes\s+0-99/(\d+)') {
            if ([long]$Matches[1] -ne $LinuxArchiveBytes) { Fail "edge reports total $($Matches[1]) bytes, local is $LinuxArchiveBytes ($LinuxObjectKey)" }
            Good "edge: 206 with Content-Range total $LinuxArchiveBytes"
        } else { Warn 'edge returned 206 but no parseable Content-Range (linux)' }
        if ($VerifyFull) {
            $tmp = Join-Path $env:TEMP $LinuxArchiveName
            & curl.exe -4 -s -o $tmp $LinuxArchiveUrl
            $back = (Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash
            Remove-Item -LiteralPath $tmp -Force
            if ($back -ne $LinuxArchiveSha) { Fail "round-trip sha256 $back != $LinuxArchiveSha ($LinuxObjectKey)" }
            Good 'full round-trip sha256 matches (linux)'
        }
    }
}

# =============================================================================
#  10.  DEPLOY THE PAGE
#
#  The page was RENDERED back at step 9b, deliberately before the -DryRun exit,
#  so that a dry run still exercises the token substitution and both of its
#  asserts. Only the scp and the swap live here.
# =============================================================================
if (-not $SkipSite) {
    Step 'Deploy to the Pi'

    # THE PAGE MUST NEVER ADVERTISE A HASH THAT IS NOT PUBLISHED.
    #
    # The page states the archive's sha256 and byte count, and offers a
    # Get-FileHash one-liner that prints OK or MISMATCH. The .7z is rebuilt on
    # every run and 7-Zip stamps mtimes into it, so two runs at the same version
    # produce different bytes -- which means a -SkipUpload re-run would render a
    # page whose checksum belongs to an archive nobody can download, and every
    # honest verifier would print MISMATCH at the one moment we asked them to
    # trust us. (This is not hypothetical: it happened on the 0.1.0 release.)
    #
    # One rclone call closes it. Cheap, and it also catches a page deployed
    # against an upload that silently failed earlier in the run.
    $pubMd5 = $null
    $pubJson = & rclone lsjson --hash "${Remote}:$Bucket/$ObjectKey" --bind 0.0.0.0 2>$null
    if ($LASTEXITCODE -eq 0 -and $pubJson) {
        $po = ($pubJson | Out-String | ConvertFrom-Json)
        if ($po -and $po.Count -gt 0 -and ($po[0].PSObject.Properties.Name -contains 'Hashes') -and $po[0].Hashes) {
            $pubMd5 = $po[0].Hashes.md5
        }
    }
    if ($pubMd5 -ne $ArchiveMd5) {
        $what = if ($pubMd5) { "R2 holds md5 $pubMd5, this run built $ArchiveMd5" } else { "no object at $ObjectKey" }
        Fail @"
refusing to deploy a page for an archive that is not published.
  $what
  The page would state a sha256 that no downloadable file has, so anyone who
  checked it would get MISMATCH.
  Fix: run without -SkipUpload. If R2 already holds DIFFERENT bytes at this
  version, bump the version instead -- the edge caches /$Prefix/ immutably for a
  year and there is no API token here to purge it with.
"@
    }
    Good "published archive matches this run (md5 $ArchiveMd5)"
    if ($Linux) {
        $lo = Get-R2Object $LinuxObjectKey
        if (-not $lo -or $lo.Md5 -ne $LinuxArchiveMd5) {
            Fail ("refusing to deploy a page for a Linux archive that is not published.`n  " +
                $(if ($lo) { "R2 holds md5 $($lo.Md5), this run built $LinuxArchiveMd5" } else { "no object at $LinuxObjectKey" }))
        }
        Good "published Linux archive matches this run (md5 $LinuxArchiveMd5)"
    }

    $sshOpts = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10')

    # Always push the Pi-side files, so the installed snippet can never silently
    # drift from the one in git.
    & ssh @sshOpts $PiHost "mkdir -p '$SiteRoot/.incoming/$Ver'" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "cannot reach $PiHost over ssh" }
    foreach ($f in @('ftesurf.nginx', 'install.sh', 'publish.sh')) {
        & scp @sshOpts -q (Join-Path $RelDir $f) "${PiHost}:$SiteRoot/$f"
        if ($LASTEXITCODE -ne 0) { Fail "scp $f failed" }
    }
    # NOT "$pageDir\*": scp does not glob, and on Windows the literal string is
    # passed through, so the copy fails with `stat local "...\*": No such file or
    # directory` -- AFTER both archives are already uploaded, which is the
    # documented unre-runnable state.  Enumerate the files and copy each one; the
    # page dir is rendered by this script and is five files.
    $pageFiles = @(Get-ChildItem -LiteralPath $pageDir -File | ForEach-Object { $_.FullName })
    if (-not $pageFiles.Count) { Fail "no page files in $pageDir" }
    foreach ($pf in $pageFiles) {
        & scp @sshOpts -q -LiteralPath $pf "${PiHost}:$SiteRoot/.incoming/$Ver/$([IO.Path]::GetFileName($pf))"
        if ($LASTEXITCODE -ne 0) { Fail "scp $([IO.Path]::GetFileName($pf)) failed" }
    }
    if ($LASTEXITCODE -ne 0) { Fail 'scp of the page failed' }
    & ssh @sshOpts $PiHost "chmod +x '$SiteRoot/publish.sh' '$SiteRoot/install.sh' && sh '$SiteRoot/publish.sh' '$Ver'" 2>&1 | ForEach-Object { Info $_ }
    if ($LASTEXITCODE -ne 0) { Fail 'publish.sh failed on the Pi' }

    # --- is the nginx snippet actually wired up? -----------------------------
    # Four checks, because each is blind to what the others catch. In
    # particular, https://proto.bar/ftesurf ALREADY returns 200 with an HTML
    # body on an unconfigured box -- it is the filebrowser SPA served by the
    # vhost's catch-all -- so any status-code check reports success on a Pi
    # where nothing has been installed.
    Step 'Verify the page'
    $localSnip = (Get-FileHash -LiteralPath (Join-Path $RelDir 'ftesurf.nginx') -Algorithm SHA256).Hash.ToLower()
    $remoteSnip = (& ssh @sshOpts $PiHost "sha256sum /etc/nginx/snippets/ftesurf.conf 2>/dev/null | cut -d' ' -f1").Trim()
    $included  = (& ssh @sshOpts $PiHost "grep -c 'snippets/ftesurf.conf' /etc/nginx/sites-enabled/filebrowsers.conf 2>/dev/null || true").Trim()

    $needSetup = $false
    if (-not $remoteSnip)                 { Warn 'nginx snippet is NOT installed';            $needSetup = $true }
    elseif ($remoteSnip -ne $localSnip)   { Warn 'nginx snippet on the Pi is STALE';          $needSetup = $true }
    if ($included -eq '0')                { Warn 'the include line is missing from filebrowsers.conf (certbot rewrite?)'; $needSetup = $true }

    if ($needSetup) {
        Write-Host "`n  ONE-TIME SETUP NEEDED. proto's sudo requires a password, so this script" -ForegroundColor Yellow
        Write-Host   "  cannot touch /etc/nginx. Run this once, on the Pi or over ssh:" -ForegroundColor Yellow
        Write-Host   "`n      ssh $PiHost" -ForegroundColor White
        Write-Host   "      sudo sh $SiteRoot/install.sh`n" -ForegroundColor White
        Write-Host   "  Then re-run this script with -SkipUpload to finish the page." -ForegroundColor Yellow
    } else {
        $servedFile = Join-Path $env:TEMP "ftesurf-served-$Ver.html"
        $hdrFile2   = Join-Path $env:TEMP "ftesurf-served-$Ver.txt"
        # -L IS REQUIRED, not tidiness. $SiteUrl has no trailing slash, so it hits
        # `location = /ftesurf { return 301 ... }` -- and a 301 carries neither the
        # marker header nor the page body. Without -L this step reported "nginx has
        # not reloaded" against a site that was serving the new page perfectly.
        # -D appends BOTH header blocks, so the marker is still found in the 200.
        #
        # No --compressed: curl sends no Accept-Encoding by default, so nginx's
        # gzip does not fire and the bytes on the wire are the file itself --
        # which is what makes the hash comparison exact.
        & curl.exe -4 -sL -D $hdrFile2 -o $servedFile $SiteUrl 2>$null | Out-Null
        $h2 = Get-Content -LiteralPath $hdrFile2 -Raw
        if ($h2 -notmatch '(?mi)^x-ftesurf-site:') {
            Warn 'the marker header is absent: the snippet is on disk but nginx has not reloaded it.'
            Warn "  ssh $PiHost 'sudo nginx -t && sudo systemctl reload nginx'"
        } else {
            $servedSha = (Get-FileHash -LiteralPath $servedFile -Algorithm SHA256).Hash
            # Compare hashes, not a substring: a page that lists previous releases
            # contains its own successor's version string, so a substring check
            # passes on a stale page.
            if ($servedSha -ne $pageSha) { Fail "the page served at $SiteUrl does not match what was just deployed (sha256 $servedSha != $pageSha)" }
            Good "$SiteUrl serves the new page (sha256 verified byte for byte)"
        }
        Remove-Item -LiteralPath $servedFile, $hdrFile2 -Force -ErrorAction SilentlyContinue
    }
}

# =============================================================================
#  11.  OPTIONAL: TAG, PRUNE
# =============================================================================
if ($Tag) {
    Step 'Tag'
    # A tag asserts "this commit is what shipped", which is false if any gate
    # was waved past.
    if ($Overrides.Count) { Warn "not tagging: this release used $($Overrides -join ', ')" }
    else {
        $existingTag = & git -C $SurfDir tag --list "v$Ver"
        if ($existingTag) { Warn "tag v$Ver already exists; not moving it" }
        else {
            Native 'git' @('-C', $SurfDir, 'tag', '-a', "v$Ver", '-m', "FTESurf $Ver (QC build $qcBuild, engine patch $enginePatch)") 'git tag' | Out-Null
            Good "created local tag v$Ver (NOT pushed -- git push does not send tags; use: git push origin v$Ver)"
        }
    }
}

if ($Prune -and -not $SkipUpload) {
    Step "Prune R2 (keeping the newest $PruneKeep)"
    $names = @(& rclone lsf "${Remote}:$Bucket/$Prefix/" --bind 0.0.0.0)
    # Whole versions (.7z and .tar.xz together), by PARSED SEMVER, never by
    # ModTime: a -Force re-upload rewrites ModTime and would reorder the list.
    $doomed = @(Select-PruneDoomed $names $PruneKeep @($ArchiveName, $LinuxArchiveName))
    if (-not $doomed.Count) { Info "nothing to prune ($($names.Count) objects listed)" }
    else {
        Warn "about to delete $($doomed.Count) old archive(s): $($doomed -join ', ')"
        $ans = Read-Host '  type DELETE to confirm'
        if ($ans -ceq 'DELETE') {
            foreach ($d in $doomed) {
                # deletefile on a named object, never `rclone delete` on the
                # prefix (it would take the .sha256 sidecars too) and never sync.
                Native 'rclone' @('deletefile', "${Remote}:$Bucket/$Prefix/$d", '--bind', '0.0.0.0') 'rclone deletefile' | Out-Null
                & rclone deletefile "${Remote}:$Bucket/$Prefix/$d.sha256" --bind 0.0.0.0 2>$null | Out-Null
                Info "deleted $d"
            }
        } else { Info 'not confirmed; nothing deleted' }
    }
}

# =============================================================================
Write-Host "`n=== FTESurf $Ver released ===" -ForegroundColor Green
Info "download  $ArchiveUrl"
Info "page      $SiteUrl"
Info "size      $(HumanSize $ArchiveBytes)   sha256 $ArchiveSha"
if ($Linux) {
    Info "linux     $LinuxArchiveUrl"
    Info "          $(HumanSize $LinuxArchiveBytes)   sha256 $LinuxArchiveSha   glibc $lxGlibc+   engine patch $lxLabel"
}
Info "provenance  QC build $qcBuild - engine patch $engineLabel - git $GitShort"
if ($Overrides.Count) { Warn "OVERRIDES USED: $($Overrides -join ', ')  (recorded in $ReceiptPath)" }
