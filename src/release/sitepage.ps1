<#
  sitepage.ps1 -- re-render the site for a release that is already out, and
  publish it.  For changes to page.template.html or src/release/site; anything
  that changes the archive is release.ps1's.

      pwsh -NoProfile -File src\release\sitepage.ps1 [-Version 0.1.22] [-DryRun]

  Every value on the page comes from that release's receipt
  (dist\ftesurf-<v>.json) through releaselib's Get-ReceiptTokens, so the page
  states what release.ps1 rendered for the same archive.  version.json is the
  one release.ps1 wrote (host withheld) and is kept byte for byte.  After
  publish.sh swaps the page in, every file is fetched back from the live site
  and compared by sha256.
#>
param(
    [string]$Version,
    [switch]$DryRun,
    [string]$OutDir,
    [string]$PiHost   = $(if ($env:FTESURF_PIHOST) { $env:FTESURF_PIHOST } else { 'proto@192.168.1.102' }),
    [string]$SiteRoot = '/srv/nvme/ftesurf-site',
    [string]$SiteUrl  = 'https://proto.bar/ftesurf'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RelDir  = $PSScriptRoot
$SurfDir = Split-Path -Parent (Split-Path -Parent $RelDir)
if (-not $OutDir) { $OutDir = Join-Path $SurfDir 'dist' }
. (Join-Path $RelDir 'releaselib.ps1')

function Fail ([string]$m) { Write-Host "FAIL  $m" -ForegroundColor Red; exit 1 }
function HtmlEsc ([string]$s) {
    $s.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;').Replace('"', '&quot;').Replace("'", '&#39;')
}

if (-not $Version) { $Version = (Get-Content -Raw -LiteralPath (Join-Path $OutDir 'ftesurf-latest.json') | ConvertFrom-Json).version }
if ($Version -notmatch '^\d+\.\d+\.\d+$') { Fail "not a version: '$Version'" }
$rcPath = Join-Path $OutDir "ftesurf-$Version.json"
if (-not (Test-Path -LiteralPath $rcPath)) { Fail "no receipt at $rcPath" }
$tok = Get-ReceiptTokens (Get-Content -Raw -LiteralPath $rcPath | ConvertFrom-Json)

# --- render, with release.ps1's asserts ---------------------------------------
try { $pb = Split-PageBlocks (Get-Content -LiteralPath (Join-Path $RelDir 'page.template.html') -Raw) } catch { Fail $_.Exception.Message }
$html = if ($tok.Linux) { $pb.Kept } else { $pb.Outside }
foreach ($k in $tok.Windows.Keys) { $html = $html.Replace("@@$k@@", (HtmlEsc $tok.Windows[$k])) }
if ($tok.Linux) { foreach ($k in $tok.Linux.Keys) { $html = $html.Replace("@@$k@@", (HtmlEsc $tok.Linux[$k])) } }
if ($html -match '@@([A-Z0-9_]+)@@') { Fail "template token $($Matches[0]) was not substituted" }
$d = @(Compare-TokenSets (Get-TemplateTokens $pb.Outside) @($tok.Windows.Keys))
if ($d.Count) { Fail ("template tokens and the receipt's disagree: " + ($d -join '; ')) }
$lxNames = @('LINUX_URL', 'LINUX_FILENAME', 'LINUX_SIZE_HUMAN', 'LINUX_SIZE_BYTES', 'LINUX_SHA256', 'LINUX_GLIBC', 'LINUX_ENGINE')
$d = @(Compare-TokenSets (Get-TemplateTokens $pb.Inside) $lxNames)
if ($d.Count) { Fail ("the LINUX blocks' tokens disagree: " + ($d -join '; ')) }

$pageDir = Join-Path $OutDir "site-$Version"
$vj = Join-Path $pageDir 'version.json'
if (-not (Test-Path -LiteralPath $vj)) { Fail "no $vj -- release.ps1 writes it, and it is not rebuilt here" }
$vjBytes = [System.IO.File]::ReadAllBytes($vj)
Remove-Item -LiteralPath $pageDir -Recurse -Force
New-Item -ItemType Directory -Path $pageDir -Force | Out-Null
[System.IO.File]::WriteAllBytes($vj, $vjBytes)
[System.IO.File]::WriteAllText((Join-Path $pageDir 'index.html'), $html.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding $false))
Copy-Item -LiteralPath (Join-Path $SurfDir 'ftesurf\gfx\fonts\BebasNeueRegular.ttf') -Destination $pageDir
Copy-Item -LiteralPath (Join-Path $SurfDir 'ftesurf\gfx\fonts\OFL.txt') -Destination $pageDir
Copy-Item -LiteralPath (Join-Path $SurfDir 'LICENSE') -Destination (Join-Path $pageDir 'LICENSE.txt')
try { $siteFiles = @(Copy-SiteFiles (Join-Path $RelDir 'site') $pageDir) } catch { Fail $_.Exception.Message }
$files = @(Get-ChildItem -LiteralPath $pageDir -File | Sort-Object Name)
Write-Host "rendered $pageDir -- $($files.Count) files ($($siteFiles -join ', '))"
foreach ($k in $tok.Windows.Keys) { Write-Host ("  {0,-12} {1}" -f $k, $tok.Windows[$k]) }
if ($DryRun) { Write-Host 'dry run: nothing published'; exit 0 }

# --- publish (release.ps1's path: scp each file, then publish.sh) --------------
$sshOpts = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10')
& ssh @sshOpts $PiHost "mkdir -p '$SiteRoot/.incoming/$Version'"
if ($LASTEXITCODE -ne 0) { Fail "cannot reach $PiHost over ssh" }
foreach ($f in $files) {
    & scp @sshOpts -q $f.FullName "${PiHost}:$SiteRoot/.incoming/$Version/$($f.Name)"
    if ($LASTEXITCODE -ne 0) { Fail "scp $($f.Name) failed" }
}
& ssh @sshOpts $PiHost "sh '$SiteRoot/publish.sh' '$Version'"
if ($LASTEXITCODE -ne 0) { Fail 'publish.sh failed on the Pi' }

# --- read every file back from the live site -----------------------------------
# No --compressed: without Accept-Encoding nginx sends the file itself, so the
# hash comparison is exact.
$bad = 0
foreach ($f in $files) {
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        $info = & curl.exe -4 -s -o $tmp -w '%{http_code} %{content_type}' "$SiteUrl/$($f.Name)"
        $same = (Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
        Write-Host ("  {0,-22} {1,-40} {2}" -f $f.Name, $info, $(if ($same) { 'same bytes' } else { 'DIFFERENT' }))
        if (-not $same -or $info -notmatch '^200 ') { $bad++ }
    } finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
}
if ($bad) { Fail "$bad file(s) are not served as rendered" }
Write-Host "published $Version to $SiteUrl -- every file served byte for byte" -ForegroundColor Green
