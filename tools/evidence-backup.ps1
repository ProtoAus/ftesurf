#Requires -Version 7.0
<#
Private off-box copies of EXISTING evidence. No source writes, deletes, repair,
new capture, verdict fields or guilt inference. Configuration/credentials remain
private; SSH reads existing identity/trust files. See evidence-backup.md.
#>
[CmdletBinding()]
param(
	[Parameter(Mandatory)][string]$Config,
	[switch]$Register,
	[switch]$Probe
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = $null
$safeRoot = $false
$lease = $null

function Assert-NoReparse([string]$Path) {
	$item = Get-Item -LiteralPath $Path -Force
	while ($null -ne $item) {
		if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse path refused' }
		if ($item -is [IO.DirectoryInfo]) { $item = $item.Parent } else { $item = $item.Directory }
	}
}
function Assert-Private([string]$Path, [string]$Sid, [bool]$Protected = $false) {
	$acl = Get-Acl -LiteralPath $Path
	if ($Protected -and -not $acl.AreAccessRulesProtected) { throw 'Private root must block inheritance' }
	foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
		if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin @($Sid, 'S-1-5-18')) {
			throw 'Unexpected Windows access grant'
		}
	}
}
function Assert-ManagedDirectory([string]$Path, [bool]$Create = $false) {
	$full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
	if ($full -ne $root -and -not $full.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
		throw 'Managed directory outside archive'
	}
	$currentPath = $root
	$relative = [IO.Path]::GetRelativePath($root, $full)
	$parts = @('')
	if ($relative -ne '.') { $parts += $relative.Split('\') }
	foreach ($part in $parts) {
		if ($part) { $currentPath = Join-Path $currentPath $part }
		$item = Get-Item -LiteralPath $currentPath -Force -ErrorAction SilentlyContinue
		if ($null -eq $item) {
			if (-not $Create) { throw 'Managed directory missing' }
			[void][IO.Directory]::CreateDirectory($currentPath) # Parent checked in previous iteration.
			$item = Get-Item -LiteralPath $currentPath -Force
		}
		Assert-NoReparse $currentPath
		if ($item -isnot [IO.DirectoryInfo]) { throw 'Managed path is not a directory' }
		Assert-Private $currentPath $sid
	}
}
function Assert-ManagedTree([string]$Path) {
	Assert-ManagedDirectory $Path
	$pendingDirectories = [Collections.Generic.Stack[string]]::new()
	$pendingDirectories.Push($Path)
	while ($pendingDirectories.Count) {
		$directory = $pendingDirectories.Pop()
		Assert-ManagedDirectory $directory
		foreach ($item in Get-ChildItem -LiteralPath $directory -Force) {
			Assert-NoReparse $item.FullName # Refuse BEFORE descending into a junction.
			Assert-Private $item.FullName $sid
			if ($item -is [IO.DirectoryInfo]) { $pendingDirectories.Push($item.FullName) }
		}
	}
}
function Wait-OwnedTask($Task, [Diagnostics.Stopwatch]$Clock) {
	$remaining = [int][Math]::Ceiling(([double]$cfg.TimeoutSeconds * 1000) - $Clock.Elapsed.TotalMilliseconds)
	if ($remaining -le 0 -or -not $Task.Wait($remaining)) { throw 'Owned copy process deadline; no complete-copy claim' }
}
function Write-Json([string]$Path, $Value) {
	Assert-ManagedDirectory ([IO.Path]::GetDirectoryName($Path))
	if (Test-Path -LiteralPath $Path) { Assert-NoReparse $Path; Assert-Private $Path $sid }
	$temp = $Path + '.new-' + [guid]::NewGuid().ToString('N')
	[IO.File]::WriteAllText($temp, ($Value | ConvertTo-Json -Depth 30), [Text.UTF8Encoding]::new($false))
	[IO.File]::Move($temp, $Path, $true)
}
function Msys-Path([string]$Path) {
	$full = [IO.Path]::GetFullPath($Path)
	if ($full -notmatch '^[A-Za-z]:\\') { throw 'Local drive required, not UNC' }
	return '/' + $full.Substring(0, 1).ToLowerInvariant() + '/' + $full.Substring(3).Replace('\', '/')
}
function Quote-Rsh([string]$Value) {
	if ($Value.Contains('"') -or $Value.Contains("`n") -or $Value.Contains("`r")) { throw 'Invalid SSH argument' }
	return '"' + $Value.Replace('\', '/') + '"'
}
function Invoke-PrivateProcess([string]$Exe, [string[]]$Arguments, [string]$Label, [string]$InputText = '') {
	$outPath = Join-Path $run ($Label + '.stdout')
	$errPath = Join-Path $run ($Label + '.stderr')
	$info = [Diagnostics.ProcessStartInfo]::new()
	$info.FileName = $Exe
	$info.UseShellExecute = $false
	$info.CreateNoWindow = $true
	$info.RedirectStandardInput = $true
	$info.RedirectStandardOutput = $true
	$info.RedirectStandardError = $true
	foreach ($arg in $Arguments) { $info.ArgumentList.Add($arg) }
	$process = [Diagnostics.Process]::new()
	$process.StartInfo = $info
	$output = [IO.File]::Open($outPath, 'CreateNew', 'Write', 'Read')
	$errors = $null
	$started = $false
	$stdin = $null
	try {
		$errors = [IO.File]::Open($errPath, 'CreateNew', 'Write', 'Read')
		$started = $process.Start()
		if (-not $started) { throw 'Owned copy process did not start' }
		$clock = [Diagnostics.Stopwatch]::StartNew()
		try { $process.PriorityClass = 'BelowNormal' } catch { if (-not $process.HasExited) { throw } }
		$outCopy = $process.StandardOutput.BaseStream.CopyToAsync($output)
		$errCopy = $process.StandardError.BaseStream.CopyToAsync($errors)
		$stdin = $process.StandardInput.BaseStream
		if ($InputText) {
			$bytes = [Text.UTF8Encoding]::new($false).GetBytes($InputText)
			$inputCopy = $stdin.WriteAsync($bytes, 0, $bytes.Length)
			Wait-OwnedTask $inputCopy $clock
		}
		# Direct unbuffered pipe bytes: no synchronous StreamWriter flush before the deadline.
		$stdin.Dispose()
		$remaining = [int][Math]::Ceiling(([double]$cfg.TimeoutSeconds * 1000) - $clock.Elapsed.TotalMilliseconds)
		if ($remaining -le 0 -or -not $process.WaitForExit($remaining)) {
			throw 'Owned copy process deadline; no complete-copy claim'
		}
		Wait-OwnedTask $outCopy $clock
		Wait-OwnedTask $errCopy $clock
		$output.Flush($true)
		$errors.Flush($true)
		return @{ Code = $process.ExitCode; Out = $outPath; Err = $errPath }
	} finally {
		try {
			if ($started -and -not $process.HasExited) {
				$process.Kill() # Only the process we started, never an unrelated PID.
				[void]$process.WaitForExit(10000)
			}
		} finally {
			if ($null -ne $stdin) { $stdin.Dispose() }
			$output.Dispose()
			if ($null -ne $errors) { $errors.Dispose() }
			$process.Dispose()
		}
	}
}
function Assert-Relative([string]$Relative) {
	$parts = $Relative.Split('/')
	if ($parts.Length -lt 2 -or $parts[0] -notin @('runs', 'evidence')) { throw 'Unexpected source scope' }
	foreach ($part in $parts) {
		if (-not $part -or $part -in @('.', '..') -or $part -match '[\x00-\x1f<>:"\\|?*]' -or
			$part.EndsWith('.') -or $part.EndsWith(' ') -or
			$part -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)') {
			throw 'Source name cannot be represented safely on Windows'
		}
	}
}

try {
	$cfg = Get-Content -LiteralPath $Config -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
	if ($cfg.Version -ne 1) { throw 'Unsupported configuration' }
	$root = [IO.Path]::GetFullPath($cfg.Destination).TrimEnd('\')
	if ($root -notlike 'C:\FTESurf-private\*') { throw 'Archive must remain in the private tree' }
	if ([IO.Path]::GetFullPath($Config) -ne (Join-Path $root 'config.json')) { throw 'Config must belong to archive root' }
	Assert-NoReparse $root
	Assert-NoReparse $Config
	$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
	if ($sid -ne $cfg.OwnerSid) { throw 'Wrong Windows task identity' }
	Assert-Private $root $sid $true
	Assert-Private $Config $sid
	if (-not (Get-Content -LiteralPath (Join-Path $root 'OWNER.md') -Raw).Contains($cfg.OwnerMarker)) {
		throw 'Archive ownership marker missing'
	}
	$safeRoot = $true
	# Validate existing managed roots AND subtrees before any transport or raw diagnostics.
	foreach ($managed in @('logs', 'current', 'history')) {
		$path = Join-Path $root $managed
		if (Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue) { Assert-ManagedTree $path }
	}
	if ($cfg.Host -notmatch '^[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.:-]*$') { throw 'Invalid existing SSH target' }
	if ($cfg.Synthetic) {
		if ($cfg.Source -notmatch '^/srv/nvme/agent-work/[A-Za-z0-9_/-]+/evidence-copy/source$') { throw 'Synthetic source scope refused' }
	} elseif ($cfg.Source -ne '/srv/nvme/ftesurf-server/game/ftesurf/data') { throw 'Live source scope refused' }
	if ($cfg.TimeoutSeconds -lt 1 -or $cfg.TimeoutSeconds -gt 1800 -or
		$cfg.MaxFiles -lt 1 -or $cfg.MaxFiles -gt 100000 -or $cfg.MaxBytes -lt 1 -or
		$cfg.BandwidthKiB -lt 1 -or $cfg.ReserveBytes -lt 1) { throw 'Invalid operator copy budgets' }
	$pinned = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
	foreach ($artifact in $cfg.Artifacts) {
		if ([IO.Path]::GetExtension($artifact.Path) -notin @('.exe', '.dll', '.ps1', '.py')) { throw 'Not a tool artifact' }
		Assert-NoReparse $artifact.Path
		if ((Get-FileHash -LiteralPath $artifact.Path -Algorithm SHA256).Hash -cne $artifact.Sha256.ToUpperInvariant()) {
			throw 'Bound tool bytes changed; revalidate, never silently refresh pins'
		}
		[void]$pinned.Add([IO.Path]::GetFullPath($artifact.Path))
	}
	foreach ($required in @($PSCommandPath, $cfg.Script, $cfg.Indexer, $cfg.Rsync, $cfg.SshArgv[0])) {
		if (-not $pinned.Contains([IO.Path]::GetFullPath($required))) { throw 'Unbound tool executable/source' }
	}
	# A durable empty file; FileShare.None also covers manual launches of this tool.
	$lock = Join-Path $root '.writer.lock'
	if (Test-Path -LiteralPath $lock) { Assert-NoReparse $lock }
	$lease = [IO.File]::Open($lock, 'OpenOrCreate', 'ReadWrite', 'None')
	if ($lease.Length -ne 0) { throw 'Unexpected writer sidecar content' }
	if ($Register) {
		if ($Probe) { throw 'Register and Probe are separate operations' }
		if ([IO.Path]::GetFullPath($PSCommandPath) -ne [IO.Path]::GetFullPath($cfg.Script)) { throw 'Register only installed inspected script' }
		if ($cfg.TaskName -notmatch '^FTESurf-EvidenceBackup(?:-[A-Za-z0-9]+)?$') { throw 'Unexpected task name' }
		if (Get-ScheduledTask -TaskName $cfg.TaskName -ErrorAction SilentlyContinue) { throw 'Existing task: inspect ownership, never replace silently' }
		$arguments = '-NoProfile -NonInteractive -File "' + $cfg.Script + '" -Config "' + $Config + '"'
		$action = New-ScheduledTaskAction -Execute (Join-Path $PSHOME 'pwsh.exe') -Argument $arguments -WorkingDirectory $root
		$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Hours 1)
		$principal = New-ScheduledTaskPrincipal -UserId $sid -LogonType S4U -RunLevel Limited
		$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 45)
		Register-ScheduledTask -TaskName $cfg.TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description ('Private no-delete evidence copies; owner=' + $cfg.OwnerMarker) | Out-Null
		Write-Output 'Registered hourly limited S4U task, no password, no wake; actual scheduled execution still requires verification.'
		return
	}
	$drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($root))
	if ($drive.AvailableFreeSpace -lt [long]$cfg.ReserveBytes) { throw 'Archive reserve exhausted, no automatic pruning' }
	$tag = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
	$run = Join-Path $root ('logs\' + $tag)
	Assert-ManagedDirectory $run $true
	$env:PATH = $cfg.MsysBin + ';' + $env:PATH
	$env:MSYS2_ARG_CONV_EXCL = '*'
	$env:MSYS_NO_PATHCONV = '1'
	if ($Probe) {
		$check = Invoke-PrivateProcess $cfg.SshArgv[0] (@($cfg.SshArgv | Select-Object -Skip 1) + @($cfg.Host, 'printf evidence-backup-transport-acted')) 'probe'
		if ($check.Code -ne 0 -or [IO.File]::ReadAllText($check.Out) -cne 'evidence-backup-transport-acted') { throw 'Existing noninteractive SSH profile failed' }
		Write-Json (Join-Path $root 'probe-result.json') @{ Utc = [DateTime]::UtcNow.ToString('o'); Acted = $true; OwnerSidMatched = $true; ToolsPinned = $true }
		Write-Output 'Existing noninteractive transport acted; no evidence copied.'
		return
	}
	$request = @{ root = $cfg.Source; max_files = [int]$cfg.MaxFiles; max_bytes = [long]$cfg.MaxBytes; max_seconds = [int]$cfg.TimeoutSeconds } | ConvertTo-Json -Compress
	$literal = ConvertTo-Json -InputObject $request -Compress
	$program = "import json`nREQUEST = json.loads($literal)`n" + [IO.File]::ReadAllText($cfg.Indexer)
	$indexRun = Invoke-PrivateProcess $cfg.SshArgv[0] (@($cfg.SshArgv | Select-Object -Skip 1) + @($cfg.Host, 'nice -n 10 ionice -c 3 python3 -I -B -')) 'source-index' $program
	if ($indexRun.Code -ne 0 -or (Get-Item -LiteralPath $indexRun.Out).Length -gt 16MB) { throw 'No bounded complete source index' }
	$index = Get-Content -LiteralPath $indexRun.Out -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
	if ($index.version -ne 1 -or @($index.files).Count -gt $cfg.MaxFiles) { throw 'Unexpected source index shape' }
	$names = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
	$sourceBytes = [long]0
	foreach ($row in @($index.files) + @($index.deferred)) {
		Assert-Relative $row.rel
		if (-not $names.Add($row.rel)) { throw 'Source filename case alias: refuse before copying' }
	}
	foreach ($row in $index.files) {
		if ($row.sha256 -notmatch '^[a-f0-9]{64}$' -or $row.bytes -lt 0) { throw 'Invalid copy digest/length' }
		$sourceBytes += [long]$row.bytes
	}
	if ($sourceBytes -gt $cfg.MaxBytes -or $drive.AvailableFreeSpace -lt ($sourceBytes + [long]$cfg.ReserveBytes)) { throw 'Copy space/allowance insufficient; no automatic prune' }
	$current = Join-Path $root 'current'
	Assert-ManagedDirectory $current $true
	Assert-ManagedTree $current
	$rsh = ($cfg.SshArgv | ForEach-Object { Quote-Rsh $_ }) -join ' '
	$codes = @()
	foreach ($scope in @('runs', 'evidence')) {
		$destination = Join-Path $current $scope
		Assert-ManagedDirectory $destination $true
		$history = Join-Path $root ('history\' + $tag + '\' + $scope)
		Assert-ManagedDirectory $history $true
		$rsyncArgs = @('-rtpc', '--no-owner', '--no-group', '--no-links', '--no-specials', '--no-devices',
			'--chmod=Du=rwx,Dgo=,Fu=rw,Fgo=', '--backup', ('--backup-dir=' + (Msys-Path $history)),
			('--bwlimit=' + $cfg.BandwidthKiB), '--rsync-path=nice -n 10 ionice -c 3 rsync',
			'--itemize-changes', '--stats', '-e', $rsh, ($cfg.Host + ':' + $cfg.Source + '/' + $scope + '/'), ((Msys-Path $destination) + '/'))
		$copy = Invoke-PrivateProcess $cfg.Rsync $rsyncArgs ('copy-' + $scope)
		$codes += $copy.Code
		if ($copy.Code -notin @(0, 24)) { throw 'Rsync failed; original private diagnostic retained, no complete-copy claim' }
	}
	Assert-ManagedTree $current
	Assert-ManagedTree (Join-Path $root 'history')
	Assert-ManagedTree $run
	$local = [Collections.Generic.Dictionary[string, object]]::new([StringComparer]::Ordinal)
	foreach ($file in Get-ChildItem -LiteralPath $current -File -Recurse -Force) {
		if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Copied payload reparse refused' }
		Assert-Private $file.FullName $sid
		$relative = [IO.Path]::GetRelativePath($current, $file.FullName).Replace('\', '/')
		$local.Add($relative, @{ rel = $relative; bytes = $file.Length; sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() })
	}
	$pending = [Collections.Generic.List[string]]::new()
	foreach ($row in $index.files) {
		if (-not $local.ContainsKey($row.rel) -or $local[$row.rel].sha256 -cne $row.sha256 -or $local[$row.rel].bytes -ne $row.bytes) { $pending.Add($row.rel) }
	}
	$prior = $null
	$latest = Join-Path $root 'latest.json'
	if (Test-Path -LiteralPath $latest) { $prior = Get-Content -LiteralPath $latest -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable }
	$previous = [Collections.Generic.Dictionary[string, string]]::new([StringComparer]::Ordinal)
	if ($null -ne $prior) { foreach ($row in $prior.Source.files) { $previous[$row.rel] = $row.sha256 } }
	$changed = @($index.files | Where-Object { $previous.ContainsKey($_.rel) -and $previous[$_.rel] -cne $_.sha256 } | ForEach-Object { $_.rel })
	$present = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
	foreach ($row in $index.files) { [void]$present.Add($row.rel) }
	$absent = @($previous.Keys | Where-Object { -not $present.Contains($_) })
	$complete = (@($index.deferred).Count -eq 0 -and $pending.Count -eq 0 -and @($codes | Where-Object { $_ -ne 0 }).Count -eq 0)
	$report = @{ Utc = [DateTime]::UtcNow.ToString('o'); Complete = $complete; Source = $index;
		Local = @($local.Values | ForEach-Object { $_ }); ChangedSourcePaths = $changed; NoLongerObserved = $absent; Pending = $pending;
		RsyncCodes = $codes; NoDeleteOrPiRepair = $true; NotCoherentGlobalInstant = $true; NoGuiltInference = $true }
	Write-Json (Join-Path $run 'observation.json') $report
	Write-Json $latest $report
	Write-Output ('Evidence copies: source={0}, retained={1}, changed={2}, pending={3}, deferred={4}, complete={5}; no deletes/repair/guilt.' -f @($index.files).Count, $local.Count, $changed.Count, $pending.Count, @($index.deferred).Count, $complete)
	if (-not $complete) { throw 'Partial observations retained; source changed/unavailable, not a complete-copy pass' }
} catch {
	if ($safeRoot -and $root -and (Test-Path -LiteralPath $root)) {
		try { Write-Json (Join-Path $root 'last-error.json') @{ Utc = [DateTime]::UtcNow.ToString('o'); Error = $_.Exception.ToString(); NoCompleteCopyClaim = $true } } catch { }
	}
	Write-Error 'Evidence backup stopped; inspect private diagnostics. No source deletion/repair was performed.' -ErrorAction Continue
	exit 1
} finally {
	if ($null -ne $lease) { $lease.Dispose() } # Persistent empty sidecar is NOT unlinked.
}
