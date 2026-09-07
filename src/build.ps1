<#
================================================================================
 FTESurf build + deploy.

   .\build.ps1            QC only (fast -- this is what you want 95% of the time)
   .\build.ps1 -Engine    QC + incremental engine/plugin rebuild + dual deploy
   .\build.ps1 -Engine -Full   as above, but forces a full recompile first

 WHY THE DUAL DEPLOY IS NOT OPTIONAL
 -----------------------------------
 The engine tree ($FteRoot) can be ONE source tree shared by FTESurf and a
 second install ($QuakeDir).  The engine's plugin gate checks only
 the function table (sizeof(plugmodfuncs_t) + MODPLUGFUNCS_VERSION) -- there
 is no data-struct canary -- so a plugin built against an older engine header
 loads SILENTLY and corrupts memory at map load.  That is the 2026-07-23
 "every HL2/CSS map stalls" incident in ENGINE_PATCHES.md.  So: whenever the
 exe is rebuilt, every plugin is rebuilt and BOTH installs are refreshed.

 -Full is required after ANY engine header change (pmove.h included).  Neither
 the engine nor the plugin makefiles track header dependencies: after the
 model_t layout change, `make m-rel` rebuilt 7 of 213 objects and the linked
 exe mixed old- and new-layout code, SIGSEGVing at VBSP load.
================================================================================
#>
param(
    [switch]$Engine,
    [switch]$Full,
    [switch]$Run,

    # The engine tree -- github.com/ProtoAus/ftequakers.  Only needed with
    # -Engine.  Override per-invocation with -FteRoot, or per-shell with
    # $env:FTESURF_FTEROOT.
    [string]$FteRoot  = $(if ($env:FTESURF_FTEROOT)  { $env:FTESURF_FTEROOT }
                          else { 'C:\msys64\home\Lex\fteqw' }),

    # A SECOND install that shares the same engine tree.  Where it exists the
    # dual deploy is not optional -- see the header.  Absent on disk: skipped.
    [string]$QuakeDir = $(if ($null -ne $env:FTESURF_QUAKEDIR) { $env:FTESURF_QUAKEDIR }
                          else { 'C:\FTEQuake' }),

    # msys2's make.  Only needed with -Engine.
    [string]$Make     = $(if ($env:FTESURF_MAKE)     { $env:FTESURF_MAKE }
                          else { 'C:\msys64\usr\bin\make.exe' })
)

$ErrorActionPreference = 'Stop'

# Derived from this script's own location, so a fresh clone builds wherever it
# landed.  build.ps1 lives in <install>\src\, so the install is its parent.
$SrcDir     = $PSScriptRoot
$SurfDir    = Split-Path $SrcDir -Parent
$EngineDir  = "$FteRoot\engine"
$ReleaseDir = "$EngineDir\release"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor DarkGray }

# ------------------------------------------------------------------ fteqcc ---
#  The repository does not ship a compiler binary: fteqcc is GPLv2 and we have
#  no source offer to attach to a redistributed exe.  Look, in order, for a copy
#  dropped in src\, one on PATH, and one in the engine tree -- which is where
#  `make -C <FteRoot>\engine qcc-rel FTE_TARGET=win64` puts it.  So there is no
#  third-party download here: fteqcc comes from the engine this game requires.
$Fteqcc = $null
foreach ($cand in @((Join-Path $SrcDir 'fteqcc64.exe'),
                    (Join-Path $SrcDir 'fteqcc.exe'),
                    "$ReleaseDir\fteqcc64.exe")) {
    if (Test-Path -LiteralPath $cand) { $Fteqcc = (Resolve-Path $cand).Path; break }
}
if (-not $Fteqcc) {
    $onPath = Get-Command fteqcc64.exe, fteqcc.exe -ErrorAction SilentlyContinue |
              Select-Object -First 1
    if ($onPath) { $Fteqcc = $onPath.Source }
}
if (-not $Fteqcc) {
    throw @"
fteqcc not found.
  looked in : $SrcDir
              PATH
              $ReleaseDir
Build it out of the engine tree (github.com/ProtoAus/ftequakers):
    make -C "$EngineDir" qcc-rel FTE_TARGET=win64
then copy engine\release\fteqcc64.exe into $SrcDir, put it on PATH, or set
`$env:FTESURF_FTEROOT so this script can find your engine tree.
"@
}

# ---------------------------------------------------------------- QC ---------
Step "QuakeC"
Ok "fteqcc: $Fteqcc"
Push-Location $SrcDir
try {
    foreach ($src in @('sv_progs.src', 'cl_progs.src', 'm_progs.src')) {
        $out = & $Fteqcc $src 2>&1
        if ($LASTEXITCODE -ne 0) {
            $out | Write-Host
            throw "fteqcc failed on $src"
        }
        $warn = $out | Select-String -Pattern 'warning' -SimpleMatch
        if ($warn) { $warn | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow } }
        Ok "$src ok"
    }
} finally { Pop-Location }

# ------------------------------------------------------------ engine ---------
if ($Engine) {
    $env:PATH = "C:\msys64\ucrt64\bin;C:\msys64\usr\bin;$env:PATH"

    if ($Full) {
        Step "Full rebuild: clearing objects and plugin DLLs"
        # The makefiles do not track header deps.  Removing the objects is the
        # only way to guarantee the whole tree sees a changed header.
        Remove-Item "$ReleaseDir\m_mgw64\*.o","$ReleaseDir\m_mgw64\*.d" -Force -EA SilentlyContinue
        Remove-Item "$ReleaseDir\sv_mingw64\*.o","$ReleaseDir\sv_mingw64\*.d" -Force -EA SilentlyContinue
        Remove-Item "$ReleaseDir\fteplug_*_x64.dll" -Force -EA SilentlyContinue
        Ok "objects and plugins cleared"
    }

    # FTE_TARGET=win64 is MANDATORY: msys2's gcc reports mingw, so the
    # auto-detect in engine/Makefile:542-549 picks win32.
    Step "make m-rel (client)"
    & $Make -C $EngineDir m-rel FTE_TARGET=win64
    if ($LASTEXITCODE -ne 0) { throw "m-rel failed" }

    Step "make sv-rel (dedicated server)"
    & $Make -C $EngineDir sv-rel FTE_TARGET=win64
    if ($LASTEXITCODE -ne 0) { throw "sv-rel failed" }

    # ---------------------------------------------------------------------
    #  The hl2 plugin's GLSL, which `plugins-rel` DOES NOT BUILD.
    #
    #  plugins/hl2/Makefile has `all: mat_vmt_progs.h`, a rule that runs
    #  engine/shaders/generatebuiltinsl over glsl/vmt/*.glsl to turn each
    #  program into C string literals.  `make plugins-rel` from the ENGINE
    #  directory never invokes that sub-makefile's default target, so the
    #  header is only ever regenerated by someone running make in that
    #  directory by hand.
    #
    #  ⚠ IT FAILS SILENTLY AND INVISIBLY.  Add or edit a .glsl, build, and the
    #  plugin compiles clean against the STALE header -- so the program simply
    #  is not in the DLL, every material asking for it falls back, and the only
    #  symptom is on screen.  Build 12 added vmt/flatdither and shipped it
    #  missing exactly once before this was noticed.
    #
    #  generatebuiltinsl is a build tool, not part of the engine, so it is not
    #  built by any target either; compile it if it is absent.
    # ---------------------------------------------------------------------
    Step "hl2 glsl -> mat_vmt_progs.h"
    $gbsl = "$EngineDir\shaders\generatebuiltinsl.exe"
    if (-not (Test-Path $gbsl)) {
        & gcc -O1 -o $gbsl "$EngineDir\shaders\generatebuiltinsl.c"
        if ($LASTEXITCODE -ne 0) { throw "could not build generatebuiltinsl" }
        Ok "built generatebuiltinsl"
    }
    & $Make -C "$FteRoot\plugins\hl2"
    if ($LASTEXITCODE -ne 0) { throw "hl2 glsl generation failed" }

    # Bare `plugins-rel` dies on an unrelated ffmpeg target (plugins/Makefile:241),
    # so NATIVE_PLUGINS is always explicit.
    Step "make plugins-rel (hl2 cod box3d ode)"
    & $Make -C $EngineDir plugins-rel FTE_TARGET=win64 NATIVE_PLUGINS="hl2 cod box3d ode"
    if ($LASTEXITCODE -ne 0) { throw "plugins-rel failed" }

    # ------------------------------------------------------- deploy ---------
    function Deploy($from, $to) {
        if (-not (Test-Path $from)) { throw "missing build output: $from" }
        if (Test-Path $to) { Copy-Item $to "$to.prev" -Force }
        Copy-Item $from $to -Force
        Ok ((Split-Path $to -Leaf) + "  <- " + (Get-Item $from).LastWriteTime)
    }

    Step "Deploy -> $SurfDir"
    Deploy "$ReleaseDir\fteqw64.exe"             "$SurfDir\ftesurf64.exe"
    Deploy "$ReleaseDir\fteplug_hl2_x64.dll"     "$SurfDir\fteplug_hl2_x64.dll"

    # Conditional only so a fresh clone with no second install still builds.
    # Where the second install DOES exist the dual deploy stays mandatory --
    # see the header: the plugin gate has no data-struct canary, so a plugin
    # built against an older engine header loads silently and corrupts memory.
    if ($QuakeDir -and (Test-Path -LiteralPath $QuakeDir)) {
        Step "Deploy -> $QuakeDir  (shared engine tree -- see header)"
        Deploy "$ReleaseDir\fteqw64.exe"             "$QuakeDir\fteqw64.exe"
        Deploy "$ReleaseDir\fteqwsv64.exe"           "$QuakeDir\fteqwsv64.exe"
        foreach ($p in @('hl2', 'cod', 'box3d', 'ode')) {
            Deploy "$ReleaseDir\fteplug_${p}_x64.dll" "$QuakeDir\fteplug_${p}_x64.dll"
        }
    } else {
        Ok "second install not present ($QuakeDir) -- dual deploy skipped"
    }
}

Step "Done"
Ok "qwprogs.dat  $((Get-Item "$SurfDir\ftesurf\qwprogs.dat").Length) bytes"
Ok "csprogs.dat  $((Get-Item "$SurfDir\ftesurf\csprogs.dat").Length) bytes"

if ($Run) {
    Step "Launching"
    Start-Process -FilePath "$SurfDir\ftesurf64.exe" -WorkingDirectory $SurfDir
}
