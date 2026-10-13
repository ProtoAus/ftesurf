# Execute actual release generation/object-publication/site-copy AST with a byte-copying R2 mock.
param([Parameter(Mandatory)][string]$FixtureRoot, [Parameter(Mandatory)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (Test-Path -LiteralPath $WorkRoot) { throw 'fresh owned work root required' }
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
Set-Content -LiteralPath (Join-Path $WorkRoot 'OWNER.md') -Value 'Owned network-mocked updater publication controls; synthetic keys/stages only. Retain results.'
$release = Join-Path $PSScriptRoot '../src/release/release.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Resolve-Path $release), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'production release parse failed' }
function OneBlock ($predicate) {
    $nodes = @($ast.FindAll($predicate, $true))
    if ($nodes.Count -ne 1) { throw "expected unique production AST node, got $($nodes.Count): $predicate" }
    return [scriptblock]::Create($nodes[0].Extent.Text)
}
$native = OneBlock { param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Native' }
. $native
$generate = OneBlock { param($n) $n -is [Management.Automation.Language.AssignmentStatementAst] -and $n.Extent.Text.StartsWith('$updateFeed = New-UpdateFeed') }
$publish = OneBlock { param($n) $n -is [Management.Automation.Language.IfStatementAst] -and $n.Extent.Text.StartsWith('if (-not $SkipUpload -or -not $SkipSite)') }
$feedPathBlock = OneBlock { param($n) $n -is [Management.Automation.Language.AssignmentStatementAst] -and $n.Extent.Text.StartsWith('$feedPath = Join-Path $updateFeed.Root') }
$copyGuard = OneBlock { param($n) $n -is [Management.Automation.Language.IfStatementAst] -and $n.Extent.Text.StartsWith('if ((Get-FileHash -LiteralPath $feedPath') -and $n.Extent.Text.Contains("Fail 'generated update feed changed before site deployment'") }
$copyFeed = OneBlock { param($n) $n -is [Management.Automation.Language.CommandAst] -and $n.Extent.Text.StartsWith('Copy-Item -LiteralPath $feedPath -Destination') }
$copyProof = OneBlock { param($n) $n -is [Management.Automation.Language.CommandAst] -and $n.Extent.Text.StartsWith('Copy-Item -LiteralPath $updateProof -Destination') }
. (Join-Path $PSScriptRoot '../src/release/updatefeed.ps1')
function Fail ($m) { throw $m }
function Info ($m) { $script:Calls.Add("actor $m") }
function Step ($m) { $script:Calls.Add("step $m") }
function Get-BwLimit { '3M' }
$fixture = Get-Content -LiteralPath (Join-Path $FixtureRoot 'fixture.json') -Raw | ConvertFrom-Json
$SurfDir = $FixtureRoot
$StageDir = Join-Path $FixtureRoot 'win'
$LxTree = Join-Path $FixtureRoot 'linux'
$DlBase = 'https://mock.invalid'; $Prefix = 'ftesurf'; $Remote = 'mock'; $Bucket = 'bucket'
$UpdateSeedFile = Join-Path $FixtureRoot 'seed'
function rclone {
    $script:Calls.Add("rclone $($args[0]) $($args[1]) -> $($args[2])")
    $global:LASTEXITCODE = 0
    if ($args[0] -cne 'copy') { throw 'unexpected mock R2 operation' }
    $listIndex = [array]::IndexOf($args, '--files-from-raw')
    if ($listIndex -lt 0) { throw 'production did not restrict object closure' }
    $names = @(Get-Content -LiteralPath $args[$listIndex + 1])
    $put = $args[2] -ceq 'mock:bucket/ftesurf/update/objects'
    $src = if ($put) { $args[1] } else { $script:R2 }
    $dst = if ($put) { $script:R2 } else { $args[2] }
    if ($put -and ($args -cnotcontains '--immutable' -or $args -cnotcontains '--checksum')) { throw 'missing immutable/checksum flags' }
    foreach ($name in $names) {
        $source = Join-Path $src $name; $target = Join-Path $dst $name
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
        if ($put -and (Test-Path -LiteralPath $target)) {
            if ((Get-FileHash -LiteralPath $target).Hash -cne (Get-FileHash -LiteralPath $source).Hash) {
                $global:LASTEXITCODE = 9; return 'immutable object collision'
            }
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $target
    }
    if (-not $put -and $script:Fault -in @('missing-linux', 'corrupt-linux')) {
        $target = Join-Path $dst $fixture.linux_object
        if ($script:Fault -ceq 'missing-linux') { Remove-Item -LiteralPath $target }
        else { [IO.File]::WriteAllBytes($target, [byte[]]@(1,2,3)) }
        $script:Calls.Add("fault-acted $script:Fault $($fixture.linux_object)")
    }
}
$results = @()
foreach ($case in @(
    @{ name='first-both'; first=$true; linux=$true; skip=$false; fault=''; error='' },
    @{ name='first-windows-only'; first=$true; linux=$false; skip=$false; fault=''; error='Windows AND Linux' },
    @{ name='prior-retained-linux'; first=$false; linux=$false; skip=$false; fault=''; error='' },
    @{ name='invalid-prior-empty'; first=$false; linux=$false; skip=$false; fault=''; prior='empty'; error='Expecting value' },
    @{ name='invalid-prior-object'; first=$false; linux=$false; skip=$false; fault=''; prior='object'; error='unsupported update feed' },
    @{ name='invalid-prior-null'; first=$false; linux=$false; skip=$false; fault=''; prior='null'; error='must be an object' },
    @{ name='missing-linux'; first=$false; linux=$false; skip=$false; fault='missing-linux'; error='missing referenced object' },
    @{ name='corrupt-linux'; first=$false; linux=$false; skip=$false; fault='corrupt-linux'; error='corrupt referenced object' },
    @{ name='immutable-collision'; first=$false; linux=$false; skip=$false; fault='collision'; error='immutable object collision' },
    @{ name='skip-upload-existing'; first=$false; linux=$false; skip=$true; fault=''; error='' },
    @{ name='skip-upload-missing-linux'; first=$false; linux=$false; skip=$true; fault='missing-linux'; error='missing referenced object' }
)) {
    $script:Calls = [Collections.Generic.List[string]]::new()
    $root = Join-Path $WorkRoot $case.name
    New-Item -ItemType Directory -Path $root | Out-Null
    $script:R2 = Join-Path $root 'remote-objects'
    New-Item -ItemType Directory -Path $script:R2 | Out-Null
    $OutDir = Join-Path $root 'dist'
    New-Item -ItemType Directory -Path $OutDir | Out-Null
    $pageDir = Join-Path $root 'site'
    New-Item -ItemType Directory -Path $pageDir | Out-Null
    $Ver = '0.1.25'; $Linux = $case.linux
    $FirstUpdateFeed = [switch]$case.first
    $PreviousUpdateFeed = if ($case.first) { '' } elseif ($case.ContainsKey('prior')) {
        Join-Path $FixtureRoot ("invalid-prior-$($case.prior).json")
    } else { Join-Path $FixtureRoot 'prior/update.json' }
    $PreviousUpdateObjects = if ($case.first) { '' } else { Join-Path $FixtureRoot 'prior/objects' }
    $SkipUpload = [switch]$case.skip; $SkipSite = $false
    $script:Fault = $case.fault
    if ($case.skip) { Copy-Item -Path (Join-Path $FixtureRoot 'prior/objects/*') -Destination $script:R2 -Recurse }
    if ($case.fault -ceq 'collision') {
        $p = Join-Path $script:R2 $fixture.linux_object
        New-Item -ItemType Directory -Path (Split-Path -Parent $p) | Out-Null
        [IO.File]::WriteAllBytes($p, [byte[]]@(9,8,7))
        $script:Calls.Add('fault-acted immutable-collision')
    }
    $reason = $null
    try {
        . $generate
        . $publish
        . $feedPathBlock
        . $copyGuard
        . $copyFeed
        . $copyProof
        $script:Calls.Add('site-feed-advertisement-ready')
    } catch { $reason = $_.Exception.Message }
    $advertised = Test-Path -LiteralPath (Join-Path $pageDir 'update.json')
    if ($case.error) {
        if (-not $reason -or -not $reason.Contains($case.error) -or $advertised) { throw "$($case.name): expected '$($case.error)' without advertisement, got '$reason' / $advertised" }
        if ($case.ContainsKey('prior')) {
            if (@(Get-ChildItem -LiteralPath $OutDir -Filter update.json -Recurse).Count -or
                @($script:Calls | Where-Object { $_.StartsWith('rclone ') }).Count) {
                throw 'invalid prior reached signed-feed output or network publication'
            }
        }
    } else {
        if ($reason -or -not $advertised) { throw "$($case.name): failed positive actor: $reason" }
        $proof = Get-Content -LiteralPath (Join-Path $pageDir 'update-verified.json') -Raw | ConvertFrom-Json
        if ($proof.feed_sha256 -cne (Get-FileHash -LiteralPath (Join-Path $pageDir 'update.json')).Hash.ToLower() -or $proof.verification -cne 'r2-roundtrip-blake2b-256') { throw 'proof binding failed' }
        $download = @($script:Calls | Where-Object { $_.StartsWith('rclone copy mock:') })
        $verified = @($script:Calls | Where-Object { $_.StartsWith('actor verified ') })
        if ($download.Count -ne 1 -or $verified.Count -ne 2 -or $script:Calls[-1] -cne 'site-feed-advertisement-ready') { throw 'publication actors/order incomplete' }
        if ($case.skip -and @($script:Calls | Where-Object { $_.StartsWith('rclone copy ') }).Count -ne 1) { throw 'SkipUpload unexpectedly wrote storage' }
    }
    $results += @{ case=$case.name; reason=$reason; advertised=$advertised; calls=@($script:Calls) }
    Write-Host "PASS $($case.name)"
}
$results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $WorkRoot 'result.json')
