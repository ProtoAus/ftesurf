<#
  The six-hourly map sweep.  Registered as the scheduled task "FTESurf map scan"
  (see the REGISTER block at the bottom for the exact command that made it).

  WHY THIS RUNS ON WINDOWS AND NOT ON THE PI, which is the box that is actually
  always on: mapscan.py leans on maproster.py, and maproster hashes the BUILD
  THIS INSTALL WOULD LOAD out of the two Steam installs.  Those live here.  The
  Pi has the maps but not the catalogue tooling, so a sweep there could tell you
  what it is serving and not what exists to be served.

  The cost of that choice is honest and worth writing down: if this machine is
  off at the six hour mark the sweep is simply missed.  Nothing accumulates and
  nothing is lost -- the next run compares against the same mapseen.txt and
  picks up every name that appeared in between -- but "new" then means "new
  since the last time this PC was on", not "new within six hours".

  The log is truncated per run rather than appended: the interesting output is
  ~15 lines and the previous run's copy is the only history worth keeping.  A
  run that fails leaves its error in the same place.
#>

$ErrorActionPreference = 'Stop'

$Repo = Split-Path -Parent $PSScriptRoot
$Log  = Join-Path $Repo 'ftesurf\data\mapscan.log'

# --no-fetch is NOT passed: the network refresh is the entire point of a sweep.
# maproster's own hash cache is keyed on (size, mtime), so the expensive part
# only re-reads maps that actually changed.
try {
    Set-Location $Repo
    "=== $(Get-Date -Format o) ===" | Out-File -FilePath $Log -Encoding utf8
    & python (Join-Path $Repo 'tools\mapscan.py') --go *>&1 |
        Out-File -FilePath $Log -Encoding utf8 -Append
    "=== exit $LASTEXITCODE ===" | Out-File -FilePath $Log -Encoding utf8 -Append
    exit $LASTEXITCODE
}
catch {
    "=== FAILED: $_ ===" | Out-File -FilePath $Log -Encoding utf8 -Append
    exit 1
}

<#
REGISTER (run once, as the user -- no admin needed for a per-user task):

  $a = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument '-NoProfile -ExecutionPolicy Bypass -File C:\FTESurf\tools\mapscan_6h.ps1'
  $t = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(7) `
        -RepetitionInterval (New-TimeSpan -Hours 6)
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)
  Register-ScheduledTask -TaskName 'FTESurf map scan' -Action $a -Trigger $t -Settings $s

-StartWhenAvailable is the one that matters: without it a sweep missed because
the machine was asleep is skipped entirely rather than run on the next wake.

UNREGISTER:
  Unregister-ScheduledTask -TaskName 'FTESurf map scan' -Confirm:$false
#>
