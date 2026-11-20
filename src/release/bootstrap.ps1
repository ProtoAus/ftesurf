# Real FTESurf bootstrap build/provenance. Dot-sourced by release.ps1.
# Never select a pre-existing install executable: rebuild from an explicit source tree.
function Assert-BootstrapEntries ([string[]]$Entries, [string]$Platform) {
    $name = switch ($Platform) { 'win64' { 'WOS-Launcher.exe' }; 'linux64' { 'WOS-Launcher' }; default { throw 'unknown bootstrap platform' } }
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
    $onWindows = $env:OS -eq 'Windows_NT'
    if ($Distro -and -not $onWindows) {
        # Linux host: the same Bullseye builder as a plain child process. linux-bootstrap.sh becomes
        # root of its own user/mount/pid namespaces itself when not run as root (no sudo).
        $compiler = @(& rustc -vV)
        if ($LASTEXITCODE -ne 0) { throw 'Linux bootstrap requires rustc/cargo (rustup) on PATH' }
        $toolchain = $compiler[0]
        $target = @($compiler | Where-Object { $_ -like 'host: *' })[0].Substring(6)
        if ($target -ne 'x86_64-unknown-linux-gnu') { throw 'Linux bootstrap requires the glibc x86_64 target' }
        $out = & bash (Join-Path $PSScriptRoot 'linux-bootstrap.sh') $root (Join-Path $root 'target/ftesurf-linux') $LinuxBuildChroot 2>&1
        $code = $LASTEXITCODE
        $binary = Join-Path $root "target/ftesurf-linux/$target/release/WOS-Launcher"
    } elseif ($Distro) {
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
        $binary = Join-Path $root "target/ftesurf-linux/$target/release/WOS-Launcher"
    } else {
        if (-not $onWindows) { throw 'a Linux host cannot build the Windows bootstrap; use Use-PublishedBootstrap' }
        $compiler = @(& rustc -vV)
        if ($LASTEXITCODE -ne 0) { throw 'Windows bootstrap requires rustc/cargo' }
        $toolchain = $compiler[0]
        $target = @($compiler | Where-Object { $_ -like 'host: *' })[0].Substring(6)
        if ($target -notmatch '^x86_64-pc-windows-(msvc|gnu)$') { throw 'Windows bootstrap requires the Windows x86_64 target' }
        Push-Location $root
        try {
            $out = & cargo build --locked --release --bin WOS-Launcher --target $target --target-dir (Join-Path $root 'target') 2>&1
            $code = $LASTEXITCODE
        } finally { Pop-Location }
        $binary = Join-Path $root "target/$target/release/WOS-Launcher.exe"
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

# Linux host only. There is no MSVC toolchain here, so the Windows bootstrap is the previous release's standalone
# launcher, accepted ONLY when that release recorded this exact source -- commit and the full source fingerprint
# Get-BootstrapSource computes, clean -- for a Windows x86_64 target, and the file hashes to what it published.
# Nothing is rebuilt and nothing is taken from a player install: the bytes are a published, hash-pinned artifact
# of the same source. Any other source (a launcher change) needs a Windows host to rebuild it.
function Use-PublishedBootstrap ($Source, [string]$From) {
    if (-not $From) { throw 'a Linux host cannot build the Windows bootstrap: pass -ReuseWindowsBootstrap <dir> holding the previous release''s version.json and the WOS-Launcher-<version>.exe it names' }
    $From = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($From)
    $metaPath = Join-Path $From 'version.json'
    if (-not (Test-Path -LiteralPath $metaPath -PathType Leaf)) { throw "no version.json in $From" }
    $meta = [IO.File]::ReadAllText($metaPath) | ConvertFrom-Json -AsHashtable
    $b = $meta['bootstrap']
    if (-not $b) { throw "$metaPath records no bootstrap" }
    if ($b['commit'] -cne $Source.commit -or $b['source_sha256'] -cne $Source.source_sha256) {
        throw "published bootstrap ($($meta['version'])) was built from other source (commit $($b['commit'])); a launcher change must be rebuilt on a Windows host"
    }
    if (@($b['dirty_source']).Count -or $Source.dirty_source.Count) { throw 'published or current bootstrap source is dirty' }
    if ($b['target'] -cnotmatch '^x86_64-pc-windows-(msvc|gnu)$') { throw "published bootstrap target '$($b['target'])' is not Windows x86_64" }
    if ("$($b['sha256'])" -notmatch '^[0-9A-Fa-f]{64}$') { throw 'published bootstrap has no sha256' }
    $dl = @($meta['bootstrap_downloads'] | Where-Object { $_['platform'] -ceq 'win64' })
    if ($dl.Count -ne 1) { throw 'published metadata names no single win64 standalone bootstrap' }
    $name = [string]$dl[0]['name']
    if ($name -cnotmatch '^WOS-Launcher-\d+\.\d+\.\d+\.exe$') { throw "unexpected published bootstrap name '$name'" }
    $binary = Join-Path $From $name
    if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) { throw "missing $binary (fetch $($dl[0]['url']))" }
    if ((Get-Item -LiteralPath $binary).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'linked published bootstrap is not allowed' }
    $sha = (Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash
    if ($sha -ine $b['sha256'] -or $sha -ine [string]$dl[0]['sha256']) { throw "$name does not hash to the published bootstrap ($($b['sha256']))" }
    $bytes = [IO.File]::ReadAllBytes($binary)
    $pe = if ($bytes.Length -gt 64) { [BitConverter]::ToInt32($bytes, 60) } else { -1 }
    if ($bytes.Length -lt 64 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A -or $pe -lt 64 -or $pe + 6 -gt $bytes.Length -or
        [BitConverter]::ToUInt32($bytes, $pe) -ne 0x00004550 -or [BitConverter]::ToUInt16($bytes, $pe + 4) -ne 0x8664) { throw "$name is not an x86-64 PE executable" }
    [ordered]@{
        binary = $binary
        provenance = [ordered]@{
            commit = $Source.commit; source_sha256 = $Source.source_sha256
            dirty_source = $Source.dirty_source; rustc = "$($b['rustc'])"; target = "$($b['target'])"
            sha256 = $sha
            builder = "published $($meta['version']) bootstrap reused, same source fingerprint ($($b['builder']))"
            policy = 'separate archive bootstrap; never replaced by the ordinary update manifest'
        }
    }
}
