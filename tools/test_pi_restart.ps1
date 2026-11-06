# Transport-mocked controls for the ACTUAL build.ps1 Pi blocks; no live SSH/sleep.
# Run: pwsh -NoProfile -File tools/test_pi_restart.ps1
$ErrorActionPreference = 'Stop'
$SurfDir = Split-Path $PSScriptRoot
$source = Join-Path $SurfDir 'src/build.ps1'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors -join "`n") }
$param = $ast.ParamBlock.Parameters | Where-Object { $_.Name.VariablePath.UserPath -eq 'PiWarnSeconds' }
if ($param.DefaultValue.Extent.Text -ne '10') { throw 'default countdown must be 10 seconds' }
$pi = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.IfStatementAst] -and
    $node.Clauses[0].Item1.Extent.Text -eq '$Pi'
}, $true)
$body = $pi.Clauses[0].Item2.Extent.Text
$body = $body.Substring(1, $body.Length - 2)
$start = $body.IndexOf('    Step "Pi: who is on"')
$upload = $body.IndexOf('    # 2. Upload beside the live files.')
if ($start -lt 0 -or $upload -le $start) { throw 'Pi source boundaries changed' }
$directory = [scriptblock]::Create($body.Substring($start, $upload - $start))
$delivery = [scriptblock]::Create($body.Substring($upload))
function Step($text) { }
function Ok($text) { }
function Invoke-RestMethod { param($Uri, $TimeoutSec, [switch]$UseBasicParsing)
    if ($script:Unknown) { throw 'directory unavailable control' }
    [pscustomobject]@{ lobbies = $script:Rows }
}
function Start-Sleep { param($Seconds) $script:Events.Add("wait:$Seconds") }
function PiHashes($result) {
    $hashes = @{}
    foreach ($line in $result.Out) {
        if ($line -match '^([0-9a-f]{64}) [ *](\S+)$') { $hashes[$Matches[2]] = $Matches[1] }
    }
    $hashes
}
function PiNative([string]$exe, [string[]]$argv) {
    $command = $argv -join ' '
    $code = 0; $out = @()
    if ($exe -eq 'scp') {
        if ($command -match 'lobby_announce.py') {
            $script:Events.Add('copy-warning')
            if ($script:Fault -eq 'copy') { $code = 1 }
        } else {
            $script:Events.Add('upload')
            if ($script:Fault -eq 'upload') { $code = 1 }
        }
    } elseif ($command -match 'python3 -I') {
        $script:Events.Add('warn')
        foreach ($l in $lobbies) {
            if ($command -notmatch "\b$($l.Port)\b") { throw 'warning omitted an active port' }
        }
        if ($command -notmatch 'restarts in 10 seconds') { throw 'wrong warning countdown' }
        if ($script:Fault -eq 'warn') { $code = 1 }
    } elseif ($command -match 'systemctl restart ftesurf@') {
        $script:Events.Add('restart')
    } elseif ($command -match 'cp -p qwprogs.dat') {
        $script:Events.Add('swap')
        $out = @("$hash  qwprogs.dat", "$hash  csprogs.dat")
    } elseif ($command -match 'sha256sum qwprogs.dat.new') {
        $script:Events.Add('hash-upload')
        $out = @("$hash  qwprogs.dat.new", "$hash  csprogs.dat.new")
    } else { throw "unexpected mocked transport: $exe $command" }
    [pscustomobject]@{ Code = $code; Out = $out }
}
$hash = 'a' * 64
$names = @('qwprogs.dat', 'csprogs.dat')
$local = @{ 'qwprogs.dat' = $hash; 'csprogs.dat' = $hash }
$lobbies = @([pscustomobject]@{ Unit = 1; Port = 27510 }, [pscustomobject]@{ Unit = 2; Port = 27520 })
$sshOpts = @(); $PiHost = 'mock'; $piAddr = 'mock'; $PiGame = '/mock/ftesurf'
$PiWarnSeconds = 10
$cases = @(
    @{ Name = 'occupied-default'; Players = 1 },
    @{ Name = 'empty-default'; Players = 0 },
    @{ Name = 'missing'; Missing = $true; Refuse = $true; Reason = 'directory has no row'; Events = '' },
    @{ Name = 'occupied-and-missing'; Players = 1; Missing = $true; Refuse = $true; Reason = 'directory has no row'; Events = '' },
    @{ Name = 'unknown'; Unknown = $true; Refuse = $true; Reason = 'cannot tell whether'; Events = '' },
    @{ Name = 'forced-unknown'; Unknown = $true; Force = $true },
    @{ Name = 'forced-missing'; Missing = $true; Force = $true },
    @{ Name = 'upload-failure'; Fault = 'upload'; Refuse = $true; Reason = 'scp qwprogs.dat failed'; Events = 'upload' },
    @{ Name = 'warning-copy-failure'; Fault = 'copy'; Refuse = $true; Reason = 'could not copy lobby_announce.py'; Events = 'upload,upload,hash-upload,copy-warning' },
    @{ Name = 'warning-send-failure'; Fault = 'warn'; Refuse = $true; Reason = 'warning transport failed'; Events = 'upload,upload,hash-upload,copy-warning,warn' }
)
foreach ($case in $cases) {
    $script:Events = [System.Collections.Generic.List[string]]::new()
    $script:Unknown = [bool]$case.Unknown; $script:Fault = $case.Fault; $PiForce = [bool]$case.Force
    $script:Rows = @([pscustomobject]@{ addr = 'mock:27510'; players = [int]$case.Players; name = 'mock'; map = 'test'; max = 16 })
    if (-not $case.Missing) { $script:Rows += [pscustomobject]@{ addr = 'mock:27520'; players = 0 } }
    $refused = $false; $reason = ''
    try { . $directory; . $delivery } catch { $refused = $true; $reason = $_.Exception.Message }
    if ($refused -ne [bool]$case.Refuse) { throw "wrong refusal: $($case.Name): $reason" }
    if ($case.Refuse) {
        if ($reason -notlike "*$($case.Reason)*" -or ($script:Events -join ',') -ne $case.Events) {
            throw "wrong refusal boundary: $($case.Name): $reason / $script:Events"
        }
        if ($script:Events.Contains('swap') -or $script:Events.Contains('restart')) { throw "mutated on refusal: $($case.Name)" }
    } else {
        $expected = 'upload,upload,hash-upload,copy-warning,warn,wait:10,swap,restart,restart'
        if (($script:Events -join ',') -ne $expected) { throw "wrong sequence: $($case.Name): $script:Events" }
    }
    Write-Host "PASS $($case.Name)"
}
Write-Host '10 actual-source Pi restart controls passed; transports mocked, not live acceptance.'
