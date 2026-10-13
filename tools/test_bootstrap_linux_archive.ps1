# Actual production tar/required-entry policy against real baseline and mutants.
param([Parameter(Mandatory)][string]$EvidenceRoot, [Parameter(Mandatory)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $WorkRoot) { throw 'fresh owned work root required' }
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
Set-Content (Join-Path $WorkRoot 'OWNER.md') 'Owned Linux real-archive policy verification; no builds/network. Retain result.'
. (Join-Path $PSScriptRoot '../src/release/releaselib.ps1')
. (Join-Path $PSScriptRoot '../src/release/bootstrap.ps1')
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot '../src/release/release.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'release script parse failed' }
function Production-Array ($name) {
    $matches = @($ast.FindAll({ param($n) $n -is [Management.Automation.Language.AssignmentStatementAst] -and $n.Left -is [Management.Automation.Language.VariableExpressionAst] -and $n.Left.VariablePath.UserPath -ceq $name }, $true))
    if ($matches.Count -ne 1) { throw "cannot identify production $name" }
    $array = $matches[0].Right.Find({ param($n) $n -is [Management.Automation.Language.ArrayExpressionAst] }, $true)
    if ($null -eq $array) { throw "production $name is not a literal array" }
    return $array.SafeGetValue()
}
$exec = Production-Array 'LinuxExec'
$required = Production-Array 'LinuxRequired'
$inputData = Get-Content -Raw (Join-Path $EvidenceRoot 'policy-input.json') | ConvertFrom-Json
$stage = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
foreach ($prop in $inputData.stage.PSObject.Properties) { $stage[$prop.Name] = $prop.Value }
function Assert-BoundArchive ($description) {
    $name = $description.archive
    if (-not $name -or [IO.Path]::GetFileName($name) -cne $name) { throw 'archive name must be an evidence-relative basename' }
    $archive = Join-Path $EvidenceRoot $name
    $stem = [IO.Path]::GetFileNameWithoutExtension($name)
    $log = Join-Path $EvidenceRoot "$stem-verify.log"
    foreach ($item in @(@($archive, $description.archive_sha256), @($log, $description.verify_log_sha256))) {
        if (-not (Test-Path -LiteralPath $item[0] -PathType Leaf)) { throw "bound evidence missing: $($item[0])" }
        if (-not $item[1] -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -cne $item[1]) { throw "bound evidence SHA256 changed: $($item[0])" }
    }
}
# Preflight the whole physical evidence set BEFORE emitting any policy PASS.
foreach ($description in @($inputData.baseline) + @($inputData.mutants)) { Assert-BoundArchive $description }
function Check-Archive ($description, $stageMap) {
    Assert-BoundArchive $description
    $stem = [IO.Path]::GetFileNameWithoutExtension($description.archive)
    $lines = @(Get-Content -LiteralPath (Join-Path $EvidenceRoot "$stem-verify.log"))
    if ($lines -cnotcontains 'VERIFIED') { throw 'no actual shell verify completion' }
    $entries = @(ConvertFrom-TarListing @($lines | Where-Object { $_.StartsWith('T ') } | ForEach-Object { $_.Substring(2) }))
    $hashes = ConvertFrom-ShaLines @($lines | Where-Object { $_.StartsWith('H ') } | ForEach-Object { $_.Substring(2) })
    $problems = @(Test-LinuxArchiveEntries $entries $hashes $stageMap 'FTESurf' $exec)
    $rel = @($entries | Where-Object { $_.Type -eq '-' } | ForEach-Object { $_.Path.Substring(8) })
    try { Assert-BootstrapEntries $rel 'linux64' } catch { $problems += $_.Exception.Message }
    foreach ($must in $required) { if ($rel -cnotcontains $must) { $problems += "missing required file FTESurf/$must" } }
    Assert-BoundArchive $description
    return $problems
}
$baseline = @(Check-Archive $inputData.baseline $stage)
if ($baseline.Count) { throw "baseline rejected: $($baseline -join '; ')" }
Write-Host 'PASS production full-baseline archive policy'
$results = @(@{ name = 'baseline'; problems = $baseline })
foreach ($mutant in $inputData.mutants) {
    $problems = @(Check-Archive $mutant $stage)
    $want = switch ($mutant.name) {
        'missing-bootstrap' { 'FTESurf/ftesurf-launcher is staged but not in the archive' }
        'missing-notices' { 'FTESurf/notices/bootstrap.txt is staged but not in the archive' }
        'bootstrap-not-executable' { 'FTESurf/ftesurf-launcher is -rw-r--r--, not -rwxr-xr-x' }
        'notices-executable' { 'FTESurf/notices/bootstrap.txt is -rwxr-xr-x, not -rw-r--r--' }
        'notices-byte-change' { 'FTESurf/notices/bootstrap.txt sha256 differs from the stage' }
        default { throw 'unknown archive mutant' }
    }
    if ($problems -cnotcontains $want) { throw "$($mutant.name): expected exact problem '$want', got $($problems -join '; ')" }
    $results += @{ name = $mutant.name; problems = $problems }
    Write-Host "PASS production policy refuses $($mutant.name)"
    if ($mutant.name.StartsWith('missing-')) {
        $absentStage = [Collections.Generic.Dictionary[string,string]]::new($stage, [StringComparer]::Ordinal)
        [void]$absentStage.Remove($mutant.target)
        $both = @(Check-Archive $mutant $absentStage)
        $requiredProblem = "missing required file FTESurf/$($mutant.target)"
        if ($both -cnotcontains $requiredProblem -or @($both | Where-Object { $_ -like '*staged but not in*' }).Count) { throw 'required-entry policy did not independently act' }
        $results += @{ name = "$($mutant.name)-also-absent-stage"; problems = $both }
        Write-Host "PASS independent required-entry refusal $($mutant.target) absent from stage AND archive"
    }
}
$results | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $WorkRoot 'result.json')
