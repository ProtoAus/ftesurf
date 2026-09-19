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
