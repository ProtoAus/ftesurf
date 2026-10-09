# Launch from the gamedir checkout, preserving the operator's selected model.
[CmdletBinding()]
param(
    [switch]$Check,
    [string]$FteRoot = 'C:\msys64\home\Lex\fteqw',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PiArgs
)
$ErrorActionPreference = 'Stop'
# pi-lsp currently uses PI_AGENT_DIR/HOME rather than pi.dev core's agent-dir resolver.
if (!$env:PI_AGENT_DIR) {
    $env:PI_AGENT_DIR = if ($env:PI_CODING_AGENT_DIR) { $env:PI_CODING_AGENT_DIR } else { Join-Path $HOME '.pi/agent' }
}
$root = Split-Path $PSScriptRoot -Parent
if (!(Test-Path (Join-Path $root 'AGENTS.md'))) { throw 'Missing AGENTS.md' }
foreach ($command in @('pi', 'clangd', 'python')) {
    if (!(Get-Command $command -ErrorAction SilentlyContinue)) { throw "Missing $command on PATH" }
}
if ($Check) {
    Write-Host "pi.dev startup cwd: $root"
    & pi --version
    if ($LASTEXITCODE -ne 0) { throw 'pi.dev version check failed' }
    & clangd --version
    if ($LASTEXITCODE -ne 0) { throw 'clangd version check failed' }
    $settings = Get-Content -Raw (Join-Path $root '.pi/settings.json') | ConvertFrom-Json
    Write-Host "Project packages: $($settings.packages -join ', ')"
    $lsp = Join-Path $env:PI_AGENT_DIR 'lsp.json'
    if (!(Test-Path $lsp)) { throw "Missing $lsp; follow .pi/README.md" }
    $lspConfig = Get-Content -Raw $lsp | ConvertFrom-Json
    foreach ($server in $lspConfig.servers) {
        if ($server.enabled -eq $false) { continue }
        if (!(Get-Command $server.bin -ErrorAction SilentlyContinue)) { throw "LSP executable unavailable: $($server.bin)" }
    }
    $database = Join-Path $FteRoot 'compile_commands.json'
    if (!(Test-Path $database)) { throw "Missing $database; run python tools/clangdb.py" }
    $entries = @(Get-Content -Raw $database | ConvertFrom-Json)
    if ($entries.Count -eq 0) { throw 'Empty engine compilation database' }
    Write-Host "LSP configuration: $lsp"
    Write-Host "Engine database: $database ($($entries.Count) translation units)"
    Write-Host 'Static preflight only; ask pi.dev for an engine hover to test the live server.'
    exit 0
}
Push-Location $root
try {
    & pi @PiArgs
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
