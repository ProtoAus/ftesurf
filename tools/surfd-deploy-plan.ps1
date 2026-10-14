# Pure local exact-commit planner shared by surfd-deploy and its offline tests.
# No SSH, installation, local scratch tree or live-data access here.
Set-StrictMode -Version Latest

function Get-SurfdDeployPlan {
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][string]$Ref,
        [string[]]$Only
    )
    $commit = & git -C $Repo rev-parse --verify --end-of-options "$Ref^{commit}" 2>$null
    if ($LASTEXITCODE -ne 0 -or "$commit" -notmatch '^[0-9a-f]{40}$') {
        throw "could not resolve -Ref '$Ref' to a commit"
    }
    $tree = @(& git -C $Repo ls-tree -r $commit -- surfd tools src/shared)
    if ($LASTEXITCODE -ne 0) { throw "could not list commit $commit" }
    $modeByPath = @{}
    foreach ($entry in $tree) {
        if ($entry -match '^([0-9]{6}) blob [0-9a-f]+\t(.+)$') {
            $modeByPath[$Matches[2]] = $Matches[1]
        }
    }
    $all = @($modeByPath.Keys)
    $suite = @($all | Where-Object {
        $_ -match '^surfd/.*\.(py|js|css|html|sh|nginx|sudoers)$' -and
        $_ -notmatch '/__pycache__/'
    })
    $codecs = @('tools/ksfconvert.py', 'tools/ksfreplay_info.py')
    $allowed = @($suite) + @($codecs | Where-Object { $all -contains $_ })
    $files = @($suite)
    if ($Only) {
        foreach ($file in $Only) {
            if ($allowed -notcontains $file) {
                throw "-Only path '$file' is not a deployable file at $commit"
            }
        }
        $files = @($Only | Sort-Object -Unique)
    }
    # Both importer entrypoints depend on this exact generation of the app and
    # each other; ksfconvert also imports ksfreplay_info. Do not permit a partial
    # P706 KSF ship-set. Older commits without ksfgrab retain their old layout.
    $added = @()
    if ($all -contains 'surfd/ksfgrab.py' -and
        (@($files | Where-Object {
            $_ -in @('surfd/ksfgrab.py', 'surfd/ksfimport.py') + $codecs
        }).Count -gt 0)) {
        $required = @('surfd/surfd.py', 'surfd/ksfimport.py', 'surfd/ksfgrab.py') + $codecs
        foreach ($file in $required) {
            if ($all -notcontains $file) { throw "KSF runtime dependency '$file' is absent at $commit" }
            if ($files -notcontains $file) { $added += $file; $files += $file }
        }
    }
    $files = @($files | Sort-Object -Unique)
    if (-not $files.Count) { throw "nothing to deploy at $commit" }
    $extra = @($all | Where-Object { $_ -match '^(tools|src/shared)/.*\.py$' })
    # The test stage always contains the complete app, even with -Only. Tools
    # are staged beside surfd, but only the two allowlisted codecs may ship.
    $staged = @(@($suite) + @($extra) | Sort-Object -Unique)
    $modes = @()
    foreach ($file in $files) {
        $mode = $modeByPath[$file]
        if ($mode -notin @('100644', '100755')) {
            throw "unsupported deploy file mode for '$file' at $commit"
        }
        $modes += $(if ($mode -eq '100755') { '755' } else { '644' })
    }
    [pscustomobject]@{
        Commit = "$commit"
        Files = $files
        Modes = $modes
        Destinations = @($files | ForEach-Object { $_ -replace '^surfd/', '' })
        AddedDependencies = $added
        StageFiles = $staged
    }
}
