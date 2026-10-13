# Real FTESurf bootstrap build/provenance. Dot-sourced by release.ps1.
# Never select a pre-existing install executable: rebuild from an explicit source tree.
function Assert-BootstrapEntries ([string[]]$Entries, [string]$Platform) {
    $name = switch ($Platform) { 'win64' { 'ftesurf-launcher.exe' }; 'linux64' { 'ftesurf-launcher' }; default { throw 'unknown bootstrap platform' } }
    foreach ($required in @($name, 'notices/bootstrap.txt')) {
        if ($Entries -cnotcontains $required) { throw "archive is missing a required bootstrap file: $required" }
    }
}

function Get-BootstrapSource ([string]$Root) {
    if (-not $Root) { throw 'Pass -LauncherRoot (or FTESURF_LAUNCHERROOT) naming the inspected Rust source tree.' }
    $Root = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Root)
    foreach ($required in @('Cargo.toml', 'Cargo.lock', 'LICENSE', 'src/ftesurf.rs', 'src/ftesurf_update.rs')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $required) -PathType Leaf)) {
            throw "bootstrap source missing: $required"
        }
    }
    $paths = @('Cargo.toml', 'Cargo.lock', 'LICENSE', 'src')
    foreach ($optional in @('build.rs', 'rust-toolchain', 'rust-toolchain.toml', '.cargo')) {
        if (Test-Path -LiteralPath (Join-Path $Root $optional)) { $paths += $optional }
    }
    # Hash all inputs, including untracked source. Ref alone does not identify a dirty build.
    $lines = foreach ($rel in $paths) {
        $p = Join-Path $Root $rel
        $items = @((Get-Item -LiteralPath $p))
        if ($items[0].PSIsContainer) { $items += @(Get-ChildItem -LiteralPath $p -Recurse -Force) }
        foreach ($item in $items) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'linked bootstrap source is not allowed' }
            if (-not $item.PSIsContainer) {
                $name = $item.FullName.Substring($Root.TrimEnd('\', '/').Length + 1).Replace('\', '/')
                "$name $((Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLower())"
            }
        }
    }
    for ($p = Get-Item -LiteralPath $Root; $null -ne $p; $p = $p.Parent) {
        if ($p.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'linked bootstrap root is not allowed' }
    }
    $text = (($lines | Sort-Object) -join "`n") + "`n"
    $hash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($text))).ToLower()
    $head = & git -C $Root rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw 'bootstrap tree is not an inspected Git checkout' }
    $dirty = @(& git -C $Root status --porcelain --untracked-files=all -- @paths)
    if ($LASTEXITCODE -ne 0) { throw 'cannot inspect bootstrap source status' }
    [ordered]@{ root = $Root; commit = "$head".Trim(); source_sha256 = $hash; dirty_source = $dirty }
}

function Assert-BootstrapGlibc ([string[]]$Versions) {
    if (-not $Versions.Count) { throw 'Linux bootstrap has no measured glibc floor' }
    $floor = ($Versions | ForEach-Object { [version]$_ } | Sort-Object -Descending | Select-Object -First 1).ToString()
    if ([version]$floor -gt [version]'2.31') { throw "Linux archive needs glibc $floor; supported ceiling is 2.31 (host compatibility is not sufficient)" }
    return $floor
}

function Build-Bootstrap ($Source, [string]$Distro = '', [string]$LinuxBuildChroot = '/srv/ftebuild-bullseye') {
    $root = $Source.root
    if ($Distro) {
        $wroot = & wsl.exe -d $Distro --exec wslpath -a -u $root
        if ($LASTEXITCODE -ne 0) { throw 'cannot resolve Linux bootstrap source path' }
        $wroot = "$wroot".Trim()
        $compiler = @(& wsl.exe -d $Distro -u root --exec bash -lc 'rustc -vV')
        if ($LASTEXITCODE -ne 0) { throw 'Linux bootstrap requires rustc/cargo in the selected WSL distro' }
        $toolchain = $compiler[0]
        $target = @($compiler | Where-Object { $_ -like 'host: *' })[0].Substring(6)
        if ($target -ne 'x86_64-unknown-linux-gnu') { throw 'Linux bootstrap requires the glibc x86_64 target' }
        $builder = & wsl.exe -d $Distro --exec wslpath -a -u (Join-Path $PSScriptRoot 'linux-bootstrap.sh')
        if ($LASTEXITCODE -ne 0) { throw 'cannot resolve Linux bootstrap builder path' }
        $out = & wsl.exe -d $Distro -u root --exec bash -lc 'exec bash "$@"' linux-bootstrap "$builder" $wroot "$wroot/target/ftesurf-linux" $LinuxBuildChroot 2>&1
        $code = $LASTEXITCODE
        $binary = Join-Path $root "target/ftesurf-linux/$target/release/ftesurf-launcher"
    } else {
        $compiler = @(& rustc -vV)
        if ($LASTEXITCODE -ne 0) { throw 'Windows bootstrap requires rustc/cargo' }
        $toolchain = $compiler[0]
        $target = @($compiler | Where-Object { $_ -like 'host: *' })[0].Substring(6)
        if ($target -notmatch '^x86_64-pc-windows-(msvc|gnu)$') { throw 'Windows bootstrap requires the Windows x86_64 target' }
        Push-Location $root
        try {
            $out = & cargo build --locked --release --bin ftesurf-launcher --target $target --target-dir (Join-Path $root 'target') 2>&1
            $code = $LASTEXITCODE
        } finally { Pop-Location }
        $binary = Join-Path $root "target/$target/release/ftesurf-launcher.exe"
    }
    foreach ($line in $out) { Write-Host "    $line" }
    if ($code -ne 0) { throw "bootstrap build failed (exit $code)" }
    if ("$out" -match '(?m)warning:') { throw 'bootstrap build emitted warnings' }
    if ($Distro) {
        $builtCompiler = Get-Content -LiteralPath (Join-Path $root 'target/ftesurf-linux/compiler.txt')
        if (($builtCompiler -join "`n").Trim() -cne ($compiler -join "`n").Trim()) { throw 'Linux compiler changed during bootstrap build' }
    }
    $after = Get-BootstrapSource $root
    if ($after.commit -ne $Source.commit -or $after.source_sha256 -ne $Source.source_sha256) {
        throw 'bootstrap source changed during its build; refusing mixed provenance'
    }
    if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) { throw 'bootstrap build produced no executable' }
    [ordered]@{
        binary = $binary
        provenance = [ordered]@{
            commit = $Source.commit; source_sha256 = $Source.source_sha256
            dirty_source = $Source.dirty_source; rustc = "$toolchain".Trim(); target = $target
            sha256 = (Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash
            builder = $(if ($Distro) { 'isolated Bullseye glibc 2.31; locked offline Cargo; baseline --help' } else { 'native Windows Cargo' })
            policy = 'separate archive bootstrap; never replaced by the ordinary update manifest'
        }
    }
}
