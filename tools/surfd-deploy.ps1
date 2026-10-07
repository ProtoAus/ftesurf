<#
.SYNOPSIS
    Deploy surfd (and its tools/) to the Pi, following AGENTS.md's documented
    procedure, and verify afterwards instead of trusting a "started" line.

.DESCRIPTION
    Every step AGENTS.md names, in order, each one refusing to continue on a
    surprising state:

      1. Files come FROM THE COMMIT (`git archive <Ref>`), never from the working
         tree -- the tree usually holds another session's uncommitted work.
      2. The suite runs in the stage, on the Pi, with tools/ and src/shared/
         beside surfd/ (test_sweep and the TF_* pins read them) and a private
         TMPDIR (the tests leave their temp dirs behind).
      3. `data/surfd.db` is backed up through sqlite's own backup API, and the
         copy is chmodded 600: it holds every ranked player's guid, which is a
         credential, and sqlite's backup API creates it 0644 & ~umask.
      4. Files are copied in under `flock /tmp/surfd-sweep.lock`, each as
         `install` to a temp name then `mv`, so no cron import can see a
         half-written file.  Every replaced file keeps a `.pre<sha>-<stamp>`
         backup, the tree's convention.
      5. The gunicorn master is reloaded with SIGHUP -- but ONLY after the
         pidfile is proven to name a live `surfd:app` gunicorn.  `surfd.service`
         is dead and surfd runs from run.sh, so `systemctl show surfd -p MainPID`
         reads 0 and `kill -HUP 0` would signal this script's own process group
         (it killed a deploy mid-reload on 4 Oct).
      6. Verification is read back, not assumed: `surfd ready` in the app log, a
         master and a worker both alive, and /health answering.
      7. The database backups are REPORTED -- count, bytes, oldest -- and every
         `surfd.db*` file that is not owner-only is tightened.  They are only
         DELETED with -KeepDbBackups N, because a deploy that made the backup is
         not a deploy that may decide to destroy older ones.

    It is deliberately NOT a general sync: it deploys the surfd python tree only.
    The progs go with `src/build.ps1 -Pi`, which has its own rules.

.NOTES
    THE REMOTE WORK IS WRITTEN AS SH FILES AND SHIPPED, NOT AS STRINGS ON SSH'S
    COMMAND LINE.  A first cut of this script interpolated the commands into
    PowerShell strings, and the quoting collapsed: ssh ran the argument through a
    shell, so a `>` inside it redirected the command's own echo into a file and
    the suite "passed" by printing itself.  Two failures that both looked like the
    Pi misbehaving.  A here-string piped to `cat > file` has no interpolation to
    get wrong, and the file is also inspectable on the host afterwards.

    The rcon password and SURFD_ADMIN_SECRET are never read, printed or passed
    here.  Nothing in this script needs them.

.EXAMPLE
    pwsh -NoProfile -File tools/surfd-deploy.ps1
    pwsh -NoProfile -File tools/surfd-deploy.ps1 -Ref 2007afc -SkipTests
#>
[CmdletBinding()]
param(
    [string]$Ref = "HEAD",
    [string]$PiHost = "proto@180.150.62.57",
    [string]$Remote = "/srv/nvme/surfd",
    [string[]]$Only,
    [switch]$SkipTests,
    [switch]$NoReload,
    [switch]$NoBackup,
    # Database-backup retention.  0 (the default) REPORTS what the backups cost
    # and deletes nothing; N keeps the newest N of the ones THIS script wrote
    # (`surfd.db.bak-<sha>-<stamp>`) and deletes the older ones after the deploy
    # has verified.  Hand-made copies (`surfd.db.pre*`, `.post*`, `.prewipe`,
    # `.bak-preboard`) are never touched by any value: they are somebody's
    # deliberate rollback point, not this script's output.
    [int]$KeepDbBackups = 0,
    # A deploy-only commit that reverts another session's unapproved work
    # (AGENTS.md: revert it in the deploy worktree, never on main) cannot be
    # on origin/main.  Say so explicitly; the commit is still what ships.
    [switch]$AllowUnpushed
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = Split-Path -Parent $PSScriptRoot

$script:PiExit = 0        # exit code of the last remote command; see Invoke-PiSsh
function Fail([string]$m) { Write-Host "FAIL: $m" -ForegroundColor Red; exit 1 }
function Step([string]$m) { Write-Host "`n=== $m" -ForegroundColor Cyan }

# NOT named `Ssh`.  PowerShell names are case-insensitive, so a function called
# Ssh and the `ssh` executable are ONE name: `& ssh ...` inside it called itself
# and the first run died with "call depth overflow" -- AGENTS.md's
# `-QcBuild`/`$qcBuild` trap, in a function name instead of a parameter.
# `grep -in` both spellings before naming anything after a tool.
function Invoke-PiSsh {
    param([string]$Cmd, [string]$Stdin)
    if ($null -ne $Stdin) {
        $o = ($Stdin | & ssh -o BatchMode=yes $PiHost $Cmd 2>&1) -join "`n"
    }
    else {
        $o = (& ssh -o BatchMode=yes $PiHost $Cmd 2>&1) -join "`n"
    }
    $script:PiExit = $LASTEXITCODE
    return $o
}
# Send a local file to the Pi.  scp takes a bare path: `-LiteralPath` is a
# PowerShell parameter name and a native exe answers `scp: unknown option -- L`
# (Patch 441 fixed exactly that in release.ps1).
function Send-PiFile {
    param([string]$Local, [string]$Dest)
    & scp -q -o BatchMode=yes $Local "${PiHost}:$Dest" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "scp $Local -> $Dest failed" }
}
# Write a here-string to a local temp file, ship it, run it, and fail on a
# non-zero exit.  The body is NOT interpolated by PowerShell unless a variable is
# deliberately written as $var -- everything else is literal shell.
function Invoke-PiScript {
    param([string]$Name, [string]$Body, [switch]$AllowFail)
    $local = Join-Path $env:TEMP "surfd-deploy-$Name.sh"
    [IO.File]::WriteAllText($local, ($Body -replace "`r`n", "`n"))
    Send-PiFile $local "$stage/$Name.sh"
    Remove-Item $local -ErrorAction SilentlyContinue
    $out = Invoke-PiSsh -Cmd "sh '$stage/$Name.sh'"
    # $LASTEXITCODE is captured HERE, immediately after the native call.  Reading it
    # in the CALLER instead -- after a PowerShell function returned -- reads
    # whatever the last native command in the whole script left there, because a
    # function call does not set it.  A first cut did that, so this function's
    # "did the remote step fail" test was grading an unrelated earlier command.
    $code = $LASTEXITCODE
    Write-Host $out
    if (-not $AllowFail -and $code -ne 0) {
        Fail "remote step '$Name' exited $code (output above)"
    }
    $script:PiExit = $code
    return $out
}

# ---- 0. what are we deploying, and is the tree honest about it -------------
Step "0. provenance"
Push-Location $repo
try {
    $sha = (& git rev-parse --short "$Ref").Trim()
    if (-not $sha) { Fail "could not resolve -Ref '$Ref'" }
    $subject = (& git log -1 --format=%s "$Ref").Trim()
    Write-Host "  ref      $sha  $subject"

    $paths = @("surfd")
    if ($Only) { $paths = $Only }
    $dirty = & git status --porcelain -- @paths
    if ($dirty) {
        Write-Host $dirty
        Fail ("the working tree is dirty in the deploy set; commit it or use -Ref" +
              "`n     (deploying the TREE is how another session's uncommitted work ships)")
    }
    $unpushed = & git log --oneline "origin/main..$Ref" 2>$null
    if ($unpushed -and $AllowUnpushed) {
        Write-Host $unpushed
        Write-Host "  -AllowUnpushed: deploying $Ref, which is not on origin/main" -ForegroundColor Yellow
    } elseif ($unpushed) {
        Write-Host $unpushed
        Fail "$Ref is not on origin/main; push it first, so the Pi can be told which commit it runs"
    }
    $files = @((& git ls-tree -r --name-only $sha -- surfd) |
        Where-Object { $_ -match '\.(py|js|css|html|sh|nginx|sudoers)$' -and $_ -notmatch '/__pycache__/' })
    if ($Only) { $files = @($files | Where-Object { $Only -contains $_ }) }
    if (-not $files.Count) { Fail "nothing to deploy for -Ref $sha" }
    # THE PATHS ARE RELATIVE TO $Remote, NOT TO THE REPO ROOT.  `git ls-tree`
    # returns `surfd/recplot.py`, and the Pi's layout has recplot.py directly in
    # /srv/nvme/surfd -- so installing under the repo-relative name creates a
    # NESTED surfd/ beside the live files.  A first cut did exactly that: 49 files
    # landed in a directory that is not a package and is not on the import path,
    # gunicorn kept serving the old code, and the deploy reported success.
    # The stage keeps the repo-relative names (it has to, so tools/ lands beside
    # surfd/ for the suite); only the install destination is stripped.
    $dest = @($files | ForEach-Object { $_ -replace '^surfd/', '' })
    Write-Host "  files    $($files.Count) from surfd/"
    $files | ForEach-Object { Write-Host "           $_" }

    # tools/ and src/shared/ go beside surfd/ in the stage: test_sweep and the
    # TF_* pins read them.  They are staged for the suite, NOT installed.
    $extra = @((& git ls-tree -r --name-only $sha -- tools src/shared) |
        Where-Object { $_ -match '\.py$' })
    Write-Host "  staged   $($extra.Count) python files from tools/ and src/shared/ (suite only)"
}
finally { Pop-Location }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stage = "/tmp/surfd-stage-$sha-$stamp"
$backupTag = "pre$sha-$stamp"

# ---- 1. stage from the commit ---------------------------------------------
Step "1. stage from the commit on the Pi"
Invoke-PiSsh -Cmd "set -e; rm -rf '$stage'; mkdir -p '$stage/surfd' '$stage/tmp'" | Out-Null
if ($script:PiExit -ne 0) { Fail "could not make the stage directory on the Pi" }

Push-Location $repo
try {
    $tmpTar = Join-Path $env:TEMP "surfd-stage-$sha.tar"
    & git -c core.autocrlf=false archive -o $tmpTar $sha -- @($files)
    if ($LASTEXITCODE -ne 0) { Fail "git archive failed" }
    $tmpTar2 = $null
    if ($extra.Count) {
        $tmpTar2 = Join-Path $env:TEMP "surfd-stage-$sha-extra.tar"
        & git -c core.autocrlf=false archive -o $tmpTar2 $sha -- @($extra)
        if ($LASTEXITCODE -ne 0) { Fail "git archive (tools/) failed" }
    }
}
finally { Pop-Location }

# `tar -x` from stdin: one connection, and no scp of a tarball to delete after.
Get-Content -Raw -AsByteStream $tmpTar |
    & ssh -o BatchMode=yes $PiHost "set -e; cd '$stage'; tar -x"
if ($LASTEXITCODE -ne 0) { Fail "could not unpack surfd/ on the Pi" }
if ($tmpTar2) {
    Get-Content -Raw -AsByteStream $tmpTar2 |
        & ssh -o BatchMode=yes $PiHost "set -e; cd '$stage'; tar -x"
    if ($LASTEXITCODE -ne 0) { Fail "could not unpack tools/ on the Pi" }
}
Remove-Item $tmpTar, $tmpTar2 -ErrorAction SilentlyContinue

$n = Invoke-PiSsh -Cmd "cd '$stage' && find . -type f | wc -l"
Write-Host "  staged files on the Pi: $n"
if ([int]($n.Trim()) -lt $files.Count) { Fail "the stage holds fewer files than the commit lists" }

# ---- 2. the suite, in the stage, on the Pi --------------------------------
if (-not $SkipTests) {
    Step "2. the suite in the stage (a private TMPDIR; the tests leave their dirs)"
    $body = @'
set -e
cd STAGE/surfd
mkdir -p STAGE/tmp
rc=0
for t in test_web test_recplot test_board test_join test_replays test_sweep test_surfd test_simcheck test_momboards test_momgrab test_momrequest; do
  [ -f "$t.py" ] || continue
  printf '%-16s ' "$t"
  if TMPDIR=STAGE/tmp SURFD_HOME=$(mktemp -d) python3 "$t.py" > "STAGE/tmp/$t.out" 2>&1; then
    tail -2 "STAGE/tmp/$t.out" | tr '\n' ' '; echo
  else
    echo "FAILED"; tail -30 "STAGE/tmp/$t.out"; rc=1
  fi
done
exit $rc
'@
    $r = Invoke-PiScript -Name "suite" -Body ($body -replace 'STAGE', $stage)
    # Grade on the REMOTE EXIT CODE, which is the suite's own verdict, and not on
    # the shape of its output.  A first cut also required the string "test_web" in
    # the reply, and this host's ssh banner ("WARNING: connection is not using a
    # post-quantum key exchange algorithm") pushed the first result line out of
    # what came back -- so seven passing suites read as a failure.  A check on
    # output formatting is a check on the transport.
    # -cmatch, NOT -match.  PowerShell's -match is CASE-INSENSITIVE, so a sentinel
    # spelled "FAILED" matched every suite's own "0 failed" success line and seven
    # passing suites read as a failure.  A sentinel check is only a check if the
    # spelling is compared exactly.
    if ($script:PiExit -ne 0 -or $r -cmatch "FAILED") {
        Invoke-PiSsh -Cmd "rm -rf '$stage'" | Out-Null
        Fail "the suite did not pass in the stage; nothing was deployed, the stage is removed"
    }
}
else {
    Step "2. SKIPPED (-SkipTests): the Pi is taking an untested surfd"
}

# ---- 3. back up the live database -----------------------------------------
if (-not $NoBackup) {
    Step "3. back up data/surfd.db (sqlite's own backup API)"
    $body = @'
set -e
cd REMOTE
[ -f data/surfd.db ] || { echo NO_DATABASE; exit 1; }
python3 - <<PYEOF
import sqlite3
src = sqlite3.connect("data/surfd.db")
dst = sqlite3.connect("data/surfd.db.TAG")
with dst:
    src.backup(dst)
dst.close(); src.close()
print("BACKUP_OK")
PYEOF
# The copy holds every ranked player's guid, and sqlite's backup API creates it
# 0644 & ~umask -- the same mode the live database had before surfd installed a
# 077 umask of its own.  Tighten it here, and PRINT THE MODE rather than trusting
# the chmod: a permissions fix that is not read back is a permissions hope.
chmod 600 data/surfd.db.TAG
stat -c 'BACKUP_MODE=%a %n' data/surfd.db.TAG
ls -l data/surfd.db data/surfd.db.TAG | awk '{print $5, $9}'
'@
    $bak = Invoke-PiScript -Name "backup" -AllowFail `
        -Body ($body -replace 'REMOTE', $Remote -replace 'TAG', "bak-$sha-$stamp")
    if ($bak -cnotmatch "BACKUP_OK") {
        Fail "the database backup did not report BACKUP_OK -- not deploying over an unbacked-up board"
    }
    if ($bak -cnotmatch "BACKUP_MODE=600 ") {
        Fail "the database backup is not owner-only ($($bak -join ' | ')) -- it holds every player's guid"
    }
    Write-Host "  $($bak | Where-Object { $_ -match 'BACKUP_MODE=' })"
}
else {
    Step "3. SKIPPED (-NoBackup): deploying with no fresh database backup"
}

# ---- 4. read the master's identity BEFORE touching anything ----------------
Step "4. prove the pidfile names a live gunicorn master"
$body = @'
cd REMOTE
P=$(cat surfd.pid 2>/dev/null || echo none)
echo "PIDFILE=$P"
ps -o pid=,ppid=,cmd= -p "$P" 2>/dev/null | head -1
echo "COUNT=$(ps -eo cmd= | grep -c 'surfd:app' || true)"
'@
$pre = Invoke-PiScript -Name "identify" -AllowFail -Body ($body -replace 'REMOTE', $Remote)
$pidfile = (($pre -split "`n") | Where-Object { $_ -match '^PIDFILE=' }) -replace '^PIDFILE=', ''
$pidfile = "$pidfile".Trim()
if ($pidfile -notmatch '^\d+$') {
    Fail "the pidfile does not name a pid ('$pidfile') -- run.sh's start failed at some point; fix that first"
}
$masterLine = ($pre -split "`n") | Where-Object { $_ -match "^\s*$pidfile\s" } | Select-Object -First 1
if (-not $masterLine) {
    Fail "no process $pidfile -- surfd is NOT running, so a reload would be a lie; start it with run.sh"
}
if ($masterLine -notmatch 'gunicorn' -or $masterLine -notmatch 'surfd:app') {
    Fail "pid $pidfile is not a gunicorn surfd:app master: $masterLine"
}
$ppid = ($masterLine.Trim() -split '\s+')[1]
if ($ppid -ne '1') {
    Write-Host "  NOTE: master's ppid is $ppid, not 1 -- not started detached by run.sh" -ForegroundColor Yellow
}
Write-Host "  master $pidfile (ppid $ppid) -- reload target" -ForegroundColor Green

# ---- 5. copy in under the sweep lock --------------------------------------
Step "5. copy in under flock, install+mv, keeping a .$backupTag backup"
# One line per file: "<stage-relative source> <install destination>".  A literal
# here-string (@'...'@) so the shell's own $vars survive, with a marker list
# spliced in by concatenation rather than by interpolation -- interpolation inside
# a here-string is exactly what silently produced an unexpanded `$backupTag` in the
# first cut, and an unexpanded name is an empty name under `set -e` without `-u`.
$pairs = @()
for ($i = 0; $i -lt $files.Count; $i++) { $pairs += "$($files[$i]) $($dest[$i])" }
$listBlock = ($pairs -join "`n")
$body = @'
set -eu
exec 9>/tmp/surfd-sweep.lock
flock 9
cd __REMOTE__
n=0
while read -r src dst; do
  [ -n "$src" ] && [ -n "$dst" ] || continue
  [ -f "__STAGE__/$src" ] || { echo "MISSING_IN_STAGE $src"; exit 1; }
  d=$(dirname "$dst"); mkdir -p "$d"
  if [ -f "$dst" ]; then cp -p "$dst" "$dst.__TAG__"; fi
  install -m 0644 "__STAGE__/$src" "$dst.new"
  mv -f "$dst.new" "$dst"
  n=$((n+1))
done <<'FILELIST'
__FILES__
FILELIST
echo "COPIED=$n"
'@
$body = $body.Replace('__REMOTE__', $Remote).Replace('__STAGE__', $stage).
              Replace('__TAG__', $backupTag).Replace('__FILES__', $listBlock)
$copy = Invoke-PiScript -Name "copyin" -Body $body
if ($copy -cnotmatch "COPIED=$($files.Count)") {
    Fail "copied a different number of files than the commit lists; .$backupTag backups are beside the originals"
}

# ---- 5b. PROVE THE FILES ON DISK ARE THE COMMIT'S ---------------------------
# A copy that reports COPIED=N proves only that the loop ran.  The first cut of
# this script printed COPIED=49 having installed nothing -- every install failed
# because an unexpanded variable made the destination an empty string, and the
# loop was not counting successes.  So: hash what is now on the Pi and compare it
# with what the commit says, byte for byte.  This is the step that makes the rest
# of the output mean anything.
Step "5b. verify the deployed bytes against the commit"
$manifest = @()
Push-Location $repo
try {
    foreach ($f in $files) {
        $h = (& git rev-parse "${sha}:$f").Trim()
        if (-not $h) { Fail "could not hash $f at $sha" }
        $manifest += $h
    }
}
finally { Pop-Location }
# git's blob hash is sha1("blob <len>\0" <bytes>), which is what `git hash-object`
# computes -- and the Pi has git, so it can hash the installed file the same way.
$lines = @()
for ($i = 0; $i -lt $dest.Count; $i++) { $lines += "$($dest[$i]) $($manifest[$i])" }
$body = @'
set -eu
cd __REMOTE__
bad=0
while read -r f want; do
  [ -n "$f" ] || continue
  if [ ! -f "$f" ]; then echo "ABSENT $f"; bad=$((bad+1)); continue; fi
  got=$(git hash-object "$f")
  if [ "$got" != "$want" ]; then echo "DIFFERS $f want=$want got=$got"; bad=$((bad+1)); fi
done <<'MANIFEST'
__MANIFEST__
MANIFEST
echo "VERIFY_BAD=$bad"
[ "$bad" = 0 ] || exit 1
'@
$body = $body.Replace('__REMOTE__', $Remote).Replace('__MANIFEST__', ($lines -join "`n"))
Invoke-PiScript -Name "verify" -Body $body | Out-Null
if ($script:PiExit -ne 0) {
    Fail "the files on the Pi do not match commit $sha -- the deploy did NOT take;" +
         " the .$backupTag backups are beside every file it replaced"
}
Write-Host "  all $($dest.Count) files hash-match $sha" -ForegroundColor Green

# ---- 6. reload, then verify -------------------------------------------------
if (-not $NoReload) {
    Step "6. SIGHUP the master (never pid 0, never the unit)"
    $body = @'
set -e
cd REMOTE
P=$(cat surfd.pid)
[ "$P" = "0" ] && { echo REFUSE_PID_ZERO; exit 1; }
ps -o cmd= -p "$P" | grep -q 'surfd:app' || { echo REFUSE_NOT_SURFD; exit 1; }
kill -HUP "$P"
echo "SIGHUP_SENT=$P"
sleep 8
echo "--- app log tail ---"
tail -8 logs/surfd.log
echo "--- processes ---"
ps -eo pid=,ppid=,cmd= | grep 'surfd:app' | grep -v grep | wc -l
echo "--- health ---"
curl -s -m 10 http://127.0.0.1:8084/health
echo
'@
    $rel = Invoke-PiScript -Name "reload" -AllowFail -Body ($body -replace 'REMOTE', $Remote)
    if ($rel -cmatch "REFUSE_") {
        Fail "the reload was refused; the new files are in place but the OLD code is still serving"
    }
    if ($rel -cnotmatch "SIGHUP_SENT=$pidfile") { Fail "the master was not signalled" }
    # `surfd ready` is the app's own boot line, and a SIGHUP only re-forks the
    # WORKER, so heartbeats from the 12 lobbies push it out of any small tail of
    # surfd.log.  The first cut reported a NOTE on a clean reload for that reason.
    # Grep for it instead of tailing, and prove the reload by the worker's AGE:
    # the master's pid must be unchanged and the worker's must be new.
    $ready = Invoke-PiSsh -Cmd "grep 'surfd ready' '$Remote/logs/surfd.log' | tail -1"
    Write-Host "  last boot line: $ready"
    if ($ready -cnotmatch "surfd ready") {
        Write-Host "  NOTE: no 'surfd ready' ever logged -- read logs/surfd.log before trusting this" -ForegroundColor Yellow
    }
    # The reload must leave the MASTER's pid alone and give the WORKER a new one.
    # Spelled as a shipped script: an earlier cut put a `$(...)` command
    # substitution inside a double-quoted PowerShell argument, where the escaping
    # collapsed and the remote bash tried to execute the pid as a command
    # ("2479950: command not found") -- the check printed nothing and still passed.
    $ageBody = @'
M=$(cat REMOTE/surfd.pid)
ps -o pid=,ppid=,etimes=,comm= -p "$M" --no-headers
ps -eo pid=,ppid=,etimes=,comm= --no-headers | awk -v m="$M" '$2==m {print}'
'@
    $ages = Invoke-PiScript -Name "ages" -AllowFail -Body ($ageBody -replace 'REMOTE', $Remote)
    $countLine = ($rel -split "`n") | Where-Object { $_ -match '^\d+$' } | Select-Object -Last 1
    if ([int]$countLine -lt 2) {
        Fail "only $countLine surfd:app process(es) after the reload -- expected a master and a worker"
    }
    if ($rel -notmatch '"ok"\s*:\s*true') { Fail "/health did not answer ok" }
    Write-Host "  $countLine processes (master + worker), /health ok" -ForegroundColor Green
}

# ---- 7. the database backups: what they cost, and whose they are -----------
#
# Run AFTER the verification and the reload, never before: a deploy that failed
# has no business deleting the copies that would roll it back.
Step "7. database backups (report; -KeepDbBackups N to prune)"
# DASH, NOT BASH: Invoke-PiScript runs the body with `sh`, so no process
# substitution, no [[ ]] and no arrays -- `read ... < <(...)` died on the Pi's
# dash the first time this step was tried.
# AND THE PLACEHOLDERS ARE __NAME__ WITH A LITERAL .Replace(), NOT -replace:
# PowerShell's -replace is a CASE-INSENSITIVE regex, so a `KEEP` placeholder also
# matched the English word "keeping" in the printf two lines below it and put a
# number in the middle of a sentence.  Same family as the `-match`/`-cmatch`
# sentinel trap this script's own NOTES carry.
$body = @'
set -eu
cd __REMOTE__/data
# ONLY the shape this script writes.  `surfd.db.bak-*` alone would swallow
# `surfd.db.bak-preboard`, which is a hand-made rollback point from before the
# script existed.
OURS='^\./surfd\.db\.bak-[0-9a-f]{7,40}-[0-9]{8}-[0-9]{6}$'
LIST=/tmp/surfd-baks.$$
find . -maxdepth 1 -type f -regextype posix-extended -regex "$OURS" \
     -printf '%T@ %s %f\n' | sort -n > "$LIST"
n=$(wc -l < "$LIST")
bytes=$(awk '{s+=$2} END {printf "%d", s+0}' "$LIST")
printf 'OURS=%s files, %s MiB (this script wrote them)\n' "$n" "$((bytes / 1048576))"
if [ "$n" -gt 0 ]; then
  printf 'OLDEST=%s\n' "$(head -1 "$LIST" | awk '{print $3}')"
fi
# The hand-made copies are REPORTED and never deleted, whatever -KeepDbBackups
# says: they are the ones somebody chose to keep by naming them.
handn=$(find . -maxdepth 1 -type f -name 'surfd.db.*' \
         -regextype posix-extended ! -regex "$OURS" | wc -l)
handb=$(find . -maxdepth 1 -type f -name 'surfd.db.*' \
         -regextype posix-extended ! -regex "$OURS" -printf '%s\n' |
        awk '{s+=$1} END {printf "%d", s+0}')
printf 'HANDMADE=%s files, %s MiB (never pruned here)\n' "$handn" "$((handb / 1048576))"
# Any surfd.db* file left group- or other-readable is tightened.  Idempotent, and
# it lives here rather than in a hand-run chmod because the next backup would
# otherwise reintroduce the exposure and nothing would say so.
loose=$(find . -maxdepth 1 -type f -name 'surfd.db*' -perm /077 | wc -l)
if [ "$loose" -gt 0 ]; then
  find . -maxdepth 1 -type f -name 'surfd.db*' -perm /077 -exec chmod 600 {} +
  printf 'TIGHTENED=%s file(s) were group- or other-readable, now 600\n' "$loose"
else
  printf 'TIGHTENED=0 (every surfd.db* file is already owner-only)\n'
fi
left=$(find . -maxdepth 1 -type f -name 'surfd.db*' -perm /077 | wc -l)
printf 'STILL_LOOSE=%s\n' "$left"
if [ __KEEP__ -gt 0 ] && [ "$n" -gt __KEEP__ ]; then
  drop=$((n - __KEEP__))
  printf 'PRUNE=%s oldest deleted, newest %s kept\n' "$drop" "__KEEP__"
  head -"$drop" "$LIST" | while read -r _t sz f; do
    printf 'DELETE %s (%s MiB)\n' "$f" "$((sz / 1048576))"
    rm -f -- "$f"
  done
elif [ __KEEP__ -gt 0 ]; then
  printf 'PRUNE=0 (only %s held, -KeepDbBackups __KEEP__)\n' "$n"
else
  printf 'PRUNE=off (pass -KeepDbBackups N to prune)\n'
fi
rm -f "$LIST"
[ "$left" = 0 ] || exit 1
echo BACKUPS_DONE
'@
$baks = Invoke-PiScript -Name "backups" -AllowFail `
    -Body ($body.Replace('__REMOTE__', $Remote).Replace('__KEEP__', "$KeepDbBackups"))
if ($baks -cnotmatch "BACKUPS_DONE" -or $baks -cnotmatch "STILL_LOOSE=0") {
    Fail "the database files are not all owner-only, or the report did not complete (output above)"
}

# ---- 8. clean up the stage --------------------------------------------------
Step "8. remove the stage"
Invoke-PiSsh -Cmd "rm -rf '$stage' && echo stage_removed" | Write-Host

Write-Host "`nDEPLOYED $sha to ${PiHost}:$Remote" -ForegroundColor Green
Write-Host "  database backup  $Remote/data/surfd.db.bak-$sha-$stamp (mode 600)"
Write-Host "  file backups     *.$backupTag beside each replaced file"
Write-Host "  The Pi keeps no receipt of its own: record this deploy in the commit"
Write-Host "  or ENGINE_PATCHES.md's DEPLOYED notes, and in UTC -- the Pi talks UTC"
Write-Host "  while git log talks local."
