# test_releaselib.ps1 -- unit tests for releaselib.ps1.
#
#   pwsh -NoProfile -File src\release\test_releaselib.ps1 [-Baseline <rev>] [-Wsl]
#
# Prints `N passed, M failed` and exits M. -Baseline <rev>: the template with its
# LINUX blocks cut must hash to <rev>'s template. -Wsl: pack and verify a fixture
# through linux-pack.sh. The mutation control deletes three guards from a copy of
# the library and requires each one's negative test to fail.
param([string]$Baseline, [switch]$Wsl, [string]$Distro = 'Ubuntu-22.04')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Lib = Join-Path $PSScriptRoot 'releaselib.ps1'
$SurfDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. $Lib

$script:pass = 0; $script:fail = 0
function Check ([string]$name, [scriptblock]$test) {
    $err = $null
    try { $ok = & $test } catch { $ok = $false; $err = $_.Exception.Message }
    if ($ok -eq $true) { $script:pass++ }
    else { $script:fail++; Write-Host "FAIL  $name$(if ($err) { "  ($err)" })" -ForegroundColor Red }
}
function Throws ([scriptblock]$b, [string]$like = '*') {
    try { & $b | Out-Null } catch { return $_.Exception.Message -like $like }
    return $false
}
function Has ($list, [string]$like) { return @(@($list) | Where-Object { $_ -like $like }).Count -gt 0 }
$script:tmps = @()
function TmpFile ([string]$text) {
    $f = [System.IO.Path]::GetTempFileName(); $script:tmps += $f
    [System.IO.File]::WriteAllText($f, $text, (New-Object System.Text.UTF8Encoding $false))
    return $f
}
function OrdMap ([hashtable]$h) {
    $d = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
    foreach ($k in $h.Keys) { $d[$k] = $h[$k] }
    return $d
}

# --- Split-PageBlocks ----------------------------------------------------------
$good = "a`n<!--LINUX-BEGIN-->`nb`n<!--LINUX-END-->`nc`n"
Check 'blocks: one pair' {
    $r = Split-PageBlocks $good
    $r.Outside -ceq "a`nc`n" -and $r.Inside -ceq "b`n" -and $r.Kept -ceq "a`nb`nc`n" -and $r.Pairs -eq 1
}
Check 'blocks: indented markers, CRLF kept' {
    $r = Split-PageBlocks "a`r`n    <!--LINUX-BEGIN-->  `r`nb`r`n  <!--LINUX-END-->`r`nc`r`n"
    $r.Outside -ceq "a`r`nc`r`n" -and $r.Kept -ceq "a`r`nb`r`nc`r`n"
}
Check 'blocks: no final newline' { (Split-PageBlocks "a`n<!--LINUX-BEGIN-->`nb`n<!--LINUX-END-->`nc").Outside -ceq "a`nc" }
Check 'blocks: two pairs' { (Split-PageBlocks "$good$good").Pairs -eq 2 }
Check 'blocks: zero pairs throws' { Throws { Split-PageBlocks "a`nb`n" } '*no <!--LINUX-BEGIN-->*' }
Check 'blocks: END before BEGIN throws' { Throws { Split-PageBlocks "a`n<!--LINUX-END-->`n<!--LINUX-BEGIN-->`nb`n<!--LINUX-END-->`n" } '*before its BEGIN*' }
Check 'blocks: nested throws' { Throws { Split-PageBlocks "<!--LINUX-BEGIN-->`n<!--LINUX-BEGIN-->`nb`n<!--LINUX-END-->`n<!--LINUX-END-->`n" } '*nested*' }
Check 'blocks: unclosed throws' { Throws { Split-PageBlocks "a`n<!--LINUX-BEGIN-->`nb`n" } '*never closed*' }
Check 'blocks: marker sharing a line throws' { Throws { Split-PageBlocks "a <!--LINUX-BEGIN-->`nb`n<!--LINUX-END-->`n" } '*shares line*' }
Check 'blocks: lowercase marker is not a marker' { Throws { Split-PageBlocks "<!--linux-begin-->`nb`n<!--linux-end-->`n" } '*no <!--LINUX-BEGIN-->*' }

$tplPath = Join-Path $PSScriptRoot 'page.template.html'
$winKeys = @('VERSION', 'FILENAME', 'URL', 'SIZE_HUMAN', 'SIZE_BYTES', 'SHA256', 'DATE', 'QCBUILD', 'ENGINEPATCH')
$lxKeys  = @('LINUX_URL', 'LINUX_FILENAME', 'LINUX_SIZE_HUMAN', 'LINUX_SIZE_BYTES', 'LINUX_SHA256', 'LINUX_GLIBC', 'LINUX_ENGINE')
$tpl = Split-PageBlocks ([System.IO.File]::ReadAllText($tplPath))
Check 'template: two blocks' { $tpl.Pairs -eq 2 }
Check 'template: outside tokens = Windows map' { @(Compare-TokenSets (Get-TemplateTokens $tpl.Outside) $winKeys).Count -eq 0 }
Check 'template: inside tokens = Linux names' { @(Compare-TokenSets (Get-TemplateTokens $tpl.Inside) $lxKeys).Count -eq 0 }
Check 'template: ids once each when kept' {
    @('id="sha"', 'id="cmd"', 'id="sha-linux"', 'id="cmd-linux"' | Where-Object { ([regex]::Matches($tpl.Kept, [regex]::Escape($_))).Count -ne 1 }).Count -eq 0
}
if ($Baseline) {
    Check "template: outside is byte-identical to $Baseline" {
        $f = [System.IO.Path]::GetTempFileName()
        try {
            [System.IO.File]::WriteAllBytes($f, [System.Text.Encoding]::UTF8.GetBytes($tpl.Outside))
            $a = "$(& git -C $SurfDir hash-object --no-filters -- $f)".Trim()
            $b = "$(& git -C $SurfDir rev-parse "${Baseline}:src/release/page.template.html")".Trim()
            Write-Host "      outside $a, $Baseline $b"
            $a -eq $b
        } finally { Remove-Item -LiteralPath $f -Force }
    }
}

# --- token sets ------------------------------------------------------------------
Check 'tokens: equal sets give nothing' { @(Compare-TokenSets @('A', 'B') @('B', 'A')).Count -eq 0 }
Check 'tokens: LINUX_* outside a block' {
    $r = Split-PageBlocks "@@VERSION@@ @@LINUX_URL@@`n<!--LINUX-BEGIN-->`n@@LINUX_GLIBC@@`n<!--LINUX-END-->`n"
    Has (Compare-TokenSets (Get-TemplateTokens $r.Outside) @('VERSION')) 'LINUX_URL only in template'
}
Check 'tokens: Windows token inside a block' {
    $r = Split-PageBlocks "x`n<!--LINUX-BEGIN-->`n@@VERSION@@`n<!--LINUX-END-->`n"
    Has (Compare-TokenSets (Get-TemplateTokens $r.Inside) @()) 'VERSION only in template'
}
Check 'tokens: missing LINUX_GLIBC' {
    Has (Compare-TokenSets @('LINUX_URL') @('LINUX_URL', 'LINUX_GLIBC')) 'LINUX_GLIBC only in script'
}
Check 'tokens: an empty block side names no empty token' {
    $d = @(Compare-TokenSets (Get-TemplateTokens 'no tokens') @('A'))
    $d.Count -eq 1 -and $d[0] -ceq 'A only in script'
}

# --- BUILDINFO ---------------------------------------------------------------------
$c40 = '3dd8f93c572cf63102203c31b67515da23b27a28'
$h1 = 'a' * 64; $h2 = 'B' * 64
$biGood = @"
FTESURF-LINUX-BUILD 1
commit    $c40
revision  git-6849-patch-266-60-g3dd8f93c5
builder   Debian GNU/Linux 11 (bullseye)
cc        gcc (Debian 10.2.1-6) 10.2.1 20210110
built     2026-09-20T01:02:03Z
gates     all PASS
tarball   zstd-1.5.6.tar.gz $h1
sha256    $h1  fteqw64
sha256    $h2  fteplug_hl2_amd64.so
sha256    $h1  fteqw-sv64
sha256    $h1  db/fteqw64.db
"@.Replace("`r`n", "`n") + "`n"
function BiFile ([string]$text) { TmpFile $text }
Check 'buildinfo: good parses, extra files and unknown keys allowed' {
    $b = Read-LinuxBuildInfo (BiFile $biGood)
    $b.Commit -ceq $c40 -and $b.Gates -ceq 'all PASS' -and $b.Sha256['fteqw64'] -ceq $h1.ToUpper() -and
        $b.Sha256['fteplug_hl2_amd64.so'] -ceq $h2 -and $b.Sha256.Count -eq 4 -and $b.Builder -like 'Debian*'
}
Check 'buildinfo: gates FAIL parses (the gate is the caller''s)' { (Read-LinuxBuildInfo (BiFile $biGood.Replace('all PASS', 'FAIL G8 G6'))).Gates -ceq 'FAIL G8 G6' }
Check 'buildinfo: missing plugin sha throws' { Throws { Read-LinuxBuildInfo (BiFile ($biGood -replace "(?m)^sha256 +$h2  fteplug_hl2_amd64\.so`n", '')) } '*fteplug_hl2_amd64.so*' }
Check 'buildinfo: CRLF throws' { Throws { Read-LinuxBuildInfo (BiFile $biGood.Replace("`n", "`r`n")) } '*CR*' }
Check 'buildinfo: short commit throws' { Throws { Read-LinuxBuildInfo (BiFile $biGood.Replace($c40, '3dd8f93c5')) } '*40*' }
Check 'buildinfo: duplicate key throws' { Throws { Read-LinuxBuildInfo (BiFile ($biGood + "commit    $c40`n")) } '*two*' }
Check 'buildinfo: duplicate file throws' { Throws { Read-LinuxBuildInfo (BiFile ($biGood + "sha256    $h2  fteqw64`n")) } '*twice*' }
Check 'buildinfo: no gates line throws' { Throws { Read-LinuxBuildInfo (BiFile ($biGood -replace "(?m)^gates .*`n", '')) } '*gates*' }
Check 'buildinfo: wrong header throws' { Throws { Read-LinuxBuildInfo (BiFile $biGood.Replace('BUILD 1', 'BUILD 2')) } '*header*' }
Check 'buildinfo: missing file throws' { Throws { Read-LinuxBuildInfo 'C:\no\such\BUILDINFO.txt' } '*no BUILDINFO*' }

# --- revision stamp ------------------------------------------------------------------
Check 'rev: exact describe'            { Test-RevisionMatch 'git-6849-patch-266-60-g3dd8f93c5' 6820 $c40 }
Check 'rev: longer abbreviation'       { Test-RevisionMatch 'git-6849-patch-266-60-g3dd8f93c572c' 6820 $c40 }
Check 'rev: no tag (describe --always)' { Test-RevisionMatch 'git-6849-3dd8f93c5' 6820 $c40 }
Check 'rev: -dirty rejected'           { -not (Test-RevisionMatch 'git-6849-patch-266-60-g3dd8f93c5-dirty' 6820 $c40) }
Check 'rev: wrong count rejected'      { -not (Test-RevisionMatch 'git-6848-patch-266-60-g3dd8f93c5' 6820 $c40) }
Check 'rev: wrong hash rejected'       { -not (Test-RevisionMatch 'git-6849-patch-266-60-g36bf58597' 6820 $c40) }
Check 'rev: empty rejected'            { -not (Test-RevisionMatch '' 6820 $c40) }

$bin = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllBytes($bin, [System.Text.Encoding]::Latin1.GetBytes("`0x git-6849-patch-266-60-g3dd8f93c5`0y git-6848-patch-266-59-g36bf58597-dirty`0 git-6849-patch-266-60-g3dd8f93c5`0"))
Check 'binrev: clean and -dirty are two values' {
    $r = @(Get-BinaryRevisions $bin)
    $r.Count -eq 2 -and $r -ccontains 'git-6849-patch-266-60-g3dd8f93c5' -and $r -ccontains 'git-6848-patch-266-59-g36bf58597-dirty'
}
$exe = Join-Path $SurfDir 'ftesurf64.exe'
if (Test-Path -LiteralPath $exe) {
    Check 'binrev: the installed exe carries exactly one stamp' { $r = @(Get-BinaryRevisions $exe); Write-Host "      ftesurf64.exe: $($r -join ', ')"; $r.Count -eq 1 }
    Check 'elf: a PE file is not ELF' { -not (Test-ElfX64 $exe) }
}
$elf = [byte[]]::new(64); $elf[0] = 0x7F; $elf[1] = 0x45; $elf[2] = 0x4C; $elf[3] = 0x46; $elf[4] = 2; $elf[5] = 1; $elf[18] = 0x3E
[System.IO.File]::WriteAllBytes($bin, $elf)
Check 'elf: x86-64 header' { Test-ElfX64 $bin }
$elf[18] = 0xB7; [System.IO.File]::WriteAllBytes($bin, $elf)
Check 'elf: aarch64 header rejected' { -not (Test-ElfX64 $bin) }
[System.IO.File]::WriteAllBytes($bin, [System.Text.Encoding]::Latin1.GetBytes("abc needs a build with zstd`0libEGL`0libgnutls.so.30"))
Check 'strings: must-not and must-have' {
    $p = @(Test-ByteStrings $bin -MustHave @('libEGL.so.1', 'libgnutls.so.30') -MustNot @('needs a build with zstd'))
    $p.Count -eq 2 -and (Has $p "*does not contain 'libEGL.so.1'") -and (Has $p "*contains 'needs a build with zstd'")
}
Remove-Item -LiteralPath $bin -Force

Check 'patch headings: max, ranges, the 34909 trap' {
    $r = Get-MaxPatchHeading "## Patch 12`n### Patches 30-31: x`r`n## Patch 248 - 34909 sprite entities`n## Patch 5.`nPatch 999`n"
    $r.Max -eq 248 -and $r.Count -eq 4
}

# --- tar listing and entries -----------------------------------------------------------
$T = 'FTESurf'
$L = @(
    'drwxr-xr-x 0/0               0 2026-09-19 19:00 FTESurf/'
    '-rwxr-xr-x 0/0         7105112 2026-09-19 17:00 FTESurf/ftesurf64'
    '-rwxr-xr-x 0/0            2859 2026-09-19 19:13 FTESurf/ftesurf.sh'
    '-rw-r--r-- 0/0              12 2026-09-19 19:00 FTESurf/a b.txt'
    'drwxr-xr-x 0/0               0 2026-09-19 19:00 FTESurf/ftesurf/'
    '-rw-r--r-- 0/0          123456 2026-09-19 19:00 FTESurf/ftesurf/csprogs.dat'
)
$H = OrdMap @{ 'FTESurf/ftesurf64' = '1' * 64; 'FTESurf/ftesurf.sh' = '2' * 64; 'FTESurf/a b.txt' = '3' * 64; 'FTESurf/ftesurf/csprogs.dat' = '4' * 64 }
$S = OrdMap @{ 'ftesurf64' = '1' * 64; 'ftesurf.sh' = '2' * 64; 'a b.txt' = '3' * 64; 'ftesurf/csprogs.dat' = '4' * 64 }
$X = @('ftesurf64', 'ftesurf.sh')
function Entries ([string[]]$lines) { @(ConvertFrom-TarListing $lines) }
Check 'listing: spaced path, directory slash dropped' {
    $e = Entries $L
    $e.Count -eq 6 -and $e[3].Path -ceq 'FTESurf/a b.txt' -and $e[0].Path -ceq 'FTESurf' -and $e[0].Type -eq 'd' -and $e[1].Mode -ceq '-rwxr-xr-x'
}
Check 'listing: garbage is type ?' { (Entries @('total 12'))[0].Type -eq '?' }
Check 'entries: the good set has no problems' { @(Test-LinuxArchiveEntries (Entries $L) $H $S $T $X).Count -eq 0 }
function Mutated ([int]$i, [string]$line) { $m = @($L); $m[$i] = $line; return , $m }
Check 'entries: symlink' { Has (Test-LinuxArchiveEntries (Entries ($L + 'lrwxrwxrwx 0/0 0 2026-09-19 19:00 FTESurf/l -> ftesurf64')) $H $S $T $X) "*type 'l'*" }
Check 'entries: ftesurf64 at 0644' { Has (Test-LinuxArchiveEntries (Entries (Mutated 1 '-rw-r--r-- 0/0 7105112 2026-09-19 17:00 FTESurf/ftesurf64')) $H $S $T $X) '*ftesurf64 is -rw-r--r--, not -rwxr-xr-x' }
Check 'entries: data file at 0755' { Has (Test-LinuxArchiveEntries (Entries (Mutated 3 '-rwxr-xr-x 0/0 12 2026-09-19 19:00 FTESurf/a b.txt')) $H $S $T $X) '*a b.txt is -rwxr-xr-x, not -rw-r--r--' }
Check 'entries: uid 1000' { Has (Test-LinuxArchiveEntries (Entries (Mutated 3 '-rw-r--r-- 1000/1000 12 2026-09-19 19:00 FTESurf/a b.txt')) $H $S $T $X) '*owned 1000/1000*' }
Check 'entries: group-writable directory' { Has (Test-LinuxArchiveEntries (Entries (Mutated 4 'drwxrwxr-x 0/0 0 2026-09-19 19:00 FTESurf/ftesurf/')) $H $S $T $X) '*not drwxr-xr-x' }
Check 'entries: no FTESurf/ prefix' { Has (Test-LinuxArchiveEntries (Entries ($L + '-rw-r--r-- 0/0 1 2026-09-19 19:00 other/x')) $H $S $T $X) '*outside FTESurf/*' }
Check 'entries: sha mismatch' { $h = OrdMap @{}; foreach ($k in $H.Keys) { $h[$k] = $H[$k] }; $h['FTESurf/a b.txt'] = '9' * 64; Has (Test-LinuxArchiveEntries (Entries $L) $h $S $T $X) '*a b.txt sha256 differs*' }
Check 'entries: case-only difference' {
    $p = @(Test-LinuxArchiveEntries (Entries (Mutated 5 '-rw-r--r-- 0/0 123456 2026-09-19 19:00 FTESurf/ftesurf/CSprogs.dat')) (OrdMap @{ 'FTESurf/ftesurf64' = '1' * 64; 'FTESurf/ftesurf.sh' = '2' * 64; 'FTESurf/a b.txt' = '3' * 64; 'FTESurf/ftesurf/CSprogs.dat' = '4' * 64 }) $S $T $X)
    (Has $p '*CSprogs.dat is in the archive but not staged') -and (Has $p '*csprogs.dat is staged but not in the archive')
}
Check 'entries: duplicate entry' { Has (Test-LinuxArchiveEntries (Entries ($L + $L[3])) $H $S $T $X) '*twice*' }
Check 'entries: unparsable line' { Has (Test-LinuxArchiveEntries (Entries ($L + 'crw-r--r-- 0/0 1,3 2026-09-19 19:00 FTESurf/dev')) $H $S $T $X) '*unparsable*' }
Check 'sha lines: parse, spaced path' {
    $m = ConvertFrom-ShaLines @("$('a' * 64)  FTESurf/a b.txt", 'junk')
    $m.Count -eq 1 -and $m['FTESurf/a b.txt'] -ceq ('a' * 64)
}

# --- prune ---------------------------------------------------------------------------
$seven = @(0..6 | ForEach-Object { "ftesurf-0.1.$_.7z" })
function OldPrune ([string[]]$names, [int]$keep) {
    $all = @(foreach ($n in $names) { if ($n -match '^ftesurf-(\d+)\.(\d+)\.(\d+)\.7z$') { [pscustomobject]@{ Name = $n.Trim(); Key = ([int]$Matches[1] * 1000000 + [int]$Matches[2] * 1000 + [int]$Matches[3]) } } })
    @($all | Sort-Object Key -Descending | Select-Object -Skip $keep | ForEach-Object { $_.Name })
}
Check 'prune: .7z only equals the old algorithm' {
    $a = @(Select-PruneDoomed $seven 5); $b = @(OldPrune $seven 5)
    ($a -join ',') -ceq ($b -join ',') -and ($a -join ',') -ceq 'ftesurf-0.1.1.7z,ftesurf-0.1.0.7z'
}
Check 'prune: keep counts versions, not objects' {
    $n = $seven + @('ftesurf-0.1.5-linux-x86_64.tar.xz', 'ftesurf-0.1.6-linux-x86_64.tar.xz', 'ftesurf-0.1.0-linux-x86_64.tar.xz')
    (@(Select-PruneDoomed $n 5) -join ',') -ceq 'ftesurf-0.1.1.7z,ftesurf-0.1.0-linux-x86_64.tar.xz,ftesurf-0.1.0.7z'
}
Check 'prune: semver, not lexical (0.1.10 > 0.1.9)' {
    $n = @(5..10 | ForEach-Object { "ftesurf-0.1.$_.7z" })
    (@(Select-PruneDoomed $n 5) -join ',') -ceq 'ftesurf-0.1.5.7z'
}
Check 'prune: sidecars, probes and junk never selected' {
    $n = $seven + @('ftesurf-0.1.0.7z.sha256', '.writetest', 'ftesurf-0.1.0-linux-x86_64.tar.xz.sha256', 'ftesurf-latest.json', 'index.html')
    @(Select-PruneDoomed $n 0 | Where-Object { $_ -notmatch '\.(7z|tar\.xz)$' }).Count -eq 0
}
Check 'prune: protected names stay' { @(Select-PruneDoomed $seven 5 @('ftesurf-0.1.0.7z')) -cnotcontains 'ftesurf-0.1.0.7z' }
Check 'prune: rclone line endings trimmed' { (@(Select-PruneDoomed @("ftesurf-0.1.0.7z`r", 'ftesurf-0.1.1.7z ') 1) -join ',') -ceq 'ftesurf-0.1.0.7z' }

# --- versions ------------------------------------------------------------------------
Check 'maxversion: 2.34 beats 2.3.4 and 2.29' { (Get-MaxVersion @('2.2.5', '2.34', '2.29', '2.3.4')) -ceq '2.34' }
Check 'maxversion: junk throws' { Throws { Get-MaxVersion @('2.31', 'GLIBC_PRIVATE') } '*not a version*' }

# --- mutation control ------------------------------------------------------------------
# Each guard below is deleted from a copy of the library; its negative test must
# then FAIL, or the test was not measuring that guard.
function Test-Mutant ([string]$pattern, [scriptblock]$negative) {
    $lines = [System.IO.File]::ReadAllText($Lib) -split "`r?`n"
    $hit = @($lines | Where-Object { $_ -match $pattern })
    if ($hit.Count -ne 1) { throw "mutation pattern '$pattern' matched $($hit.Count) lines" }
    $mutant = ($lines | Where-Object { $_ -notmatch $pattern }) -join "`n"
    return & { . ([scriptblock]::Create($mutant)); & $negative }
}
Check 'mutant: no END-before-BEGIN guard -> its test fails' {
    -not (Test-Mutant 'before its BEGIN' { Throws { Split-PageBlocks "a`n<!--LINUX-END-->`n<!--LINUX-BEGIN-->`nb`n<!--LINUX-END-->`n" } '*before its BEGIN*' })
}
Check 'mutant: no owner guard -> its test fails' {
    -not (Test-Mutant 'is owned' { Has (Test-LinuxArchiveEntries (Entries (Mutated 3 '-rw-r--r-- 1000/1000 12 2026-09-19 19:00 FTESurf/a b.txt')) $H $S $T $X) '*owned 1000/1000*' })
}
Check 'mutant: no CR guard -> its test fails' {
    -not (Test-Mutant 'has CR bytes' { Throws { Read-LinuxBuildInfo (BiFile $biGood.Replace("`n", "`r`n")) } '*CR*' })
}

# --- linux-pack.sh in WSL ------------------------------------------------------------------
if ($Wsl) {
    $root = Join-Path $env:TEMP "ftesurf-t0-$PID"
    $stage = Join-Path $root 'stage dir'
    $top = Join-Path $stage 'FTESurf'
    try {
        foreach ($d in @('', 'dir with space', 'ftesurf\cfg')) { New-Item -ItemType Directory -Force -Path (Join-Path $top $d) | Out-Null }
        $files = [ordered]@{ 'ftesurf64' = "stub engine`n"; 'ftesurf.sh' = "#!/bin/sh`necho hi`n"; 'dir with space/file name.txt' = "spaced`n";
            'ftesurf/cfg/default.cfg' = "set x 1`n"; 'ftesurf/CaseFile.TXT' = "case`n" }
        foreach ($k in $files.Keys) { [System.IO.File]::WriteAllText((Join-Path $top ($k -replace '/', '\')), $files[$k], (New-Object System.Text.UTF8Encoding $false)) }
        $stageMap = OrdMap @{}
        foreach ($k in $files.Keys) { $stageMap[$k] = (Get-FileHash -LiteralPath (Join-Path $top ($k -replace '/', '\')) -Algorithm SHA256).Hash.ToLower() }
        $pack = ConvertTo-WslPath $Distro (Join-Path $PSScriptRoot 'linux-pack.sh')
        $out = "$(ConvertTo-WslPath $Distro $root)/t0.tar.xz"
        $r = Invoke-WslRaw $Distro @('sh', $pack, 'pack', (ConvertTo-WslPath $Distro $stage), 'FTESurf', $out, 'ftesurf64', 'ftesurf.sh')
        Check 'wsl: pack exits 0' { if ($r.Rc -ne 0) { Write-Host ($r.Lines -join "`n") }; $r.Rc -eq 0 }
        $v = Invoke-WslRaw $Distro @('sh', $pack, 'verify', $out, 'FTESurf')
        Check 'wsl: verify exits 0' { $v.Rc -eq 0 -and $v.Lines -ccontains 'VERIFIED' }
        $e = @(ConvertFrom-TarListing @($v.Lines | Where-Object { $_.StartsWith('T ') } | ForEach-Object { $_.Substring(2) }))
        $h = ConvertFrom-ShaLines @($v.Lines | Where-Object { $_.StartsWith('H ') } | ForEach-Object { $_.Substring(2) })
        Check 'wsl: entries match the stage (modes, owner, hashes)' {
            $p = @(Test-LinuxArchiveEntries $e $h $stageMap 'FTESurf' @('ftesurf64', 'ftesurf.sh'))
            if ($p.Count) { Write-Host ($p -join "`n") }
            $p.Count -eq 0 -and $h.Count -eq 5
        }
        Check 'wsl: 0755 exactly the exec set, spaced name 0644' {
            $x = @($e | Where-Object { $_.Mode -ceq '-rwxr-xr-x' } | ForEach-Object { $_.Path } | Sort-Object)
            ($x -join ',') -ceq 'FTESurf/ftesurf.sh,FTESurf/ftesurf64' -and
                @($e | Where-Object { $_.Path -ceq 'FTESurf/dir with space/file name.txt' -and $_.Mode -ceq '-rw-r--r--' -and $_.Uid -eq 0 }).Count -eq 1
        }
        Check 'wsl: control -- a changed stage hash is caught' {
            $bad = OrdMap @{}; foreach ($k in $stageMap.Keys) { $bad[$k] = $stageMap[$k] }; $bad['ftesurf/CaseFile.TXT'] = '0' * 64
            Has (Test-LinuxArchiveEntries $e $h $bad 'FTESurf' @('ftesurf64', 'ftesurf.sh')) '*CaseFile.TXT sha256 differs*'
        }
        $r2 = Invoke-WslRaw $Distro @('sh', $pack, 'pack', (ConvertTo-WslPath $Distro $stage), 'FTESurf', "$out.2", 'ftesurf64', 'missing')
        Check 'wsl: pack with a missing exec path fails' { $r2.Rc -ne 0 -and (Has $r2.Lines '*exec path is not a file*') -and -not (Test-Path -LiteralPath (Join-Path $root 't0.tar.xz.2')) }
    } finally { Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue }
}

Remove-Item -LiteralPath $script:tmps -Force -ErrorAction SilentlyContinue
Write-Host "$script:pass passed, $script:fail failed"
exit $script:fail
