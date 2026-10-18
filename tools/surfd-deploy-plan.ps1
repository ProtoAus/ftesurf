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
    $tree = @(& git -C $Repo ls-tree -r $commit -- surfd tools src/shared src/release/ftesurf.nginx)
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
    $ksfEntries = @('surfd/ksfgrab.py', 'surfd/ksfimport.py') + $codecs
    if ($all -contains 'surfd/ksfprofile.py') {
        # Schema18/app and the paced worker must move together, even -Only app.
        $ksfEntries += @('surfd/surfd.py', 'surfd/ksfprofile.py')
    }
    # Schema20 routes, schema migration and social implementation form one
    # generation. Close both groups: selecting accounts can add app, and a KSF
    # selection can add app too. Always inspect COMMIT paths, not tree files.
    $socialEntries = @('surfd/surfd.py', 'surfd/accounts.py', 'surfd/social.py')
    # Pool policy, file-zone index, admin writer/template and completion readers
    # are one generation; an app-only swap must not leave an older signature.
    $mapEntries = @('surfd/surfd.py', 'surfd/admin.py', 'surfd/mapmanifest.py',
                    'surfd/templates/admin_maps.html')
    $hidEntries = @('surfd/surfd.py', 'surfd/hidupload.py')
    do {
        $before = $files.Count
        if ($all -contains 'surfd/hidupload.py' -and
            (@($files | Where-Object { $_ -in $hidEntries }).Count -gt 0)) {
            foreach ($file in $hidEntries) {
                if ($files -notcontains $file) { $added += $file; $files += $file }
            }
        }
        if ($all -contains 'surfd/mapmanifest.py' -and
            (@($files | Where-Object { $_ -in $mapEntries }).Count -gt 0)) {
            foreach ($file in $mapEntries) {
                if ($all -notcontains $file) { throw "map-pool runtime dependency '$file' is absent at $commit" }
                if ($files -notcontains $file) { $added += $file; $files += $file }
            }
        }
        if ($all -contains 'surfd/social.py' -and
            (@($files | Where-Object { $_ -in $socialEntries }).Count -gt 0)) {
            foreach ($file in $socialEntries) {
                if ($all -notcontains $file) { throw "social runtime dependency '$file' is absent at $commit" }
                if ($files -notcontains $file) { $added += $file; $files += $file }
            }
        }
        if ($all -contains 'surfd/ksfgrab.py' -and
            (@($files | Where-Object { $_ -in $ksfEntries }).Count -gt 0)) {
            $required = @('surfd/surfd.py', 'surfd/ksfimport.py', 'surfd/ksfgrab.py') + $codecs
            if ($all -contains 'surfd/ksfprofile.py') { $required += 'surfd/ksfprofile.py' }
            foreach ($file in $required) {
                if ($all -notcontains $file) { throw "KSF runtime dependency '$file' is absent at $commit" }
                if ($files -notcontains $file) { $added += $file; $files += $file }
            }
        }
    } while ($files.Count -gt $before)
    $files = @($files | Sort-Object -Unique)
    if (-not $files.Count) { throw "nothing to deploy at $commit" }
    $extra = @($all | Where-Object {
        $_ -match '^(tools|src/shared)/.*\.py$' -or $_ -eq 'src/release/ftesurf.nginx'
    })
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
