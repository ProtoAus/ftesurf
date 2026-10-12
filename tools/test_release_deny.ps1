# Physical stage/archive controls using release.ps1's ACTUAL tripwire, never publication.
param([Parameter(Mandatory)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $WorkRoot) { throw 'use a fresh owned test root' }
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
Set-Content -LiteralPath (Join-Path $WorkRoot 'OWNER.md') -Value 'Owned release deny fixtures; tiny stages/archives only, retained updater evidence.'
$release = Join-Path $PSScriptRoot '../src/release/release.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($release, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'release script parse failed' }
$assignment = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left -is [Management.Automation.Language.VariableExpressionAst] -and
        $node.Left.VariablePath.UserPath -eq 'DenyPatterns'
}, $true)
$function = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Test-Deny'
}, $true)
if (-not $assignment -or -not $function) { throw 'production deny policy/function missing' }
# Evaluate only these inspected production definitions, not release execution/network code.
Invoke-Expression $assignment.Extent.Text
function Fail([string]$Message) { throw $Message }
Invoke-Expression $function.Extent.Text
$sevenzip = 'C:/Program Files/7-Zip/7z.exe'
$good = @('ftesurf/data/mapdl.txt', 'ftesurf/maps/zones/local/surf_fixture.json',
          'ftesurf/gfx/fonts/Roboto.ttf', 'ftesurf/gfx/fonts/FONTS.md', 'ftesurf/gfx/fonts/OFL.txt')
$bad = @('ftesurf/data/mapdl.net.txt', 'ftesurf/data/mapdl.net.tmp', 'ftesurf/data/mapbuild.txt',
         'ftesurf/maps/settings/local/surf_fixture.cfg', 'ftesurf/data/maps/settings/local/surf_fixture.cfg',
         'ftesurf/gfx/fonts/Roboto.ttf.prev', 'FTESURF/DATA/MAPBUILD.TXT')
function Put-File([string]$Stage, [string]$Relative) {
    $target = Join-Path $Stage $Relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Set-Content -LiteralPath $target -Value 'owned tiny tripwire fixture'
}
function Get-StagePaths([string]$Stage) {
    @(Get-ChildItem -LiteralPath $Stage -Recurse -File | ForEach-Object {
        $_.FullName.Substring($Stage.Length + 1).Replace('\', '/')
    })
}
function Get-ArchivePaths([string]$Archive) {
    $lines = & $sevenzip l -ba -slt $Archive
    if ($LASTEXITCODE -ne 0) { throw '7z listing failed' }
    $current = $null
    foreach ($line in $lines) {
        if ($line.StartsWith('Path = ')) { $current = $line.Substring(7).Replace('\', '/') }
        elseif ($line.StartsWith('Attributes = ') -and $current) {
            if ($line -notmatch 'D') { $current }
            $current = $null
        }
    }
}
$results = @()
for ($i = -1; $i -lt $bad.Count; $i++) {
    $stage = Join-Path $WorkRoot "stage-$i"
    foreach ($path in $good) { Put-File $stage $path }
    if ($i -ge 0) { Put-File $stage $bad[$i] }
    $archive = Join-Path $WorkRoot "fixture-$i.7z"
    Push-Location $stage
    try { & $sevenzip a -t7z -mx=0 -bso0 -bsp0 $archive '.\*' | Out-Null } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw '7z pack failed' }
    foreach ($kind in @('stage', 'archive')) {
        $paths = if ($kind -eq 'stage') { @(Get-StagePaths $stage) } else { @(Get-ArchivePaths $archive) }
        $expected = $good.Count + $(if ($i -ge 0) { 1 } else { 0 })
        if ($paths.Count -ne $expected) { throw 'fixture paths were not materialised/listed' }
        $denied = $false
        try { Test-Deny $paths $kind } catch {
            if ($i -lt 0 -or $_.Exception.Message -notlike 'DENY TRIPWIRE tripped*' -or
                $_.Exception.Message -notlike "*$($bad[$i])*") { throw }
            $denied = $true
        }
        if ($denied -ne ($i -ge 0)) { throw "tripwire did not act for $kind fixture $i" }
        $results += [ordered]@{ fixture = $i; kind = $kind; paths = $paths.Count; denied = $denied }
    }
}
$results | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $WorkRoot 'result.json')
Write-Host "PASS production tripwire: real baseline stage/archive allowed; $($bad.Count) runtime/backup paths individually refused in both materialised stages and physical archives."
