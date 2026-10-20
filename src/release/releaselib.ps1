# releaselib.ps1 -- pure helpers for release.ps1 (-Linux and the page blocks).
# Dot-sourced by release.ps1 and test_releaselib.ps1. Helpers throw or return a
# list of problems; the caller decides what is fatal.

# --- page blocks ---------------------------------------------------------------
# A block is whole lines between a line that is exactly <!--NAME-BEGIN--> and one
# that is exactly <!--NAME-END-->. Outside = the page with blocks cut (byte-equal
# to a template that never had them), Kept = the page with only the marker lines
# cut, Inside = the block lines alone (for the token assert).
function Split-PageBlocks ([string]$Text, [string]$Name = 'LINUX') {
    $begin = "<!--$Name-BEGIN-->"; $end = "<!--$Name-END-->"; $tag = "<!--$Name-"
    $out = [System.Text.StringBuilder]::new(); $in = [System.Text.StringBuilder]::new()
    $kept = [System.Text.StringBuilder]::new()
    $open = $false; $pairs = 0; $n = 0
    foreach ($line in [regex]::Split($Text, '(?<=\n)')) {
        $n++
        $t = $line.Trim()
        if ($t -ceq $begin) {
            if ($open) { throw "page blocks: nested $begin at line $n" }
            $open = $true; continue
        }
        if ($t -ceq $end) {
            if (-not $open) { throw "page blocks: $end before its BEGIN at line $n" }
            $open = $false; $pairs++; continue
        }
        if ($line.Contains($tag)) { throw "page blocks: a $tag marker shares line $n with other text" }
        [void]$kept.Append($line)
        if ($open) { [void]$in.Append($line) } else { [void]$out.Append($line) }
    }
    if ($open) { throw "page blocks: $begin is never closed" }
    if ($pairs -eq 0) { throw "page blocks: no $begin/$end pair in the template" }
    [pscustomobject]@{ Outside = $out.ToString(); Inside = $in.ToString(); Kept = $kept.ToString(); Pairs = $pairs }
}

function Get-TemplateTokens ([string]$Text) {
    $set = [System.Collections.Generic.SortedSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($m in [regex]::Matches($Text, '@@([A-Z0-9_]+)@@')) { [void]$set.Add($m.Groups[1].Value) }
    return [string[]]@($set)
}

# Both directions, in release.ps1's historical wording ("X only in template/script").
function Compare-TokenSets ([string[]]$Template, [string[]]$Script) {
    $Template = @($Template | Where-Object { $_ }); $Script = @($Script | Where-Object { $_ })
    $t = [System.Collections.Generic.HashSet[string]]::new([string[]]@($Template), [System.StringComparer]::Ordinal)
    $s = [System.Collections.Generic.HashSet[string]]::new([string[]]@($Script), [System.StringComparer]::Ordinal)
    $d = @()
    foreach ($x in @($Template) | Sort-Object -Unique) { if (-not $s.Contains($x)) { $d += "$x only in template" } }
    foreach ($x in @($Script) | Sort-Object -Unique) { if (-not $t.Contains($x)) { $d += "$x only in script" } }
    return $d
}

# --- BUILDINFO.txt (written by tools/linux/build.sh) ---------------------------
# FTESURF-LINUX-BUILD 1, then `key value` lines: commit (40 hex), revision,
# builder, cc, built, gates (`all PASS` or the failures), and `sha256 <hex> <file>`
# once per file. Singleton keys may not repeat; unknown keys are ignored.
function Read-LinuxBuildInfo ([string]$Path, [string[]]$Require = @('fteqw64', 'fteplug_hl2_amd64.so')) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "no BUILDINFO at $Path" }
    $raw = [System.IO.File]::ReadAllText($Path)
    if ($raw.Contains("`r")) { throw "BUILDINFO has CR bytes (it is written in Linux and never edited): $Path" }
    $lines = @($raw -split "`n")
    if ($lines[0] -cne 'FTESURF-LINUX-BUILD 1') { throw "BUILDINFO header is '$($lines[0])', expected 'FTESURF-LINUX-BUILD 1'" }
    $single = @('commit', 'revision', 'builder', 'cc', 'built', 'gates')
    $kv = @{}
    $sha = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
    for ($i = 1; $i -lt $lines.Count; $i++) {
        $l = $lines[$i].Trim()
        if (-not $l) { continue }
        if ($l -notmatch '^(\S+)\s+(.*)$') { throw "BUILDINFO line $($i + 1) has no value: '$l'" }
        $k = $Matches[1]; $v = $Matches[2].Trim()
        if ($k -ceq 'sha256') {
            if ($v -notmatch '^([0-9A-Fa-f]{64})\s+(\S.*)$') { throw "BUILDINFO line $($i + 1): expected 'sha256 <64 hex> <file>'" }
            $f = $Matches[2].Trim()
            if ($sha.ContainsKey($f)) { throw "BUILDINFO names $f twice" }
            $sha[$f] = $Matches[1].ToUpperInvariant()
        } elseif ($single -ccontains $k) {
            if ($kv.ContainsKey($k)) { throw "BUILDINFO has two '$k' lines" }
            $kv[$k] = $v
        }
    }
    if (-not $kv.ContainsKey('commit') -or $kv.commit -notmatch '^[0-9a-f]{40}$') { throw 'BUILDINFO commit must be 40 lowercase hex' }
    if (-not $kv.ContainsKey('gates')) { throw 'BUILDINFO has no gates line' }
    foreach ($f in $Require) { if (-not $sha.ContainsKey($f)) { throw "BUILDINFO has no sha256 line for $f" } }
    [pscustomobject]@{
        Commit = $kv.commit; Gates = $kv.gates; Sha256 = $sha
        Revision = $kv['revision']; Builder = $kv['builder']; Cc = $kv['cc']; Built = $kv['built']
    }
}

# --- engine revision stamp -------------------------------------------------------
# engine/Makefile: git-<rev-list --count + 29>-<describe --long --always --dirty>.
# Matched tolerantly (the describe abbreviation length depends on the repo's
# object count): same count, hash part a prefix of the commit, never -dirty.
function Test-RevisionMatch ([string]$Rev, [int]$CommitCount, [string]$Commit) {
    if ($Rev -cnotmatch '^git-(\d+)-(?:.+-g)?([0-9a-f]{7,40})$') { return $false }
    return ([int]$Matches[1] -eq $CommitCount + 29) -and $Commit.ToLowerInvariant().StartsWith($Matches[2])
}

function Get-BinaryRevisions ([string]$Path) {
    $s = [System.Text.Encoding]::Latin1.GetString([System.IO.File]::ReadAllBytes($Path))
    $set = [System.Collections.Generic.SortedSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($m in [regex]::Matches($s, 'git-\d+-(?:[A-Za-z0-9._-]+-g)?[0-9a-f]{7,40}(?:-dirty)?(?![0-9a-f])')) { [void]$set.Add($m.Value) }
    return [string[]]@($set)
}

function Test-ElfX64 ([string]$Path) {
    $fs = [System.IO.File]::OpenRead($Path)
    try { $b = [byte[]]::new(20); $n = $fs.Read($b, 0, 20) } finally { $fs.Dispose() }
    return $n -eq 20 -and $b[0] -eq 0x7F -and $b[1] -eq 0x45 -and $b[2] -eq 0x4C -and $b[3] -eq 0x46 -and
        $b[4] -eq 2 -and $b[5] -eq 1 -and $b[18] -eq 0x3E -and $b[19] -eq 0
}

# Strings the build's gates look for, re-checked on the bytes that ship.
function Test-ByteStrings ([string]$Path, [string[]]$MustHave = @(), [string[]]$MustNot = @()) {
    $s = [System.Text.Encoding]::Latin1.GetString([System.IO.File]::ReadAllBytes($Path))
    $leaf = Split-Path -Leaf $Path
    $p = @()
    foreach ($x in $MustHave) { if ($s.IndexOf($x, [System.StringComparison]::Ordinal) -lt 0) { $p += "$leaf does not contain '$x'" } }
    foreach ($x in $MustNot) { if ($s.IndexOf($x, [System.StringComparison]::Ordinal) -ge 0) { $p += "$leaf contains '$x'" } }
    return $p
}

# Same heading regex as release.ps1's Provenance step, over text (git show output).
function Get-MaxPatchHeading ([string]$Text) {
    $max = 0; $count = 0
    foreach ($m in [regex]::Matches($Text, '(?m)^##+ Patch(?:es)? (\d+)(?:-(\d+))?(?=[\s,.:]|$)')) {
        $count++
        foreach ($g in 1, 2) { if ($m.Groups[$g].Success -and [int]$m.Groups[$g].Value -gt $max) { $max = [int]$m.Groups[$g].Value } }
    }
    [pscustomobject]@{ Max = $max; Count = $count }
}

# --- the tar.xz --------------------------------------------------------------------
# GNU `tar --numeric-owner -tv` lines. A line that does not parse keeps Type '?'.
function ConvertFrom-TarListing ([string[]]$Lines) {
    foreach ($l in $Lines) {
        if ($l -cmatch '^(\S{10})\s+(\d+)/(\d+)\s+\d+\s+\S+\s+\S+\s(.+)$') {
            $p = $Matches[4]
            if ($Matches[1][0] -eq 'd') { $p = $p.TrimEnd('/') }
            [pscustomobject]@{ Type = [string]$Matches[1][0]; Mode = $Matches[1]; Uid = [int]$Matches[2]; Gid = [int]$Matches[3]; Path = $p; Raw = $l }
        } else {
            [pscustomobject]@{ Type = '?'; Mode = ''; Uid = -1; Gid = -1; Path = ''; Raw = $l }
        }
    }
}

# `sha256sum` lines (`<hex>  <path>`) -> ordinal map path -> lowercase hex.
function ConvertFrom-ShaLines ([string[]]$Lines) {
    $h = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
    foreach ($l in $Lines) { if ($l -cmatch '^([0-9a-f]{64}) [ *](.+)$') { $h[$Matches[2]] = $Matches[1] } }
    return $h
}

# Entries vs the stage. $Hashes: extracted path (with $Top/) -> hex; $Stage:
# path under $Top -> hex. Paths compare Ordinal: Linux is case-sensitive.
function Test-LinuxArchiveEntries ($Entries, $Hashes, $Stage, [string]$Top, [string[]]$Exec) {
    $p = @()
    $files = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($e in @($Entries)) {
        if ($e.Type -eq '?') { $p += "unparsable listing line: $($e.Raw)"; continue }
        if (-not $seen.Add($e.Path)) { $p += "$($e.Path) is in the archive twice" }
        if ($e.Path -cne $Top -and -not $e.Path.StartsWith("$Top/", [System.StringComparison]::Ordinal)) { $p += "$($e.Path) is outside $Top/" }
        if ($e.Uid -ne 0 -or $e.Gid -ne 0) { $p += "$($e.Path) is owned $($e.Uid)/$($e.Gid), not 0/0" }
        if ($e.Type -eq 'd') {
            if ($e.Mode -cne 'drwxr-xr-x') { $p += "$($e.Path)/ is $($e.Mode), not drwxr-xr-x" }
        } elseif ($e.Type -eq '-') {
            $rel = if ($e.Path.Length -gt $Top.Length) { $e.Path.Substring($Top.Length + 1) } else { $e.Path }
            [void]$files.Add($rel)
            $want = if ($Exec -ccontains $rel) { '-rwxr-xr-x' } else { '-rw-r--r--' }
            if ($e.Mode -cne $want) { $p += "$($e.Path) is $($e.Mode), not $want" }
            if (-not $Hashes.ContainsKey($e.Path)) { $p += "$($e.Path) has no extracted sha256" }
            elseif ($Stage.ContainsKey($rel) -and $Hashes[$e.Path] -ne $Stage[$rel].ToLowerInvariant()) { $p += "$($e.Path) sha256 differs from the stage" }
        } else {
            $p += "$($e.Path) is type '$($e.Type)'; only files and directories may ship"
        }
    }
    foreach ($f in $files) { if (-not $Stage.ContainsKey($f)) { $p += "$Top/$f is in the archive but not staged" } }
    foreach ($f in $Stage.Keys) { if (-not $files.Contains($f)) { $p += "$Top/$f is staged but not in the archive" } }
    return $p
}

# --- R2 housekeeping ---------------------------------------------------------------
# Keep the newest $Keep VERSIONS (by parsed semver, never ModTime) and doom every
# artifact of the older ones. Sidecars and probes never match; $Protect never goes.
function Select-PruneDoomed ([string[]]$Names, [int]$Keep, [string[]]$Protect = @()) {
    $items = @(foreach ($n in $Names) {
        $t = "$n".Trim()
        if ($t -cmatch '^ftesurf-(\d+)\.(\d+)\.(\d+)(\.7z|-linux-x86_64\.tar\.xz)$') {
            [pscustomobject]@{ Name = $t; Ver = [version]::new([int]$Matches[1], [int]$Matches[2], [int]$Matches[3]) }
        }
    })
    $keepSet = @($items | ForEach-Object { $_.Ver } | Sort-Object -Unique -Descending | Select-Object -First $Keep)
    $doomed = @($items | Where-Object { $keepSet -notcontains $_.Ver -and $Protect -notcontains $_.Name } |
        Sort-Object -Property @{ Expression = 'Ver'; Descending = $true }, @{ Expression = 'Name'; Descending = $false } |
        ForEach-Object { $_.Name })
    return $doomed
}

function Get-MaxVersion ([string[]]$Versions) {
    $best = $null; $bestS = $null
    foreach ($s in $Versions) {
        $v = "$s".Trim()
        if ($v -notmatch '^\d+(\.\d+){0,3}$') { throw "not a version: '$s'" }
        $vv = [version]$(if ($v.Contains('.')) { $v } else { "$v.0" })
        if ($null -eq $best -or $vv -gt $best) { $best = $vv; $bestS = $v }
    }
    return $bestS
}

# --- WSL -----------------------------------------------------------------------------
# Always --exec: without it wsl.exe hands the joined line to a login shell, which
# expands $vars. Output is UTF-8 bytes, so decode it as UTF-8 for the call.
function Invoke-WslRaw ([string]$Distro, [string[]]$Argv) {
    $enc = [Console]::OutputEncoding; $old = $env:WSL_UTF8
    try {
        [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
        $env:WSL_UTF8 = '1'
        $out = & wsl.exe -d $Distro --exec @Argv 2>&1
        $rc = $LASTEXITCODE
    } finally { [Console]::OutputEncoding = $enc; $env:WSL_UTF8 = $old }
    [pscustomobject]@{ Rc = $rc; Lines = [string[]]@($out | ForEach-Object { "$_" }) }
}

function ConvertTo-WslPath ([string]$Distro, [string]$WinPath) {
    $r = Invoke-WslRaw $Distro @('wslpath', '-a', '-u', $WinPath.TrimEnd('\'))
    if ($r.Rc -ne 0 -or $r.Lines.Count -ne 1 -or -not $r.Lines[0].StartsWith('/')) { throw "wslpath failed for $WinPath`: $($r.Lines -join ' ')" }
    return $r.Lines[0]
}


# --- the site from a receipt (sitepage.ps1) -------------------------------------
# release.ps1 renders the page from what it measured; sitepage.ps1 renders it
# again from the receipt that run wrote.  Both must format a value the same way,
# so the rules live here: release.ps1's HumanSize, its date and its labels.
function Format-HumanSize ([long]$b) {
    if ($b -ge 1MB) { '{0:N1} MB' -f ($b / 1MB) }
    elseif ($b -ge 1KB) { '{0:N0} KB' -f ($b / 1KB) }
    else { "$b bytes" }
}

function Format-EngineLabel ($Patch, $Verified) {
    if ($Verified) { "$Patch" } else { "$Patch (unverified against this binary)" }
}

# PowerShell 7's ConvertFrom-Json turns an ISO string into a DateTime already.
function Format-ReceiptDate ($When) {
    $t = if ($When -is [datetime]) { $When } else {
        [datetime]::Parse("$When", [Globalization.CultureInfo]::InvariantCulture,
                          [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal)
    }
    $t.ToUniversalTime().ToString('d MMMM yyyy', [Globalization.CultureInfo]::InvariantCulture)
}

# The page's token values for one receipt: Windows always, Linux only when the
# release shipped one (else $null, and the LINUX blocks are cut).
function Get-ReceiptTokens ($Receipt) {
    $a = $Receipt.archive
    $win = [ordered]@{
        'VERSION'     = "$($Receipt.version)"
        'FILENAME'    = "$($a.name)"
        'URL'         = "$($a.url)"
        'SIZE_HUMAN'  = (Format-HumanSize ([long]$a.bytes))
        'SIZE_BYTES'  = ('{0:N0}' -f [long]$a.bytes)
        'SHA256'      = "$($a.sha256)".ToUpper()
        'DATE'        = (Format-ReceiptDate $Receipt.built_utc)
        'QCBUILD'     = "$($Receipt.qc.build)"
        'ENGINEPATCH' = (Format-EngineLabel $Receipt.engine.patch_doc $Receipt.engine.patch_applies_to_binary)
    }
    $lx = $null
    if ($Receipt.PSObject.Properties.Name -contains 'linux' -and $Receipt.linux) {
        $l = $Receipt.linux
        $lx = [ordered]@{
            'LINUX_URL'        = "$($l.archive.url)"
            'LINUX_FILENAME'   = "$($l.archive.name)"
            'LINUX_SIZE_HUMAN' = (Format-HumanSize ([long]$l.archive.bytes))
            'LINUX_SIZE_BYTES' = ('{0:N0}' -f [long]$l.archive.bytes)
            'LINUX_SHA256'     = "$($l.archive.sha256)".ToLower()
            'LINUX_GLIBC'      = "$($l.glibc_min)"
            'LINUX_ENGINE'     = (Format-EngineLabel $l.engine.patch_doc $l.engine.binary_verified)
        }
    }
    if ($Receipt.PSObject.Properties.Name -contains 'bootstrap_downloads') {
        $wb = @($Receipt.bootstrap_downloads | Where-Object platform -eq 'win64')
        if ($wb.Count -ne 1) { throw 'receipt needs exactly one Windows launcher download' }
        $win['LAUNCHER_URL'] = "$($wb[0].url)"
        $win['LAUNCHER_SHA256'] = "$($wb[0].sha256)"
        if ($null -ne $lx) {
            $lb = @($Receipt.bootstrap_downloads | Where-Object platform -eq 'linux64')
            if ($lb.Count -ne 1) { throw 'receipt needs exactly one Linux launcher download' }
            $lx['LINUX_LAUNCHER_URL'] = "$($lb[0].url)"
            $lx['LINUX_LAUNCHER_SHA256'] = "$($lb[0].sha256)"
        }
    }
    [pscustomobject]@{ Windows = $win; Linux = $lx }
}

# src/release/site: fixed files copied as they are, so a token in one is a
# mistake -- refused rather than shipped literally.  Returns the names copied.
function Copy-SiteFiles ([string]$From, [string]$To) {
    $names = @()
    foreach ($f in @(Get-ChildItem -LiteralPath $From -File | Sort-Object Name)) {
        if ($f.Extension -in '.html', '.css', '.js', '.json', '.txt', '.svg') {
            $m = [regex]::Match([System.IO.File]::ReadAllText($f.FullName), '@@([A-Z0-9_]+)@@')
            if ($m.Success) { throw "site file $($f.Name) holds a template token $($m.Value)" }
        }
        Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $To $f.Name)
        $names += $f.Name
    }
    return $names
}

# --- patch notes -----------------------------------------------------------------------
# PATCHNOTES.md -> patchnotes.json beside update.json, read by the page's side panel
# (site.js) and the title menu (m_update.qc). Newest release first: `## next` (the
# one being prepared) or `## <version> <yyyy-mm-dd>`; `### P<n> <title>`; `- <point>`
# one line each. Other lines are prose and skipped. Printable ASCII and no ^: the
# menu draws ^ as a colour code. -Version: `next` becomes that release, dated -Date.
# -Upto: re-rendering a live release, so `next` and anything newer are left out.
# Only the newest -Keep releases are returned: the menu refuses a reply over 256 KiB.
function ConvertFrom-PatchNotes ([string]$Text, [string]$Version, [string]$Date, [string]$Upto, [int]$Keep = 12) {
    if ([bool]$Version -eq [bool]$Upto) { throw 'patch notes: give -Version (preparing) or -Upto (a live release)' }
    $isDate = { param($d) $t = [datetime]::MinValue; [datetime]::TryParseExact($d, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture, 'None', [ref]$t) }
    if ($Version -and -not (& $isDate $Date)) { throw "patch notes: -Date '$Date' is not yyyy-mm-dd" }
    $rels = [System.Collections.Generic.List[object]]::new()
    $nums = @{}
    $rel = $null; $pat = $null; $inRange = $false; $prev = $null; $next = $false; $n = 0
    $endPatch = { if ($pat -and -not $pat.points.Count) { throw "patch notes: P$($pat.patch) has no points" } }
    $endRelease = {
        . $endPatch
        if ($rel -and $rel.version -and -not $rel.patches.Count) { throw "patch notes: release $($rel.version) has no patches" }
    }
    foreach ($line in ($Text -split "`r?`n")) {
        $n++
        $isRel = $line.StartsWith('## '); $isPat = $line.StartsWith('### '); $isPt = $line.StartsWith('- ')
        if (-not ($isRel -or $isPat -or $isPt)) { continue }
        if ($line -cmatch '[^\x20-\x7E]' -or $line.Contains('^')) { throw "patch notes line ${n}: printable ASCII only, and no ^" }
        if ($isRel) {
            . $endRelease; $pat = $null
            $h = $line.Substring(3).Trim()
            if ($h -ceq 'next') {
                if ($next -or $prev) { throw "patch notes line ${n}: ## next must be the first release, and only once" }
                $v = $Version; $d = $Date; $inRange = [bool]$Version; $next = $true
            } elseif ($h -cmatch '^((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)) (\S+)$') {
                $v = $Matches[1]; $d = $Matches[2]
                if (-not (& $isDate $d)) { throw "patch notes line ${n}: '$d' is not a date (yyyy-mm-dd)" }
                if ($prev -and [version]$v -ge [version]$prev) { throw "patch notes line ${n}: $v is not older than $prev above it" }
                $inRange = $Upto -eq '' -or [version]$v -le [version]$Upto
            } else { throw "patch notes line ${n}: expected '## next' or '## <version> <yyyy-mm-dd>'" }
            if ($v) { $prev = $v }
            $rel = [ordered]@{ version = $v; date = $d; patches = [System.Collections.Generic.List[object]]::new() }
            if ($inRange) { $rels.Add($rel) }
            continue
        }
        if ($isPat) {
            if (-not $rel) { throw "patch notes line ${n}: a patch before any release" }
            . $endPatch
            if ($line -cnotmatch '^### P(\d{1,5}) (\S.{0,79})$') { throw "patch notes line ${n}: expected '### P<number> <title>', title up to 80 characters" }
            $p = [int]$Matches[1]
            if ($nums.ContainsKey($p)) { throw "patch notes line ${n}: P$p appears twice" }
            $nums[$p] = 1
            $pat = [ordered]@{ patch = $p; title = $Matches[2].Trim(); points = [System.Collections.Generic.List[string]]::new() }
            $rel.patches.Add($pat)
            continue
        }
        if (-not $pat) { throw "patch notes line ${n}: a point before any patch" }
        $t = $line.Substring(2).Trim()
        if (-not $t -or $t.Length -gt 250) { throw "patch notes line ${n}: a point is 1 to 250 characters" }
        $pat.points.Add($t)
    }
    . $endRelease
    if ($Version -and (-not $rels.Count -or $rels[0].version -cne $Version)) {
        throw "patch notes: nothing for $Version -- add a '## next' section with its patches"
    }
    [ordered]@{ format = 1; releases = @($rels | Select-Object -First $Keep) }
}

function ConvertTo-PatchNotesJson ($Notes) { ($Notes | ConvertTo-Json -Depth 6 -Compress) + "`n" }

# Exercise the actual receipt renderer before any compiler/packer runs. There is
# no second hard-coded token list for the publisher to drift away from.
function Test-ReleaseTemplate ([string]$Text) {
    $archive = [pscustomobject]@{ name = 'probe'; url = 'https://invalid.example/probe'; bytes = 1; sha256 = ('0' * 64) }
    $engine = [pscustomobject]@{ patch_doc = 0; patch_applies_to_binary = $true; binary_verified = $true }
    $probe = [pscustomobject]@{
        version = '0.0.0'; archive = $archive; built_utc = [datetime]'2020-01-01T00:00:00Z'
        qc = [pscustomobject]@{ build = 0 }; engine = $engine
        linux = [pscustomobject]@{ archive = $archive; engine = $engine; glibc_min = '0.0' }
        bootstrap_downloads = @(
            [pscustomobject]@{ platform = 'win64'; url = 'https://invalid.example/launcher.exe'; sha256 = ('0' * 64) },
            [pscustomobject]@{ platform = 'linux64'; url = 'https://invalid.example/launcher'; sha256 = ('0' * 64) })
    }
    $parts = Split-PageBlocks $Text
    $maps = Get-ReceiptTokens $probe
    $problems = @(Compare-TokenSets (Get-TemplateTokens $parts.Outside) @($maps.Windows.Keys)) +
                @(Compare-TokenSets (Get-TemplateTokens $parts.Inside) @($maps.Linux.Keys))
    if ($problems.Count) { throw ('release template contract: ' + ($problems -join '; ')) }
    [pscustomobject]@{ Parts = $parts; WindowsKeys = @($maps.Windows.Keys); LinuxKeys = @($maps.Linux.Keys) }
}

function Get-ReleaseVersion ([string]$Current, [string]$Bump) {
    $Current = $Current.Trim()
    if ($Current -notmatch '^\d+\.\d+\.\d+$') { throw "invalid release VERSION: $Current" }
    if (-not $Bump) { return $Current }
    $parts = @($Current.Split('.') | ForEach-Object { [int]$_ })
    switch ($Bump) {
        'major' { $parts[0]++; $parts[1] = 0; $parts[2] = 0 }
        'minor' { $parts[1]++; $parts[2] = 0 }
        'patch' { $parts[2]++ }
        default { throw "invalid release bump: $Bump" }
    }
    return ($parts -join '.')
}
