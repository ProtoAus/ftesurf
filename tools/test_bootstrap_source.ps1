# Source/provenance falsifiers, not a substitute for the real Rust build/runtime test.
param([Parameter(Mandatory)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (Test-Path -LiteralPath $WorkRoot) { throw 'use a fresh owned fixture root' }
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
Set-Content -LiteralPath (Join-Path $WorkRoot 'OWNER.md') -Value 'Owned bootstrap source unit fixtures. Retain evidence; no product commits/builds.'
. (Join-Path $PSScriptRoot '../src/release/bootstrap.ps1')
$tree = Join-Path $WorkRoot 'source'
New-Item -ItemType Directory -Path $tree | Out-Null
try { Get-BootstrapSource $tree; throw 'missing source incorrectly accepted' }
catch { if ($_.Exception.Message -notlike 'bootstrap source missing: Cargo.toml*') { throw } }
Write-Host 'PASS missing source refuses instead of selecting a stale executable'
New-Item -ItemType Directory -Path (Join-Path $tree 'src') | Out-Null
$files = @('Cargo.toml', 'Cargo.lock', 'LICENSE', 'src/ftesurf.rs', 'src/ftesurf_update.rs')
foreach ($f in $files) { Set-Content -LiteralPath (Join-Path $tree $f) -Value "owned fixture $f" }
& git -C $tree init -q
if ($LASTEXITCODE) { throw 'fixture git init failed' }
& git -C $tree config user.name 'Bootstrap fixture'
if ($LASTEXITCODE) { throw 'fixture git config failed' }
& git -C $tree config user.email 'bootstrap-fixture@example.invalid'
if ($LASTEXITCODE) { throw 'fixture git config failed' }
& git -C $tree add -- @files
if ($LASTEXITCODE) { throw 'fixture git add failed' }
& git -C $tree commit -q -m 'Owned bootstrap source fixture' -- @files
if ($LASTEXITCODE) { throw 'fixture git commit failed' }
$before = Get-BootstrapSource $tree
if ($before.dirty_source.Count) { throw 'clean fixture source incorrectly dirty' }
$path = Join-Path $tree 'src/ftesurf_update.rs'
$original = [IO.File]::ReadAllBytes($path)
try {
    Add-Content -LiteralPath $path -Value '// owned source delta'
    $after = Get-BootstrapSource $tree
    if ($after.commit -ne $before.commit -or $after.source_sha256 -eq $before.source_sha256 -or -not $after.dirty_source.Count) {
        throw 'dirty source hash/status failed to distinguish same-commit mutation'
    }
    Write-Host 'PASS same-commit source mutation changes fingerprint and dirty status'
} finally { [IO.File]::WriteAllBytes($path, $original) }
$restored = Get-BootstrapSource $tree
if ($restored.source_sha256 -ne $before.source_sha256 -or $restored.dirty_source.Count) { throw 'source restoration not exact' }
$outside = Join-Path $WorkRoot 'link-target.txt'
Set-Content -LiteralPath $outside -Value 'owned external link target'
Remove-Item -LiteralPath $path
try {
    New-Item -ItemType SymbolicLink -Path $path -Target $outside | Out-Null
    try { Get-BootstrapSource $tree; throw 'linked source incorrectly accepted' }
    catch { if ($_.Exception.Message -ne 'linked bootstrap source is not allowed') { throw } }
    Write-Host 'PASS real linked source refused'
} finally {
    if (Test-Path -LiteralPath $path) {
        if (-not ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'unexpected replacement of owned link' }
        Remove-Item -LiteralPath $path
    }
    [IO.File]::WriteAllBytes($path, $original)
}
$restored = Get-BootstrapSource $tree
if ($restored.source_sha256 -ne $before.source_sha256 -or $restored.dirty_source.Count) { throw 'linked source restoration not exact' }
Write-Host 'PASS exact source restoration after both negative controls'
