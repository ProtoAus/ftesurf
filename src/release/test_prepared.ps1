# Fast, secretless graph/reader/refusal controls. Fake archive bytes are NOT
# archive/build acceptance; a real full prepare + entrypoint validation is separate.
param([Parameter(Mandatory)][string]$WorkRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'releaselib.ps1')
. (Join-Path $PSScriptRoot 'prepared.ps1')
if (Test-Path -LiteralPath $WorkRoot) { throw 'fresh owned test root required' }
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
[IO.File]::WriteAllText((Join-Path $WorkRoot 'OWNER.md'), 'Owned prepared-release controls. Synthetic data; no game/network/signing key.')
$script:results = @()
function Put ([string]$Path, [string]$Text) {
    [IO.Directory]::CreateDirectory((Split-Path $Path -Parent)) | Out-Null
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}
function Fixture ([string]$Name) {
    $r = Join-Path $WorkRoot $Name
    [IO.Directory]::CreateDirectory($r) | Out-Null
    $archive = Join-Path $r 'ftesurf-1.2.3.7z'; Put $archive 'synthetic archive bytes'
    $launcher = Join-Path $r 'ftesurf-launcher-1.2.3.exe'; Put $launcher 'synthetic launcher bytes'
    $page = Join-Path $r 'site'; Put (Join-Path $page 'index.html') 'synthetic page'
    $feed = Join-Path $r 'feed'; Put (Join-Path $feed 'update.json') '{}'; Put (Join-Path $feed 'objects.txt') ''
    Put (Join-Path $feed 'objects/00/fixture') 'synthetic object'
    $publisher = Join-Path $r 'publisher'; [IO.Directory]::CreateDirectory($publisher) | Out-Null
    foreach ($file in @('publish.sh', 'install.sh', 'ftesurf.nginx')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $publisher }
    foreach ($file in @('updatefeed.py', 'ed25519.py')) { Copy-Item -LiteralPath (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "tools/$file") -Destination $publisher }
    $sha = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $md5 = (Get-FileHash $archive -Algorithm MD5).Hash.ToLowerInvariant()
    $head = 'a' * 40
    $receipt = Join-Path $r 'ftesurf-1.2.3.json'
    $meta = [ordered]@{ version = '1.2.3'; qc = @{ head = $head }; archive = @{ sha256 = $sha; md5 = $md5; bytes = (Get-Item $archive).Length }; overrides = @() }
    Put $receipt ($meta | ConvertTo-Json -Depth 8)
    $state = [ordered]@{}
    foreach ($key in $ReleaseStateKeys) { $state[$key] = $null }
    $state.Ver = '1.2.3'; $state.ArchiveName = 'ftesurf-1.2.3.7z'; $state.ArchivePath = $archive
    $state.Remote = 'fixture'; $state.Bucket = 'fixture-bucket'; $state.Prefix = 'ftesurf'; $state.DlBase = 'https://invalid.example'
    $state.ObjectKey = 'ftesurf/ftesurf-1.2.3.7z'; $state.ArchiveUrl = 'https://invalid.example/ftesurf/ftesurf-1.2.3.7z'
    $state.ArchiveSha = $sha; $state.ArchiveMd5 = $md5; $state.ArchiveBytes = (Get-Item $archive).Length
    $state.Linux = $false; $state.GitHead = $head; $state.GitShort = $head.Substring(0, 8)
    $state.ReceiptPath = $receipt; $state.pageDir = $page; $state.pageSha = (Get-FileHash (Join-Path $page 'index.html') -Algorithm SHA256).Hash.ToLowerInvariant()
    $state.publisherDir = $publisher; $state.PiHost = 'fixture@example.invalid'; $state.SiteRoot = '/srv/fixture'; $state.SiteUrl = 'https://invalid.example/ftesurf'
    $state.updateFeed = [ordered]@{ Root = $feed; Tool = (Join-Path $publisher 'updatefeed.py'); PreviousSha = 'none'; FeedSha = (Get-FileHash (Join-Path $feed 'update.json') -Algorithm SHA256).Hash.ToLowerInvariant() }
    $state.launcherArtifacts = @([ordered]@{ Platform = 'win64'; Name = 'ftesurf-launcher-1.2.3.exe'; Path = $launcher; Key = 'ftesurf/ftesurf-launcher-1.2.3.exe'; Url = 'https://invalid.example/ftesurf/ftesurf-launcher-1.2.3.exe'; Sha = (Get-FileHash $launcher -Algorithm SHA256).Hash.ToLowerInvariant(); Md5 = (Get-FileHash $launcher -Algorithm MD5).Hash.ToLowerInvariant() })
    $candidate = New-ReleaseCandidate -Root $r -Path (Join-Path $r 'candidate.json') -State $state -Files @($archive, $launcher, $receipt, (Join-Path $feed 'update.json'), (Join-Path $feed 'objects.txt')) -Trees @($page, $publisher, (Join-Path $feed 'objects')) -ReaderDirectory $PSScriptRoot
    return [pscustomobject]@{ Root = $r; Candidate = $candidate; Archive = $archive; Page = $page; Feed = $feed }
}
function Load ($f) { Read-ReleaseCandidate -Path $f.Candidate.Path -ExpectedSha256 $f.Candidate.Sha256 -ReaderDirectory $PSScriptRoot }
function Reseal ($f, [scriptblock]$Change) {
    $d = Get-Content -LiteralPath $f.Candidate.Path -Raw | ConvertFrom-Json -AsHashtable
    & $Change $d
    Put $f.Candidate.Path ($d | ConvertTo-Json -Depth 16)
    $f.Candidate.Sha256 = (Get-FileHash $f.Candidate.Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Reject ([string]$Name, [scriptblock]$Action, [string]$Pattern) {
    try { & $Action | Out-Null; throw 'DID NOT REJECT' }
    catch { if ($_.Exception.Message -notmatch $Pattern) { throw }; $script:results += @{ case = $Name; passed = $true; refusal = $_.Exception.Message }; Write-Host "PASS $Name" }
}
$f = Fixture 'positive'
$loaded = Load $f
if ($loaded.State.Ver -cne '1.2.3' -or $loaded.State.Linux) { throw 'valid candidate state lost' }
$results += @{ case = 'positive'; passed = $true }
Write-Host 'PASS exact candidate graph'
Reject 'candidate seal mandatory' { Read-ReleaseCandidate -Path $f.Candidate.Path -ExpectedSha256 '' -ReaderDirectory $PSScriptRoot } 'trusted -PreparedSha256'
Reject 'candidate cannot be overwritten' { New-ReleaseCandidate -Root $f.Root -Path $f.Candidate.Path -State @{} -Files @() -Trees @() -ReaderDirectory $PSScriptRoot } 'already exists'
$f = Fixture 'archive-mutation'; Put $f.Archive 'synthetic ARCHIVE bytes'
Reject 'same-size archive mutation' { Load $f } 'artifact changed'
$f = Fixture 'manifest-mutation'; Add-Content -LiteralPath $f.Candidate.Path -Value ' '
Reject 'receipt mutation' { Load $f } 'receipt SHA256 mismatch'
$f = Fixture 'missing-file'; Remove-Item -LiteralPath $f.Archive
Reject 'missing artifact' { Load $f } 'cannot find|does not exist'
$f = Fixture 'extra-site-file'; Put (Join-Path $f.Page 'unexpected.txt') 'must not leak'
Reject 'unexpected site file' { Load $f } 'unexpected prepared tree entry'
$f = Fixture 'extra-object-file'; Put (Join-Path $f.Feed 'objects/extra.txt') 'must not upload'
Reject 'unexpected object' { Load $f } 'unexpected prepared tree entry'
$f = Fixture 'unknown-state'; Reseal $f { param($d) $d.state['ErrorActionPreference'] = 'Continue' }
Reject 'JSON cannot set arbitrary caller variables' { Load $f } 'publication state'
$f = Fixture 'unsafe-path'; Reseal $f { param($d) $d.files[0].path = '../outside' }
Reject 'path traversal' { Load $f } 'unsafe candidate path'
$f = Fixture 'aliased-path'; Reseal $f { param($d) $d.files += $d.files[0] }
Reject 'duplicate path alias' { Load $f } 'duplicate/aliased'
$f = Fixture 'unsafe-destination'; Reseal $f { param($d) $d.state.SiteRoot = '/srv/../fixture' }
Reject 'unsafe remote path' { Load $f } 'unsafe prepared site root'
$f = Fixture 'reader-change'; Reseal $f { param($d) $d.readers['updatefeed.ps1'] = ('0' * 64) }
Reject 'changed publisher reader' { Load $f } 'publisher changed'
$f = Fixture 'rogue-publisher'
Put (Join-Path $f.Root 'publisher/updatefeed.py') 'not trusted executable code'
Reseal $f {
    param($d)
    $file = Join-Path $f.Root 'publisher/updatefeed.py'
    foreach ($row in $d.files) {
        if ($row.path -ceq 'publisher/updatefeed.py') { $row.bytes = (Get-Item $file).Length; $row.sha256 = (Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
}
Reject 'resealed publisher code cannot bypass trusted verifier' { Load $f } 'frozen publisher bytes differ'
$f = Fixture 'tree-coverage'; Reseal $f { param($d) $d.trees = @($d.trees | Where-Object { $_ -ne 'site' }) }
Reject 'publication tree must be sealed' { Load $f } 'tree is not sealed'
$f = Fixture 'archive-state'; Reseal $f { param($d) $d.state.ArchiveSha = ('0' * 64) }
Reject 'state cannot relabel archive bytes' { Load $f } 'receipt/provenance'
$f = Fixture 'link-ancestor'
$alias = Join-Path $WorkRoot 'owned-link'
New-Item -ItemType Junction -Path $alias -Target $f.Root | Out-Null
try {
    Reject 'linked candidate ancestor' { Read-ReleaseCandidate -Path (Join-Path $alias 'candidate.json') -ExpectedSha256 $f.Candidate.Sha256 -ReaderDirectory $PSScriptRoot } 'linked release'
} finally { [IO.Directory]::Delete($alias); if (-not (Test-Path $f.Archive)) { throw 'junction target was damaged' } }
$f = Fixture 'courier-source'
$courier = Join-Path $WorkRoot 'courier-no-sources'; Copy-Item -LiteralPath $f.Root -Destination $courier -Recurse
$handoff = Read-ReleaseCandidate -Path (Join-Path $courier 'candidate.json') -ExpectedSha256 $f.Candidate.Sha256 -ReaderDirectory $PSScriptRoot
if (-not $handoff.State.ArchivePath.StartsWith($courier)) { throw 'candidate did not relocate by relative paths' }
$results += @{ case = 'courier without source/build trees'; passed = $true }
Write-Host 'PASS courier without source/build trees'
# A structurally valid receipt cannot bypass the pinned cryptographic verifier.
$log = @(& pwsh -NoProfile -File (Join-Path $PSScriptRoot 'release.ps1') -PublishPrepared $f.Candidate.Path -PreparedSha256 $f.Candidate.Sha256 -DryRun -Offline 2>&1)
$rc = $LASTEXITCODE
Put (Join-Path $WorkRoot 'crypto-refusal.log') ($log -join "`n")
if ($rc -eq 0 -or ($log -join "`n") -notmatch 'prepared signed feed/object validation') { throw 'entrypoint did not act on invalid signed feed' }
$results += @{ case = 'entrypoint refuses unsigned fixture before any transport'; passed = $true }
Load $f | Out-Null
$results += @{ case = 'entrypoint validation leaves frozen trees unchanged (no bytecode cache)'; passed = $true }
$results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $WorkRoot 'results.json')
Write-Host "$($results.Count) prepared-candidate controls passed; no network/build/signing key used"
