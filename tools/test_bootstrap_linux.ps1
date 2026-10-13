# Exercise the actual release bootstrap dependency/floor block, not a duplicate gate.
param([Parameter(Mandatory)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $WorkRoot) { throw 'fresh owned work root required' }
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
Set-Content -LiteralPath (Join-Path $WorkRoot 'OWNER.md') -Value 'Owned Linux bootstrap gate controls; no builds/network/publication. Retain results.'
$release = Join-Path $PSScriptRoot '../src/release/release.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Resolve-Path $release), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'release script parse failed' }
$blocks = @($ast.FindAll({ param($n) $n -is [Management.Automation.Language.IfStatementAst] -and $n.Extent.Text.Contains('$bootstrapGlibcs =') }, $true))
if ($blocks.Count -ne 1) { throw 'cannot uniquely identify production bootstrap floor block' }
$block = [scriptblock]::Create($blocks[0].Extent.Text)
$allow = @($ast.ParamBlock.Parameters | Where-Object { $_.Name.VariablePath.UserPath -eq 'LinuxNeededAllow' })
if ($allow.Count -ne 1) { throw 'cannot identify production dependency allowlist' }
$defaultAllow = $allow[0].DefaultValue.SafeGetValue()
. (Join-Path $PSScriptRoot '../src/release/bootstrap.ps1')
. (Join-Path $PSScriptRoot '../src/release/releaselib.ps1')
function Test-ElfX64 { return $true }
function WslPath ($p) { return $p }
function Good ($text) {}
function Fail ($text) { throw $text }
$results = @()
foreach ($case in @(
    @{ name = 'supported'; engine = '2.31'; floor = '2.31'; needed = 'libc.so.6'; error = $null },
    @{ name = 'compiler-runtime'; engine = '2.31'; floor = '2.30'; needed = 'libgcc_s.so.1'; error = $null },
    @{ name = 'host-is-not-baseline'; engine = '2.31'; floor = '2.34'; needed = 'libc.so.6'; error = '2.31' },
    @{ name = 'engine-is-not-baseline'; engine = '2.34'; floor = '2.31'; needed = 'libc.so.6'; error = '2.31' },
    @{ name = 'missing-symbols'; engine = '2.31'; floor = ''; needed = 'libc.so.6'; error = 'no measured glibc floor' },
    @{ name = 'unapproved-dependency'; engine = '2.31'; floor = '2.31'; needed = 'libssl.so.3'; error = 'not in -LinuxNeededAllow' }
)) {
    $Linux = $true; $LinuxPackWsl = 'unused'; $linuxBootstrap = @{ binary = 'unused' }
    $LinuxNeededAllow = $defaultAllow; $lxNeeded = [ordered]@{}
    $lxGlibc = $case.engine; $lxHostGlibc = '2.35'
    function Invoke-Wsl {
        "N ftesurf-launcher $($case.needed)"
        if ($case.floor) { "G ftesurf-launcher GLIBC_$($case.floor)" }
    }
    $reason = $null
    try { . $block } catch { $reason = $_.Exception.Message }
    if ($case.error) {
        if (-not $reason -or -not $reason.Contains($case.error)) { throw "$($case.name): expected '$($case.error)', got '$reason' (combined floor $lxGlibc)" }
    } else {
        if ($reason -or $lxGlibc -ne '2.31' -or $lxNeeded['ftesurf-launcher'] -cne $case.needed) { throw "$($case.name): baseline did not act: $reason / $lxGlibc" }
    }
    $results += @{ case = $case.name; reason = $reason; combined_floor = $lxGlibc }
    Write-Host "PASS $($case.name)"
}
$results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $WorkRoot 'result.json')
