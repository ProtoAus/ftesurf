# Prepared releases are data, never commands. One sealed receipt binds the exact
# publication inputs; volatile remote proofs/downloads stay outside these trees.
$ReleaseStateKeys = @('Ver', 'ArchiveName', 'ArchivePath', 'ObjectKey', 'ArchiveUrl', 'ArchiveBytes', 'ArchiveSha', 'ArchiveMd5',
    'Linux', 'LinuxArchiveName', 'LinuxArchivePath', 'LinuxObjectKey', 'LinuxArchiveUrl', 'LinuxArchiveBytes', 'LinuxArchiveSha', 'LinuxArchiveMd5',
    'qcBuild', 'enginePatch', 'engineLabel', 'GitHead', 'GitShort', 'lxGlibc', 'lxLabel', 'ReceiptPath', 'pageDir', 'pageSha',
    'updateFeed', 'launcherArtifacts', 'publisherDir', 'Remote', 'Bucket', 'Prefix', 'DlBase', 'PiHost', 'SiteRoot', 'SiteUrl')
$ReleasePathKeys = @('ArchivePath', 'ReceiptPath', 'pageDir', 'publisherDir')
$ReleaseReaderFiles = @('release.ps1', 'releaselib.ps1', 'prepared.ps1', 'updatefeed.ps1', 'bootstrap.ps1',
    'publish.sh', 'install.sh', 'ftesurf.nginx', '../../tools/updatefeed.py', '../../tools/ed25519.py')

function Get-ReleaseSourceState ([string]$Root, [switch]$IgnoreVersion) {
    $head = & git -C $Root rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw "not an inspected source checkout: $Root" }
    $paths = @('.')
    if ($IgnoreVersion) { $paths += ':(exclude)VERSION' }
    $dirty = @(& git -C $Root status --porcelain --untracked-files=all -- @paths)
    if ($LASTEXITCODE -ne 0) { throw 'cannot inspect source status' }
    $diff = @(& git -C $Root diff --binary HEAD -- @paths)
    if ($LASTEXITCODE -ne 0) { throw 'cannot inspect source changes' }
    $text = (($dirty + $diff) -join "`n")
    $hash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($text))).ToLowerInvariant()
    $describeArgs = @('describe', '--long', '--always')
    if (-not $IgnoreVersion) { $describeArgs += '--dirty' }
    $description = & git -C $Root @describeArgs
    if ($LASTEXITCODE -ne 0) { throw 'cannot inspect source revision description' }
    [pscustomobject]@{ Head = "$head".Trim(); Dirty = [bool]$dirty.Count; ChangesSha256 = $hash; Description = "$description".Trim() }
}

function Assert-ReleaseNoLink ([string]$Path) {
    for ($item = Get-Item -LiteralPath $Path -Force; $null -ne $item; $item = $item.Parent) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "linked release input: $Path" }
        # FileInfo has Directory, not Parent. Check the complete ancestor chain.
        if ($item -isnot [IO.DirectoryInfo]) { $item = $item.Directory; if ($null -eq $item) { break } }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "linked release ancestor: $Path" }
    }
}

function Resolve-ReleaseInput ([string]$Root, [string]$Relative) {
    if (-not $Relative -or $Relative.Contains('\') -or [IO.Path]::IsPathRooted($Relative)) { throw 'candidate path must be relative, slash-separated' }
    foreach ($segment in $Relative.Split('/')) {
        if ($segment -notmatch '^[A-Za-z0-9_.-]+$' -or $segment -in @('.', '..') -or $segment.EndsWith('.')) { throw "unsafe candidate path: $Relative" }
        if ($segment.Split('.')[0] -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$') { throw "reserved candidate path: $Relative" }
    }
    $path = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    Assert-ReleaseNoLink $path
    return $path
}

function Get-ReleaseInputFiles ([string]$Root) {
    Assert-ReleaseNoLink $Root
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($Root)
    while ($pending.Count) {
        $dir = $pending.Pop()
        foreach ($item in Get-ChildItem -LiteralPath $dir -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "linked release entry: $($item.FullName)" }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
            else { $item.FullName }
        }
    }
}

function Get-ReleaseReaderHashes ([string]$Directory) {
    $hashes = [ordered]@{}
    foreach ($name in $ReleaseReaderFiles) {
        $p = Join-Path $Directory $name
        Assert-ReleaseNoLink $p
        $hashes[$name] = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $hashes
}

function ConvertTo-ReleaseRelative ([string]$Root, [string]$Path) {
    $rel = [IO.Path]::GetRelativePath($Root, [IO.Path]::GetFullPath($Path)).Replace('\', '/')
    [void](Resolve-ReleaseInput $Root $rel)
    return $rel
}

function Test-ReleaseState ($State) {
    if (@(Compare-TokenSets @($State.Keys) $ReleaseStateKeys).Count) { throw 'unknown/missing prepared publication state' }
    if ($State.Ver -notmatch '^\d+\.\d+\.\d+$' -or $State.GitHead -notmatch '^[0-9a-f]{40}$') { throw 'invalid prepared version/source' }
    foreach ($k in @('Remote', 'Bucket')) {
        if ($State[$k] -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]*$') { throw "unsafe prepared $k" }
    }
    if ($State.Prefix -notmatch '^[A-Za-z0-9][A-Za-z0-9_./-]*$' -or $State.Prefix.Split('/') -contains '..') { throw 'unsafe prepared prefix' }
    if ($State.PiHost -notmatch '^([A-Za-z0-9_][A-Za-z0-9._-]*@)?[A-Za-z0-9_][A-Za-z0-9.-]*$') { throw 'unsafe prepared SSH host' }
    if ($State.SiteRoot -notmatch '^/[A-Za-z0-9._/-]+$' -or $State.SiteRoot.Split('/') -contains '..') { throw 'unsafe prepared site root' }
    foreach ($k in @('DlBase', 'SiteUrl')) {
        $uri = [uri]$State[$k]
        if (-not $uri.IsAbsoluteUri -or $uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) { throw "unsafe prepared $k URL" }
    }
    foreach ($part in @(@('ArchiveName', 'ObjectKey', 'ArchiveUrl', "ftesurf-$($State.Ver).7z"),
                        @('LinuxArchiveName', 'LinuxObjectKey', 'LinuxArchiveUrl', "ftesurf-$($State.Ver)-linux-x86_64.tar.xz"))) {
        if ($part[0] -like 'Linux*' -and -not $State.Linux) { continue }
        if ($State[$part[0]] -cne $part[3] -or $State[$part[1]] -cne "$($State.Prefix)/$($part[3])" -or
            $State[$part[2]] -cne "$($State.DlBase)/$($State[$part[1]])") { throw 'prepared archive identity disagrees with destination' }
    }
    if (@(Compare-TokenSets @($State.updateFeed.Keys) @('Root', 'Tool', 'PreviousSha', 'FeedSha')).Count) { throw 'invalid prepared feed state' }
    if ($State.updateFeed.FeedSha -notmatch '^[0-9a-f]{64}$' -or $State.updateFeed.PreviousSha -notmatch '^(none|[0-9a-f]{64})$') { throw 'invalid prepared feed hashes' }
}

function New-ReleaseCandidate {
    param([string]$Root, [string]$Path, $State, [string[]]$Files, [string[]]$Trees, [string]$ReaderDirectory)
    $Root = [IO.Path]::GetFullPath($Root)
    Assert-ReleaseNoLink $Root
    if (Test-Path -LiteralPath $Path) { throw 'candidate already exists; promote it instead of rebuilding' }
    Test-ReleaseState $State
    foreach ($key in $ReleasePathKeys) { $State[$key] = ConvertTo-ReleaseRelative $Root $State[$key] }
    if ($State.Linux) { $State.LinuxArchivePath = ConvertTo-ReleaseRelative $Root $State.LinuxArchivePath }
    foreach ($key in @('Root', 'Tool')) { $State.updateFeed[$key] = ConvertTo-ReleaseRelative $Root $State.updateFeed[$key] }
    foreach ($artifact in $State.launcherArtifacts) { $artifact.Path = ConvertTo-ReleaseRelative $Root $artifact.Path }
    $all = @($Files)
    foreach ($tree in $Trees) { $all += @(Get-ReleaseInputFiles $tree) }
    $index = @()
    foreach ($file in @($all | Sort-Object -Unique)) {
        $rel = ConvertTo-ReleaseRelative $Root $file
        $item = Get-Item -LiteralPath $file
        if ($item.PSIsContainer) { throw 'candidate file index contains a directory' }
        $index += [ordered]@{ path = $rel; bytes = $item.Length; sha256 = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
    $treeNames = @($Trees | ForEach-Object { ConvertTo-ReleaseRelative $Root $_ })
    $document = [ordered]@{ schema = 1; state = $State; trees = $treeNames; files = $index; readers = (Get-ReleaseReaderHashes $ReaderDirectory) }
    [IO.File]::WriteAllText($Path, (($document | ConvertTo-Json -Depth 16).Replace("`r`n", "`n") + "`n"), [Text.UTF8Encoding]::new($false))
    [pscustomobject]@{ Path = [IO.Path]::GetFullPath($Path); Sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant(); Version = $State.Ver }
}

function Read-ReleaseCandidate {
    param([string]$Path, [string]$ExpectedSha256, [string]$ReaderDirectory)
    if ($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$') { throw 'pass the trusted -PreparedSha256 printed by preparation' }
    Assert-ReleaseNoLink $Path
    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer -or $item.Length -gt 16MB) { throw 'invalid candidate receipt size/type' }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ine $ExpectedSha256) { throw 'prepared receipt SHA256 mismatch' }
    $doc = [IO.File]::ReadAllText($Path) | ConvertFrom-Json -AsHashtable
    if (@(Compare-TokenSets @($doc.Keys) @('schema', 'state', 'trees', 'files', 'readers')).Count -or $doc.schema -ne 1) { throw 'unsupported prepared receipt schema' }
    if ($doc.files.Count -eq 0 -or $doc.files.Count -gt 50000) { throw 'invalid prepared file count' }
    $readers = Get-ReleaseReaderHashes $ReaderDirectory
    if (@(Compare-TokenSets @($doc.readers.Keys) @($readers.Keys)).Count) { throw 'prepared publisher reader set changed' }
    foreach ($key in $readers.Keys) { if ($readers[$key] -cne $doc.readers[$key]) { throw "prepared publisher changed: $key; use the original inspected tooling" } }
    Test-ReleaseState $doc.state
    $root = Split-Path ([IO.Path]::GetFullPath($Path)) -Parent
    $index = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($row in $doc.files) {
        if (@(Compare-TokenSets @($row.Keys) @('path', 'bytes', 'sha256')).Count -or $row.sha256 -notmatch '^[0-9a-f]{64}$') { throw 'invalid prepared file record' }
        if ($index.ContainsKey($row.path)) { throw 'duplicate/aliased prepared path' }
        $p = Resolve-ReleaseInput $root $row.path
        $f = Get-Item -LiteralPath $p
        if ($f.PSIsContainer -or $f.Length -ne $row.bytes -or (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ine $row.sha256) { throw "prepared artifact changed: $($row.path)" }
        $index.Add($row.path, $row)
    }
    foreach ($tree in $doc.trees) {
        $dir = Resolve-ReleaseInput $root $tree
        foreach ($p in @(Get-ReleaseInputFiles $dir)) {
            $rel = ConvertTo-ReleaseRelative $root $p
            if (-not $index.ContainsKey($rel)) { throw "unexpected prepared tree entry: $rel" }
        }
    }
    $s = $doc.state
    foreach ($tree in @($s.pageDir, $s.publisherDir, ($s.updateFeed.Root + '/objects'))) {
        if ($doc.trees -cnotcontains $tree) { throw 'prepared publication tree is not sealed' }
    }
    foreach ($key in $ReleasePathKeys) {
        if ($key -in @('ArchivePath', 'ReceiptPath') -and -not $index.ContainsKey($s[$key])) { throw 'prepared required file is not sealed' }
        $s[$key] = Resolve-ReleaseInput $root $s[$key]
    }
    if ($s.Linux) {
        if (-not $index.ContainsKey($s.LinuxArchivePath)) { throw 'prepared Linux archive is not sealed' }
        $s.LinuxArchivePath = Resolve-ReleaseInput $root $s.LinuxArchivePath
    }
    foreach ($key in @('Root', 'Tool')) { $s.updateFeed[$key] = Resolve-ReleaseInput $root $s.updateFeed[$key] }
    if (@(Get-ReleaseInputFiles $s.publisherDir).Count -ne 5) { throw 'unexpected frozen publisher input (including bytecode caches)' }
    if ($s.updateFeed.Tool -cne (Join-Path $s.publisherDir 'updatefeed.py')) { throw 'prepared verifier must be the frozen publisher' }
    foreach ($pair in @(@('publish.sh', 'publish.sh'), @('install.sh', 'install.sh'), @('ftesurf.nginx', 'ftesurf.nginx'),
                        @('updatefeed.py', '../../tools/updatefeed.py'), @('ed25519.py', '../../tools/ed25519.py'))) {
        $rel = ConvertTo-ReleaseRelative $root (Join-Path $s.publisherDir $pair[0])
        if (-not $index.ContainsKey($rel) -or $index[$rel].sha256 -cne $readers[$pair[1]]) { throw "frozen publisher bytes differ from trusted tooling: $($pair[0])" }
    }
    $feedRel = ConvertTo-ReleaseRelative $root (Join-Path $s.updateFeed.Root 'update.json')
    if (-not $index.ContainsKey($feedRel) -or $index[$feedRel].sha256 -cne $s.updateFeed.FeedSha) { throw 'prepared feed SHA disagrees with sealed files' }
    foreach ($artifact in $s.launcherArtifacts) {
        if (@(Compare-TokenSets @($artifact.Keys) @('Platform', 'Name', 'Path', 'Key', 'Url', 'Sha', 'Md5')).Count) { throw 'invalid prepared launcher state' }
        if (-not $index.ContainsKey($artifact.Path) -or $index[$artifact.Path].sha256 -ine $artifact.Sha -or
            $artifact.Key -cne "$($s.Prefix)/$($artifact.Name)" -or $artifact.Url -cne "$($s.DlBase)/$($artifact.Key)") { throw 'prepared launcher identity mismatch' }
        $artifact.Path = Resolve-ReleaseInput $root $artifact.Path
    }
    $receipt = [IO.File]::ReadAllText($s.ReceiptPath) | ConvertFrom-Json -AsHashtable
    if ($receipt.version -cne $s.Ver -or $receipt.qc.head -cne $s.GitHead -or $receipt.archive.sha256 -ine $s.ArchiveSha -or
        $receipt.archive.md5 -ine $s.ArchiveMd5 -or $receipt.archive.bytes -ne $s.ArchiveBytes -or $receipt.overrides.Count) { throw 'prepared receipt/provenance disagrees or contains overrides' }
    $archiveRel = ConvertTo-ReleaseRelative $root $s.ArchivePath
    $pageRel = ConvertTo-ReleaseRelative $root (Join-Path $s.pageDir 'index.html')
    if ($index[$archiveRel].sha256 -ine $s.ArchiveSha -or -not $index.ContainsKey($pageRel) -or $index[$pageRel].sha256 -ine $s.pageSha) { throw 'prepared archive/page hash disagrees with receipt' }
    if ($s.Linux -and ($receipt.linux.archive.sha256 -ine $s.LinuxArchiveSha -or $receipt.linux.archive.md5 -ine $s.LinuxArchiveMd5 -or $receipt.linux.archive.bytes -ne $s.LinuxArchiveBytes)) { throw 'prepared Linux receipt disagrees' }
    [pscustomobject]@{ Root = $root; State = $s; Sha256 = $ExpectedSha256.ToLowerInvariant(); Receipt = $receipt }
}
