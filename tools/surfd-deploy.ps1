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
         half-written file. Git executable modes are installed and verified.
         Every replaced file keeps a `.pre<sha>-<stamp>-<nonce>`
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

    It is deliberately NOT a general sync: it deploys the surfd tree and the two
    allowlisted KSF codecs under tools/. A KSF -Only selection expands to the
    matched app/importer/codec ship-set. The progs go with `src/build.ps1 -Pi`.
    -PlanOnly prints the exact commit, source/destination pairs and test-stage
    manifest locally; it performs no SSH, installation or scratch creation.

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
    [switch]$PlanOnly,
    [switch]$SkipTests,
    [switch]$NoReload,
    [switch]$NoBackup,
    # Database-backup retention.  0 (the default) REPORTS what the backups cost
    # and deletes nothing; N keeps the newest N of the ones THIS script wrote
    # (`surfd.db.bak-<sha>-<stamp>[-<nonce>]`) and deletes the older ones after the deploy
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
. (Join-Path $PSScriptRoot 'surfd-deploy-plan.ps1')
try { $plan = Get-SurfdDeployPlan -Repo $repo -Ref $Ref -Only $Only }
catch { Write-Error $_; exit 1 }
if ($PlanOnly) { $plan | ConvertTo-Json -Depth 4; exit 0 }

$script:PiExit = 0        # exit code of the last remote command; see Invoke-PiSsh
function Fail([string]$m) {
    Write-Host "FAIL: $m" -ForegroundColor Red
    if (Get-Variable -Name work -ErrorAction SilentlyContinue) {
        Write-Host "  retained local ownership/plan: $work"
        Write-Host "  remote owned stage (if created): $stage"
    }
    exit 1
}
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
    $local = Join-Path $work "surfd-deploy-$Name.sh"
    [IO.File]::WriteAllText($local, ($Body -replace "`r`n", "`n"))
    Send-PiFile $local "$stage/$Name.sh"
    Remove-Item $local -ErrorAction SilentlyContinue
    $out = Invoke-PiSsh -Cmd "sh '$stage/$Name.sh'"
    # Invoke-PiSsh captured its native exit status immediately. Use that saved
    # status, not a caller's LASTEXITCODE from a different earlier command.
    $code = $script:PiExit
    if (Get-Variable -Name DeployLock -Scope Script -ErrorAction SilentlyContinue) {
        Assert-DeployLock
    }
    Write-Host $out
    if (-not $AllowFail -and $code -ne 0) {
        Fail "remote step '$Name' exited $code (output above)"
    }
    $script:PiExit = $code
    return $out
}

# The remote holder outlives individual step SSH sessions. Never unlink its lock.
function Read-DeployLockLine {
    param([System.Diagnostics.Process]$Holder, [int]$TimeoutMs = 20000)
    $line = $Holder.StandardOutput.ReadLineAsync()
    if (-not $line.Wait($TimeoutMs)) { throw 'deployment lock handshake timed out' }
    return $line.GetAwaiter().GetResult()
}
function Assert-DeployLock {
    param([string]$Token = [guid]::NewGuid().ToString('N'))
    if ($script:DeployLock.HasExited) { throw 'deployment transaction lock holder exited' }
    $script:DeployLock.StandardInput.WriteLine($token)
    $script:DeployLock.StandardInput.Flush()
    if ((Read-DeployLockLine $script:DeployLock) -cne "LOCK_ACK=$token") {
        throw 'deployment transaction lock acknowledgment lost; no receipt accepted'
    }
}

# ---- 0. what are we deploying, and is the tree honest about it -------------
Step "0. provenance"
Push-Location $repo
try {
    $commit = $plan.Commit
    $sha = $commit.Substring(0, 12)
    $subject = (& git log -1 --format=%s $commit).Trim()
    Write-Host "  ref      $sha  $subject"

    $paths = $plan.Files
    $dirty = & git status --porcelain -- @paths
    if ($dirty) {
        Write-Host $dirty
        Fail ("the working tree is dirty in the deploy set; commit it or use -Ref" +
              "`n     (deploying the TREE is how another session's uncommitted work ships)")
    }
    $unpushed = & git log --oneline "origin/main..$commit" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Fail "could not establish publication against origin/main; fetch and inspect the ref first"
    }
    if ($unpushed -and $AllowUnpushed) {
        Write-Host $unpushed
        Write-Host "  -AllowUnpushed: deploying $Ref, which is not on origin/main" -ForegroundColor Yellow
    } elseif ($unpushed) {
        Write-Host $unpushed
        Fail "$Ref is not on origin/main; push it first, so the Pi can be told which commit it runs"
    }
    $files = $plan.Files
    $stageFiles = $plan.StageFiles
    foreach ($f in $plan.AddedDependencies) { Write-Host "  dependency added: $f" }
    # THE PATHS ARE RELATIVE TO $Remote, NOT TO THE REPO ROOT.  `git ls-tree`
    # returns `surfd/recplot.py`, and the Pi's layout has recplot.py directly in
    # /srv/nvme/surfd -- so installing under the repo-relative name creates a
    # NESTED surfd/ beside the live files.  A first cut did exactly that: 49 files
    # landed in a directory that is not a package and is not on the import path,
    # gunicorn kept serving the old code, and the deploy reported success.
    # The stage keeps the repo-relative names (it has to, so tools/ lands beside
    # surfd/ for the suite); only the install destination is stripped.
    $dest = $plan.Destinations
    Write-Host "  files    $($files.Count) from surfd/ and allowlisted codecs"
    $files | ForEach-Object { Write-Host "           $_" }

    # Complete test dependencies are staged even for a restricted installation.
    # Only plan.Files ships: staging tools is not evidence of installing codecs.
    Write-Host "  staged   $($stageFiles.Count) app/tool/shared files for the suite"
}
finally { Pop-Location }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
# momgrab's fixture worker checks the data disk's 20 GB floor. Root /tmp can
# have only 5 GB free while NVMe has ample room; stage on the target volume.
$nonce = [guid]::NewGuid().ToString('N')
$stage = "/srv/nvme/agent-work/surfdship-$sha-$stamp-$nonce"
$work = Join-Path 'C:\FTESurf-worktrees' "surfdship-$sha-$stamp-$nonce"
# Exclusive creation before any archive/script, ownership before population.
[IO.Directory]::CreateDirectory((Split-Path -Parent $work)) | Out-Null
New-Item -ItemType Directory -Path $work -ErrorAction Stop | Out-Null
[IO.File]::WriteAllText((Join-Path $work 'OWNER.md'),
    "Owner: surfd-deploy.ps1; created UTC $([DateTime]::UtcNow.ToString('o')).`n" +
    "Source: $repo at $commit. Owned local root: $work. Remote stage: $stage.`n" +
    "Status: active; no game processes. Retain on failure; on success keep receipt and remove only owned disposable archives/scripts.`n")
$plan | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $work 'plan.json')
Write-Host "  local ownership/plan: $work"
$backupTag = "pre$sha-$stamp-$nonce"
$dbBackupTag = "bak-$sha-$stamp-$nonce"

# ---- 1. stage from the commit ---------------------------------------------
Step "1. stage from the commit on the Pi"
Invoke-PiSsh -Cmd ("set -eu; umask 077; mkdir -p '/srv/nvme/agent-work'; mkdir '$stage'; " +
    "printf '%s\n' 'Owner: surfd-deploy.ps1; commit $commit; local receipt $work; status active, retained on failure.' > '$stage/OWNER.md'; " +
    "mkdir '$stage/surfd' '$stage/tmp'") | Out-Null
if ($script:PiExit -ne 0) { Fail "could not make the stage directory on the Pi" }

Push-Location $repo
try {
    $tmpTar = Join-Path $work "surfd-stage-$sha.tar"
    & git -c core.autocrlf=false archive -o $tmpTar $commit -- @($stageFiles)
    if ($LASTEXITCODE -ne 0) { Fail "git archive failed" }
}
finally { Pop-Location }

# `tar -x` from stdin: one connection, and no scp of a tarball to delete after.
Get-Content -Raw -AsByteStream $tmpTar |
    & ssh -o BatchMode=yes $PiHost "set -e; cd '$stage'; tar -x"
if ($LASTEXITCODE -ne 0) { Fail "could not unpack surfd/ on the Pi" }
Remove-Item -LiteralPath $tmpTar -ErrorAction Stop

$n = Invoke-PiSsh -Cmd "cd '$stage' && find . -type f | wc -l"
Write-Host "  staged files on the Pi: $n"
if ([int]($n.Trim()) -lt $stageFiles.Count) { Fail "the stage holds fewer files than the commit lists" }

# ---- 2. the suite, in the stage, on the Pi --------------------------------
if (-not $SkipTests) {
    Step "2. the suite in the stage (a private TMPDIR; the tests leave their dirs)"
    $body = @'
set -e
cd STAGE/surfd
mkdir -p STAGE/tmp
# Export before command substitution: TMPDIR=x cmd $(mktemp -d) applies x
# too late to control mktemp. Every suite-created home must stay in our stage.
TMPDIR=STAGE/tmp
export TMPDIR
rc=0
for t in test_web test_recplot test_board test_join test_replays test_sweep test_surfd test_simcheck test_momboards test_momgrab test_momrequest test_accounts test_ranked test_ksfimport test_ksfprofile test_ksftopup test_ksfgrab test_mapwatch test_zonefit test_variants test_mappool; do
  [ -f "$t.py" ] || continue
  printf '%-16s ' "$t"
  if [ "$t" = test_ksfgrab ]; then
    set -- --out "STAGE/tmp/ksfgrab"
  else
    set --
  fi
  if TMPDIR=STAGE/tmp SURFD_HOME=$(mktemp -d) python3 "$t.py" "$@" > "STAGE/tmp/$t.out" 2>&1; then
    tail -2 "STAGE/tmp/$t.out" | tr '\n' ' '; echo
  else
    echo "FAILED"; tail -30 "STAGE/tmp/$t.out"; rc=1
  fi
done
if [ -f ../tools/test_ksfconvert.py ]; then
  if TMPDIR=STAGE/tmp python3 ../tools/test_ksfconvert.py > STAGE/tmp/test_ksfconvert.out 2>&1; then
    tail -2 STAGE/tmp/test_ksfconvert.out
  else
    echo 'FAILED test_ksfconvert'; tail -30 STAGE/tmp/test_ksfconvert.out; rc=1
  fi
fi
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
        Fail "the suite did not pass; nothing was deployed, owned stage/logs retained at $stage"
    }
}
else {
    Step "2. SKIPPED (-SkipTests): the Pi is taking an untested surfd"
}

# Hold exclusion before backups until the accepted receipt, including failure paths.
$lockBody = @'
set -eu
exec 8>/tmp/surfd-deploy.lock
flock -w 120 8
printf '%s\n' LOCK_ACQUIRED
while IFS= read -r token; do
  printf 'LOCK_ACK=%s\n' "$token"
done
'@
$lockPath = Join-Path $work 'transaction-lock.sh'
[IO.File]::WriteAllText($lockPath, ($lockBody -replace "`r`n", "`n"))
Send-PiFile $lockPath "$stage/transaction-lock.sh"
$script:DeployLock = [System.Diagnostics.Process]::new()
$lockInfo = [System.Diagnostics.ProcessStartInfo]::new('ssh')
$lockInfo.UseShellExecute = $false
$lockInfo.RedirectStandardInput = $true
$lockInfo.RedirectStandardOutput = $true
$lockInfo.RedirectStandardError = $true
foreach ($arg in @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o',
                  'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=3',
                  $PiHost, "sh '$stage/transaction-lock.sh'")) {
    $lockInfo.ArgumentList.Add($arg)
}
$script:DeployLock.StartInfo = $lockInfo
$lockStarted = $false
try {
    $lockStarted = $script:DeployLock.Start()
    if (-not $lockStarted) { throw 'could not start deployment lock holder' }
    $lockErrors = $script:DeployLock.StandardError.ReadToEndAsync()
    if ((Read-DeployLockLine $script:DeployLock -TimeoutMs 150000) -cne 'LOCK_ACQUIRED') {
        throw 'deployment transaction lock was not acquired'
    }
    Assert-DeployLock

# ---- 3. back up the live database -----------------------------------------
if (-not $NoBackup) {
    Step "3. back up data/surfd.db (sqlite's own backup API)"
    $body = @'
set -e
cd REMOTE
[ -f data/surfd.db ] || { echo NO_DATABASE; exit 1; }
python3 - <<PYEOF
import os, sqlite3
fd = os.open("data/surfd.db.TAG", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(fd)
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
        -Body ($body -replace 'REMOTE', $Remote -replace 'TAG', $dbBackupTag)
    if ($script:PiExit -ne 0 -or $bak -cnotmatch "BACKUP_OK") {
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
for ($i = 0; $i -lt $files.Count; $i++) { $pairs += "$($files[$i]) $($dest[$i]) $($plan.Modes[$i])" }
$listBlock = ($pairs -join "`n")
$body = @'
set -eu
exec 9>/tmp/surfd-sweep.lock
flock 9
cd __REMOTE__
n=0
while read -r src dst mode; do
  [ -n "$src" ] && [ -n "$dst" ] || continue
  [ -f "__STAGE__/$src" ] || { echo "MISSING_IN_STAGE $src"; exit 1; }
  d=$(dirname "$dst"); mkdir -p "$d"
  case "$mode" in 644|755) ;; *) echo "REFUSE_MODE $src"; exit 1 ;; esac
  if [ -f "$dst" ]; then
    (set -C; : > "$dst.__TAG__") || { echo "REFUSE_BACKUP_EXISTS $dst"; exit 1; }
    cp -p "$dst" "$dst.__TAG__"
  fi
  install -m "$mode" "__STAGE__/$src" "$dst.new"
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
Step "5b. verify the deployed bytes and modes against the commit"
$manifest = @()
Push-Location $repo
try {
    foreach ($f in $files) {
        $h = (& git rev-parse "${commit}:$f").Trim()
        if (-not $h) { Fail "could not hash $f at $sha" }
        $manifest += $h
    }
}
finally { Pop-Location }
# git's blob hash is sha1("blob <len>\0" <bytes>), which is what `git hash-object`
# computes -- and the Pi has git, so it can hash the installed file the same way.
$lines = @()
for ($i = 0; $i -lt $dest.Count; $i++) { $lines += "$($dest[$i]) $($manifest[$i]) $($plan.Modes[$i])" }
$body = @'
set -eu
cd __REMOTE__
bad=0
while read -r f want mode; do
  [ -n "$f" ] || continue
  if [ ! -f "$f" ]; then echo "ABSENT $f"; bad=$((bad+1)); continue; fi
  actual_mode=$(stat -c '%a' -- "$f")
  if [ "$actual_mode" != "$mode" ]; then echo "MODE_DIFFERS $f want=$mode got=$actual_mode"; bad=$((bad+1)); fi
  got=$(git hash-object --no-filters -- "$f")
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
Write-Host "  all $($dest.Count) files hash/mode-match $sha" -ForegroundColor Green

# ---- 6. reload, then verify -------------------------------------------------
if (-not $NoReload) {
    Step "6. SIGHUP the master (never pid 0, never the unit)"
    # The shipped service has ONE worker and a 20s graceful timeout. Require
    # all old workers gone, one new direct child of the SAME master, that PID's
    # fresh app-ready line, and health. Historical logs/global counts cannot act.
    $body = @'
set -eu
cd __REMOTE__
P=$(cat surfd.pid)
[ "$P" = "__MASTER__" ] && [ "$P" != 0 ] || { echo REFUSE_MASTER_CHANGED; exit 1; }
master=$(ps -o cmd= -p "$P")
case "$master" in *gunicorn*surfd:app*) ;; *) echo REFUSE_NOT_SURFD; exit 1 ;; esac
workers() {
  snapshot=$(ps -eo pid=,ppid=,cmd=) || return 1
  printf '%s\n' "$snapshot" | awk -v m="$P" '$2==m && /gunicorn/ && /surfd:app/ {print $1}'
}
old=$(workers)
[ -n "$old" ] || { echo REFUSE_NO_OLD_WORKER; exit 1; }
log_id=$(stat -c '%d:%i' logs/surfd.log)
lines=$(wc -l < logs/surfd.log)
clock() { awk '{print int($1)}' /proc/uptime; }
deadline=$(($(clock)+60))
kill -HUP "$P"
echo "SIGHUP_SENT=$P"
while [ "$(clock)" -lt "$deadline" ]; do
  [ "$(cat surfd.pid)" = "$P" ] || { echo REFUSE_MASTER_CHANGED; exit 1; }
  master=$(ps -o cmd= -p "$P")
  case "$master" in *gunicorn*surfd:app*) ;; *) echo REFUSE_NOT_SURFD; exit 1 ;; esac
  now=$(workers)
  # No old direct child may still serve. Exactly one new child must remain.
  count=$(printf '%s\n' "$now" | awk 'NF {n++} END {print n+0}')
  stale=0
  for w in $now; do
    for previous in $old; do [ "$w" != "$previous" ] || stale=1; done
  done
  if [ "$count" = 1 ] && [ "$stale" = 0 ]; then
    W=$now
    # Rotation starts a fresh file; the new worker's PID still gates readiness.
    offset=$((lines+1))
    current_id=$(stat -c '%d:%i' logs/surfd.log)
    current_lines=$(wc -l < logs/surfd.log)
    if [ "$current_id" != "$log_id" ] || [ "$current_lines" -lt "$lines" ]; then offset=1; fi
    if tail -n "+$offset" logs/surfd.log | grep -F " INFO [$W] surfd ready (" >/dev/null; then
      remaining=$((deadline-$(clock)))
      [ "$remaining" -gt 0 ] || break
      timeout=$remaining
      [ "$timeout" -le 5 ] || timeout=5
      health=$(curl -fs -m "$timeout" http://127.0.0.1:8084/health) || health=''
      if printf '%s\n' "$health" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*true' &&
         [ "$(clock)" -le "$deadline" ]; then
        echo "RELOAD_VERIFIED=$P worker=$W"
        exit 0
      fi
    fi
  fi
  remaining=$((deadline-$(clock)))
  [ "$remaining" -gt 0 ] || break
  delay=$remaining
  [ "$delay" -le 2 ] || delay=2
  sleep "$delay"
done
echo REFUSE_RELOAD_TIMEOUT
exit 1
'@
    $rel = Invoke-PiScript -Name "reload" -AllowFail -Body (
        $body.Replace('__REMOTE__', $Remote).Replace('__MASTER__', $pidfile))
    if ($script:PiExit -ne 0 -or $rel -cmatch "REFUSE_") {
        Fail "reload not verified; installed files/backups and owned stage are retained; live code is unproven"
    }
    if ($rel -cnotmatch "SIGHUP_SENT=$pidfile" -or
        $rel -cnotmatch "RELOAD_VERIFIED=$pidfile worker=\d+") {
        Fail "reload did not prove the same master and a fresh ready replacement worker"
    }
    Write-Host "  same master, replacement worker ready, old workers retired, /health ok" -ForegroundColor Green
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
OURS='^\./surfd\.db\.bak-[0-9a-f]{7,40}-[0-9]{8}-[0-9]{6}(-[0-9a-f]{32})?$'
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

# This exact ACK is the point-in-time receipt, emitted remotely under flock.
# Before acceptance, retain every failed stage/log. A later disconnect or
# cleanup failure does not undo this already accepted point.
Assert-DeployLock -Token "ACCEPTED:$($commit):$nonce"

# ---- 8. success-only removal of what we staged -----------------------------
Step "8. remove the stage"
$stageState = "cleanup unconfirmed; inspect $stage"
try {
    Invoke-PiSsh -Cmd "rm -rf '$stage' && echo stage_removed" | Write-Host
    if ($script:PiExit -ne 0) { throw 'owned stage removal returned nonzero' }
    $stageState = 'removed'
}
catch {
    Write-Warning "Deployment already accepted; stage cleanup unconfirmed; inspect ${stage}: $_"
}
Add-Content -LiteralPath (Join-Path $work 'OWNER.md') -Value (
    "Accepted UTC $([DateTime]::UtcNow.ToString('o')); remote stage $stageState. " +
    "Deployment commit $commit; local plan/receipt retained; live destination/backups are NOT disposable scratch.")
Write-Host "`nDEPLOYED $commit to ${PiHost}:$Remote" -ForegroundColor Green
Write-Host "  database backup  $Remote/data/surfd.db.$dbBackupTag (mode 600)"
Write-Host "  file backups     *.$backupTag beside each replaced file"
Write-Host "  remote stage     $stageState"
Write-Host "  The Pi keeps no receipt of its own: record this deploy in the commit"
Write-Host "  or ENGINE_PATCHES.md's DEPLOYED notes, and in UTC -- the Pi talks UTC"
Write-Host "  while git log talks local."

}
finally {
    try {
        if ($lockStarted) {
            $script:DeployLock.StandardInput.Close()
            if (-not $script:DeployLock.WaitForExit(5000)) {
                Write-Warning 'owned SSH lock holder did not exit within 5s after EOF; no signal sent'
            }
        }
    }
    finally { $script:DeployLock.Dispose() }
}
