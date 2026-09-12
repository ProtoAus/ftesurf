<#
================================================================================
 FTESurf build + deploy.

   .\build.ps1            QC only (fast -- this is what you want 95% of the time)
   .\build.ps1 -Engine    QC + incremental engine/plugin rebuild + dual deploy
   .\build.ps1 -Engine -Full   as above, but forces a full recompile first
   .\build.ps1 -Pi        QC, then qwprogs.dat + csprogs.dat to the NanoPi and
                          all five lobbies restarted.  Refused while anyone is
                          on a lobby; -PiForce overrides.  -PiHost/-PiGame
                          name the Pi and its gamedir.

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

 -Pi: A LOBBY RUNS THE PI'S PROGS, NOT YOURS
 ------------------------------------------
 A remote player downloads csprogs.dat from the lobby they join, so a client
 change that works on a listen server is invisible on every lobby until the Pi
 has it.  -Pi ships the two progs a dedicated server loads, qwprogs.dat and
 csprogs.dat, and NEVER menu.dat: a dedicated server has no menu, and the menu
 a player sees is the one in their own install.  It runs after the QC compile
 (and after the engine deploy, with -Engine), in this order:

   1. Reads surfd's http://<host>:8084/lobbies.json, <host> being the host half
      of $PiHost, and REFUSES if any lobby has players, because step 5 drops
      every one of them.  It refuses too when the directory cannot be read, and
      when the directory carries no row for one of the five lobbies step 5
      restarts -- A LOBBY THE DIRECTORY CANNOT SEE IS NOT AN EMPTY LOBBY: the
      panel's flush button empties the table outright, a surfd restart or a new
      DB starts empty, and a lobby whose heartbeats are being refused ages out
      of the table after LOBBY_TTL (30 s) while it is up and full of players.
      Only a row for each of the five, every one reading 0 players, means
      nobody is on.  -PiForce overrides all three.
   2. scp's each file to <name>.new beside the live one in $PiGame.
   3. Hashes both .new files on the Pi (sha256sum).  One that is not the local
      file's hash stops the deploy here, with the live files untouched.
   4. In ONE ssh command: keeps the live pair as <name>.prev, mv -f's both .new
      files into place, and hashes the result.
   5. Runs `sudo -n /usr/bin/systemctl restart ftesurf@N` for N = 1..5, one ssh
      each so every unit keeps its own exit code and message.  A failure is
      reported and the rest still restart; the script fails at the end.

 WHY STEP 4 IS A RENAME, AND BOTH FILES IN ONE COMMAND.  scp writes into its
 target in place.  A lobby that loads csprogs.dat while it is half-copied -- a
 map rotation reloads it -- publishes an empty *csprogs, and every client drops
 to the stock Quake HUD: the Patch 282 finding.  <name>.new sits in the same
 directory, so it is on the same filesystem and mv -f is rename(2), which is
 atomic: a lobby opens the old file or the new one, never a torn one.  Both
 renames ride one ssh command because the two progs must agree -- sh_defs.qc's
 STAT_FS_* numbers are compiled into both -- so the window in which a rotation
 could load a new half beside an old half is two adjacent renames, not the
 length of a second ssh handshake.

 WHY IT RESTARTS.  Left alone, each lobby would pick the new pair up at its own
 next rotation, up to half an hour apart, and until then lobbies would hand
 players different client code.  Restarting all five publishes the new
 *csprogs everywhere together.

 WHY THERE IS NO .service SUFFIX.  sudo matches the argument vector against the
 grant in /etc/sudoers.d/ftesurf LITERALLY, and that grant names `ftesurf@1`.
 `ftesurf@1.service` is the same unit to systemd and a different command to
 sudo, and -n turns the mismatch into "a password is required" -- which reads
 exactly like a missing grant.  surfd/surfd-admin.sudoers records the grant;
 lobbies 4 and 5 fail step 5 until its six new lines are installed.

 Needs ssh key authentication to $PiHost.  Every ssh and scp runs with
 BatchMode=yes, so a missing key fails at once instead of prompting.
================================================================================
#>
param(
    [switch]$Engine,
    [switch]$Full,
    [switch]$Run,

    # After the build, push qwprogs.dat and csprogs.dat to the NanoPi's lobbies
    # and restart them -- see the header.  -PiForce deploys even while the
    # directory shows players on a lobby, cannot be read, or has no row for one
    # of the five lobbies that are about to be restarted.
    [switch]$Pi,
    [switch]$PiForce,

    # The Pi as ssh sees it.  Its host half also locates surfd's directory,
    # http://<host>:8084/lobbies.json, which -Pi reads before touching anything.
    [string]$PiHost   = 'proto@192.168.1.102',

    # The lobbies' gamedir on the Pi: run.sh's -basedir plus the game name.
    [string]$PiGame   = '/srv/nvme/ftesurf-server/game/ftesurf',

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

# ---------------------------------------------------------------- Pi ---------
#  The order and the reasons are in the header.  Everything that can refuse
#  does so BEFORE a live file is touched: the players check, the upload and the
#  hash check all leave the Pi's lobbies exactly as they were.
if ($Pi) {
    Step "Pi deploy -> ${PiHost}:$PiGame"

    # Both are pasted into remote shell commands, so anything that is not a
    # plain user@host and a plain absolute path is refused rather than quoted
    # around.  The leading character is pinned too: ssh reads '-...' as an
    # option.
    if ($PiHost -notmatch '^([A-Za-z0-9_][A-Za-z0-9._-]*@)?[A-Za-z0-9_][A-Za-z0-9.-]*$') {
        throw "-PiHost '$PiHost' is not a plain user@host"
    }
    if ($PiGame -notmatch '^/[A-Za-z0-9._/-]+$') {
        throw "-PiGame '$PiGame' is not a plain absolute path"
    }
    foreach ($tool in @('ssh', 'scp')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "$tool not found -- -Pi needs the OpenSSH client"
        }
    }

    # ssh and scp write host-key notices, warnings and errors to stderr.  Under
    # this script's $ErrorActionPreference = 'Stop', Windows PowerShell turns a
    # redirected stderr line into a terminating error -- the same trap as
    # fteqcc's banner -- which would abort a deploy half way through.  So each
    # call runs under Continue, and the exit code is the verdict.
    function PiNative([string]$exe, [string[]]$argv) {
        $ErrorActionPreference = 'Continue'
        $lines = @(& $exe @argv 2>&1 | ForEach-Object { "$_" })
        [pscustomobject]@{ Code = $LASTEXITCODE; Out = $lines }
    }
    # sha256sum lines -> @{ file = hash }.  Anything else in the output is
    # ignored, so a missing file simply has no entry and fails the compare.
    function PiHashes($result) {
        $h = @{}
        foreach ($line in $result.Out) {
            if ($line -match '^([0-9a-fA-F]{64}) [ *](\S+)$') {
                $h[$Matches[2]] = $Matches[1].ToLowerInvariant()
            }
        }
        $h
    }
    $sshOpts = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10')
    $piAddr  = ($PiHost -split '@')[-1]
    $names   = @('qwprogs.dat', 'csprogs.dat')          # never menu.dat

    # The lobbies step 5 restarts, in restart order, each with the port its own
    # cfg binds (ftesurf/cfg/lobbyN.cfg's sv_port; lobby1.cfg's header has why
    # the port is a lobby's identity and why they are spaced by ten).  ONE list,
    # because step 1 has to know exactly which lobbies step 5 will drop -- a
    # directory with no row for one of them cannot say that one is empty -- and
    # two separate lists would drift apart at the next renumber.
    $lobbies = @(
        [pscustomobject]@{ Unit = 1; Port = 27510 }     # surf tier 1
        [pscustomobject]@{ Unit = 2; Port = 27520 }     # surf tier 2
        [pscustomobject]@{ Unit = 3; Port = 27530 }     # surf tier 3
        [pscustomobject]@{ Unit = 4; Port = 27540 }     # bhop easy
        [pscustomobject]@{ Unit = 5; Port = 27550 }     # bhop hard
    )

    $local = @{}
    foreach ($n in $names) {
        $path = Join-Path "$SurfDir\ftesurf" $n
        if (-not (Test-Path -LiteralPath $path)) { throw "missing build output: $path" }
        $local[$n] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        Ok ("{0}  sha256 {1}  {2} bytes" -f $n, $local[$n], (Get-Item -LiteralPath $path).Length)
    }

    # 1. Nobody on.  The counts are the lobbies' own heartbeats, so they are at
    #    most lobby_master_rate (5 s) old -- read once, just before uploading.
    #
    #    A MISSING ROW IS NOT AN EMPTY LOBBY, so "nobody is on" needs positive
    #    evidence for every unit step 5 restarts: a row for each of $lobbies,
    #    all of them 0 players.  surfd knows a lobby only while its heartbeats
    #    arrive and drops the row after LOBBY_TTL (30 s), so an empty or short
    #    list is routine and says nothing about who is playing -- the panel's
    #    flush button DELETEs every row (its own documented stopall -> flush ->
    #    edit -> runall), a restarted surfd or a fresh DB answers with an empty
    #    array, and a lobby being rate limited ages out while it is up and full.
    #    Treating any of those as "nobody on" would drop a full lobby at step 5,
    #    so a short list refuses exactly like an unreachable directory.
    Step "Pi: who is on"
    $dirUrl = "http://${piAddr}:8084/lobbies.json"
    $busy   = $null                     # $null = could not tell; @() = no row has players
    $noRow  = @()                       # lobbies step 5 restarts that have no row at all
    try {
        $dir = Invoke-RestMethod -Uri $dirUrl -TimeoutSec 5 -UseBasicParsing
        if ($dir -and $dir.PSObject.Properties['lobbies']) {
            $rows = @($dir.lobbies)
            # surfd's addr is "host:port" and SURFD_PUBLIC_HOST can make the
            # host half a name or a literal, so the port is the tail after the
            # LAST colon -- the rule the menu's Lob_PortOf and test_surfd.py
            # already use, and the only one an IPv6 host cannot fool.
            $seen  = @($rows | ForEach-Object { "$($_.addr)".Split(':')[-1] })
            $noRow = @($lobbies | Where-Object { $seen -notcontains "$($_.Port)" })
            $busy  = @($rows | Where-Object { [int]$_.players -gt 0 })
            Ok ("{0}: {1} live lobbies" -f $dirUrl, $rows.Count)
        } else {
            Write-Host "    $dirUrl answered without a lobbies array" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "    cannot read ${dirUrl}: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    if ($null -eq $busy) {
        if (-not $PiForce) {
            throw "cannot tell whether anyone is on a lobby, so nothing was deployed.  Check surfd, or pass -PiForce."
        }
        Write-Host "    -PiForce: deploying without knowing who is on" -ForegroundColor Yellow
    } elseif ($busy.Count -gt 0) {
        foreach ($l in $busy) {
            Write-Host ("    {0} on {1}: {2}/{3} players" -f $l.name, $l.map, $l.players, $l.max) -ForegroundColor Yellow
        }
        if (-not $PiForce) {
            throw "players are on a lobby and -Pi restarts all five, so nothing was deployed.  Wait for 0 players, or pass -PiForce."
        }
        Write-Host "    -PiForce: deploying anyway -- everyone above is dropped" -ForegroundColor Yellow
    } elseif ($noRow.Count -gt 0) {
        foreach ($l in $noRow) {
            Write-Host ("    no row for ftesurf@{0} (port {1}) -- it may be up and full" -f $l.Unit, $l.Port) -ForegroundColor Yellow
        }
        if (-not $PiForce) {
            $which = ($noRow | ForEach-Object { "ftesurf@$($_.Unit)" }) -join ', '
            throw ("the directory has no row for $which -- nothing can say who is on, " +
                   "and -Pi restarts all five, so nothing was deployed.  Check that every lobby is up and " +
                   "heart-beating -- 4 and 5 need the sudoers grant and the systemctl enable from Stage L -- or pass -PiForce.")
        }
        Write-Host "    -PiForce: deploying without knowing who is on the lobbies above" -ForegroundColor Yellow
    } else {
        Ok "nobody on any lobby (a row for each of the five, all 0 players)"
    }

    # 2. Upload beside the live files.  Bare names from their own directory, so
    #    a drive letter's colon can never be read as scp's host:path separator.
    Step "Pi: upload"
    Push-Location "$SurfDir\ftesurf"
    try {
        foreach ($n in $names) {
            $r = PiNative 'scp' ($sshOpts + @('-q', $n, ('{0}:{1}/{2}.new' -f $PiHost, $PiGame, $n)))
            if ($r.Code -ne 0) {
                $r.Out | Write-Host
                throw "scp $n failed (exit $($r.Code)) -- the live files are untouched"
            }
            Ok "$n -> $n.new"
        }
    } finally { Pop-Location }

    # 3. The copies are the build, byte for byte, before anything is swapped.
    $r = PiNative 'ssh' ($sshOpts + @($PiHost,
            ('cd {0} && sha256sum qwprogs.dat.new csprogs.dat.new' -f $PiGame)))
    $remote = PiHashes $r
    foreach ($n in $names) {
        if ($remote["$n.new"] -ne $local[$n]) {
            $r.Out | Write-Host
            throw "$n.new on the Pi does not hash to the local $n (ssh exit $($r.Code)) -- the live files are untouched"
        }
    }
    Ok "both .new files hash to this build"

    # 4. THE SWAP -- one command, two renames.  See the header for why.
    Step "Pi: swap"
    $swap = ('cd {0}' +
             ' && cp -p qwprogs.dat qwprogs.dat.prev && cp -p csprogs.dat csprogs.dat.prev' +
             ' && mv -f qwprogs.dat.new qwprogs.dat && mv -f csprogs.dat.new csprogs.dat' +
             ' && sha256sum qwprogs.dat csprogs.dat') -f $PiGame
    $r = PiNative 'ssh' ($sshOpts + @($PiHost, $swap))
    $remote = PiHashes $r
    foreach ($n in $names) {
        if ($remote[$n] -ne $local[$n]) {
            $r.Out | Write-Host
            throw ("the swap did not complete (ssh exit $($r.Code)): the live $n is not this build.  " +
                   "Nothing was restarted -- check both files in $PiGame before a rotation loads them; " +
                   "a file that was replaced has its predecessor in <name>.prev.")
        }
    }
    Ok "live qwprogs.dat and csprogs.dat are this build (previous pair kept as .prev)"

    # 5. Restart all five.  NO .service SUFFIX -- sudo matches the grant
    #    literally, see the header.  -n: a missing grant fails, it never prompts.
    Step "Pi: restart ftesurf@1..5"
    $failed = @()
    foreach ($l in $lobbies) {
        $i = $l.Unit                    # same list step 1 demanded a row for
        $r = PiNative 'ssh' ($sshOpts + @($PiHost, "sudo -n /usr/bin/systemctl restart ftesurf@$i"))
        if ($r.Code -eq 0) {
            Ok "ftesurf@$i restarted"
        } else {
            $failed += $i
            $why = ($r.Out -join ' ').Trim()
            Write-Host "    ftesurf@$i FAILED (exit $($r.Code)): $why" -ForegroundColor Red
            if ($why -match 'password is required') {
                Write-Host "      no NOPASSWD grant for ftesurf@$i on the Pi -- see surfd\surfd-admin.sudoers" -ForegroundColor Red
            }
        }
    }
    if ($failed.Count -gt 0) {
        throw ("the new progs are live on the Pi, but ftesurf@{0} did not restart and will run the old ones until it restarts or rotates" -f
               ($failed -join ', ftesurf@'))
    }
    Ok "all five lobbies restarted on this build"
}

Step "Done"
Ok "qwprogs.dat  $((Get-Item "$SurfDir\ftesurf\qwprogs.dat").Length) bytes"
Ok "csprogs.dat  $((Get-Item "$SurfDir\ftesurf\csprogs.dat").Length) bytes"

if ($Run) {
    Step "Launching"
    Start-Process -FilePath "$SurfDir\ftesurf64.exe" -WorkingDirectory $SurfDir
}
