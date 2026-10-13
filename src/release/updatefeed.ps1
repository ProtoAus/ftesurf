# Signed updates are a separate publication contract from archive receipts.
# Caller supplies stages only AFTER archive/stage verification; no player-install input.
function New-UpdateFeed {
    param([string]$Tool, [string]$WindowsStage, [string]$LinuxStage,
        [string]$Output, [string]$Version, [string]$Mirror, [string]$SeedFile,
        [switch]$First, [string]$Previous, [string]$PreviousObjects)
    if ($First.IsPresent -eq [bool]$Previous) { Fail 'choose -FirstUpdateFeed OR -PreviousUpdateFeed explicitly' }
    if ($First -and -not $LinuxStage) { Fail 'first update feed requires verified Windows AND Linux stages' }
    if (-not (Test-Path -LiteralPath $Tool -PathType Leaf)) { Fail 'missing update publisher' }
    $argv = @($Tool, '--windows', $WindowsStage, '--output', $Output, '--version', $Version,
        '--mirror', $Mirror, '--seed-file', $SeedFile)
    if ($LinuxStage) { $argv += @('--linux', $LinuxStage) }
    $priorSha = 'none'
    if ($First) { $argv += '--first-release' }
    else {
        $priorSha = (Get-FileHash -LiteralPath $Previous -Algorithm SHA256).Hash.ToLower()
        $argv += @('--previous', $Previous)
        if ($PreviousObjects) { $argv += @('--previous-objects', $PreviousObjects) }
    }
    Native 'python' $argv 'signed update generation' | ForEach-Object { Info $_ }
    foreach ($file in @('update.json', 'objects.txt')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Output $file) -PathType Leaf)) { Fail "publisher did not produce $file" }
    }
    # Freeze exact generated feed; every later reader must still observe these bytes.
    return [pscustomobject]@{ Root = $Output; Tool = $Tool; PreviousSha = $priorSha;
        FeedSha = (Get-FileHash -LiteralPath (Join-Path $Output 'update.json') -Algorithm SHA256).Hash.ToLower() }
}

function Publish-UpdateObjects {
    param($Feed, [string]$Destination, [string]$Limit, [switch]$SkipPut)
    $feedPath = Join-Path $Feed.Root 'update.json'
    if ((Get-FileHash -LiteralPath $feedPath -Algorithm SHA256).Hash.ToLower() -cne $Feed.FeedSha) {
        Fail 'generated update feed changed before object publication'
    }
    $list = Join-Path $Feed.Root 'objects.txt'
    # Regenerate/validate inventory from the signed feed rather than trusting a mutable list.
    Native 'python' @($Feed.Tool, 'verify-objects', '--feed', $feedPath,
        '--objects', (Join-Path $Feed.Root 'objects'), '--receipt', (Join-Path $Feed.Root 'local-check.json'), '--inventory', $list) 'local update object check' | ForEach-Object { Info $_ }
    # --immutable + --checksum refuses an existing same-name/different-byte object.
    if (-not $SkipPut) {
        Native 'rclone' @('copy', (Join-Path $Feed.Root 'objects'), $Destination,
            '--files-from-raw', $list, '--immutable', '--checksum', '--bind', '0.0.0.0',
            '--s3-upload-cutoff', '200M', '--bwlimit', $Limit,
            '--header-upload', 'Cache-Control: public, max-age=31536000, immutable',
            '--header-upload', 'Content-Type: application/octet-stream') 'immutable update object upload' | Out-Null
    }
    $checkRoot = Join-Path $Feed.Root ('.verify-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $checkRoot | Out-Null
    $objects = Join-Path $checkRoot 'objects'
    New-Item -ItemType Directory -Path $objects | Out-Null
    Native 'rclone' @('copy', $Destination, $objects, '--files-from-raw', $list,
        '--checksum', '--bind', '0.0.0.0', '--bwlimit', $Limit) 'update object round-trip download' | Out-Null
    $proof = Join-Path $checkRoot 'publication.json'
    Native 'python' @($Feed.Tool, 'verify-objects', '--feed', $feedPath, '--objects', $objects,
        '--receipt', $proof, '--roundtrip') 'full referenced update object verification' | ForEach-Object { Info $_ }
    if ((Get-FileHash -LiteralPath $feedPath -Algorithm SHA256).Hash.ToLower() -cne $Feed.FeedSha) {
        Fail 'generated update feed changed during object verification'
    }
    # Retain failed round-trip evidence; retire only successful verified disposable downloads.
    $saved = Join-Path $Feed.Root ('publication-' + [guid]::NewGuid().ToString('N') + '.json')
    Copy-Item -LiteralPath $proof -Destination $saved
    Remove-Item -LiteralPath $checkRoot -Recurse -Force
    return $saved
}
