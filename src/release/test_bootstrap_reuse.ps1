# test_bootstrap_reuse.ps1 -- falsifier for the Linux-host release path (bootstrap.ps1 Use-PublishedBootstrap,
# releaselib.ps1 Invoke-NativeRaw).
#
#   pwsh -NoProfile -File src/release/test_bootstrap_reuse.ps1
#
# Prints `N passed, M failed` and exits M. The mutation control loads a copy of bootstrap.ps1 with the source
# fingerprint check deleted and requires the "other source" refusal to fail there.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'releaselib.ps1')
. (Join-Path $PSScriptRoot 'bootstrap.ps1')

$script:pass = 0; $script:fail = 0
function Check ([string]$name, [scriptblock]$test) {
    $err = $null
    try { $ok = & $test } catch { $ok = $false; $err = $_.Exception.Message }
    if ($ok -eq $true) { $script:pass++ } else { $script:fail++; Write-Host "FAIL  $name$(if ($err) { "  ($err)" })" -ForegroundColor Red }
}
function Throws ([scriptblock]$b, [string]$like = '*') {
    try { & $b | Out-Null } catch { return $_.Exception.Message -like $like }
    return $false
}

$root = Join-Path ([IO.Path]::GetTempPath()) ('bootreuse-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    # A minimal x86-64 PE: MZ, e_lfanew = 64, "PE\0\0", machine 0x8664.
    $pe = [byte[]]::new(256); $pe[0] = 0x4D; $pe[1] = 0x5A; $pe[60] = 64
    $pe[64] = 0x50; $pe[65] = 0x45; $pe[68] = 0x64; $pe[69] = 0x86
    $commit = 'a' * 40; $srcSha = 'b' * 64
    function Fixture ([string]$name, [byte[]]$bytes, [hashtable]$over = @{}) {
        $d = Join-Path $root $name; New-Item -ItemType Directory -Path $d | Out-Null
        [IO.File]::WriteAllBytes((Join-Path $d 'WOS-Launcher-0.1.48.exe'), $bytes)
        $sha = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes))
        $b = [ordered]@{ commit = $commit; source_sha256 = $srcSha; dirty_source = @(); rustc = 'rustc 1.97.1'; target = 'x86_64-pc-windows-msvc'
            sha256 = $sha; builder = 'native Windows Cargo'; policy = 'p' }
        foreach ($k in $over.Keys) { $b[$k] = $over[$k] }
        $meta = [ordered]@{ version = '0.1.48'; bootstrap = $b
            bootstrap_downloads = @([ordered]@{ platform = 'win64'; name = 'WOS-Launcher-0.1.48.exe'; url = 'https://invalid.example/x'; sha256 = $sha.ToLower(); bytes = $bytes.Length }) }
        [IO.File]::WriteAllText((Join-Path $d 'version.json'), ($meta | ConvertTo-Json -Depth 6))
        return $d
    }
    $source = [ordered]@{ root = $root; commit = $commit; source_sha256 = $srcSha; dirty_source = @() }

    $good = Fixture 'good' $pe
    Check 'same source and bytes: accepted, provenance names the reuse' {
        $r = Use-PublishedBootstrap $source $good
        ($r.provenance.target -ceq 'x86_64-pc-windows-msvc') -and ($r.provenance.builder -like 'published 0.1.48 bootstrap reused*') -and
            ($r.provenance.commit -ceq $commit) -and (Test-Path -LiteralPath $r.binary)
    }
    Check 'no folder: refused' { Throws { Use-PublishedBootstrap $source '' } '*cannot build the Windows bootstrap*' }
    $other = Fixture 'other-source' $pe @{ source_sha256 = 'c' * 64 }
    Check 'other source fingerprint: refused' { Throws { Use-PublishedBootstrap $source $other } '*other source*' }
    $otherCommit = Fixture 'other-commit' $pe @{ commit = 'd' * 40 }
    Check 'other commit: refused' { Throws { Use-PublishedBootstrap $source $otherCommit } '*other source*' }
    $dirty = Fixture 'dirty' $pe @{ dirty_source = @(' M src/x.rs') }
    Check 'dirty published source: refused' { Throws { Use-PublishedBootstrap $source $dirty } '*dirty*' }
    $linux = Fixture 'linux-target' $pe @{ target = 'x86_64-unknown-linux-gnu' }
    Check 'non-Windows target: refused' { Throws { Use-PublishedBootstrap $source $linux } '*not Windows x86_64*' }
    $tamper = Fixture 'tampered' $pe
    $tb = [IO.File]::ReadAllBytes((Join-Path $tamper 'WOS-Launcher-0.1.48.exe')); $tb[200] = 1
    [IO.File]::WriteAllBytes((Join-Path $tamper 'WOS-Launcher-0.1.48.exe'), $tb)
    Check 'bytes that differ from the record: refused' { Throws { Use-PublishedBootstrap $source $tamper } '*does not hash*' }
    $notpe = [byte[]]::new(256); $notpe[0] = 0x7F; $notpe[1] = 0x45
    $elf = Fixture 'not-pe' $notpe
    Check 'not a PE file: refused' { Throws { Use-PublishedBootstrap $source $elf } '*not an x86-64 PE*' }
    $dirtyNow = [ordered]@{ root = $root; commit = $commit; source_sha256 = $srcSha; dirty_source = @('?? new.rs') }
    Check 'dirty current source: refused' { Throws { Use-PublishedBootstrap $dirtyNow $good } '*dirty*' }

    if (-not (Test-WindowsHost)) {
        Check 'Invoke-NativeRaw: exit code and lines' {
            $r = Invoke-NativeRaw @('sh', '-c', 'echo one; echo two; exit 3')
            ($r.Rc -eq 3) -and ($r.Lines -join ',') -ceq 'one,two'
        }
    }

    # Mutation control: without the fingerprint check the other-source fixture must be accepted.
    $mut = Join-Path $root 'bootstrap-mutant.ps1'
    $text = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'bootstrap.ps1'))
    $guard = "if (`$b['commit'] -cne `$Source.commit -or `$b['source_sha256'] -cne `$Source.source_sha256) {"
    if (-not $text.Contains($guard)) { throw 'mutation control: guard text not found' }
    [IO.File]::WriteAllText($mut, $text.Replace($guard, 'if ($false) {'))
    . $mut
    Check 'mutation control: the fingerprint guard is what refuses other source' { -not (Throws { Use-PublishedBootstrap $source $other } '*other source*') }
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "$script:pass passed, $script:fail failed"
exit $script:fail
