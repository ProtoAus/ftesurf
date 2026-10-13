#!/bin/bash
# Build against the engine's Bullseye baseline, offline, without modifying its
# shared chroot/cache. Mounts live only in this process's private namespace.
set -euo pipefail
export LC_ALL=C
fail() { echo "linux-bootstrap: $*" >&2; exit 1; }
if [[ ${1-} != --inside ]]; then
    [[ $EUID == 0 ]] || fail 'requires WSL root and private mount namespaces'
    exec unshare --mount --propagation private -- bash "$0" --inside "$@"
fi
shift
[[ $# == 3 ]] || fail 'usage: <source> <target-dir> <bullseye-chroot>'
source=$(realpath -e -- "$1")
mkdir -p -- "$2"
out=$(realpath -e -- "$2")
ch=$(realpath -e -- "$3")
[[ -f $source/Cargo.lock && -f $source/Cargo.toml ]] || fail 'missing locked bootstrap source'
[[ -d $ch/mnt && -d $ch/proc && -d $ch/dev ]] || fail 'incomplete build chroot'
[[ $out != "$source" && $ch != / ]] || fail 'invalid output/chroot'
compiler=$(rustup which rustc)
cargo=$(rustup which cargo)
toolchain=$(dirname -- "$compiler")
[[ $(dirname -- "$cargo") == "$toolchain" ]] || fail 'rustc/cargo toolchains differ'
registry=$(realpath -e -- "${CARGO_HOME:-$HOME/.cargo}/registry")
# Refuse a builder with existing submounts: remounting only its root read-only
# must not leave a peer's writable child mount reachable to build scripts.
while IFS= read -r mounted; do
    [[ $mounted != "$ch" && $mounted != "$ch/"* ]] || fail 'builder has active mounts; coordinate before use'
done < <(findmnt -rn -o TARGET)
# No writes even to /build, /tmp or /root in the shared builder. Overlay only
# existing mountpoints; all writable mountpoints and compiler tmp are task-owned.
mount --bind "$ch" "$ch"
mount -o remount,bind,ro "$ch"
mount -t tmpfs -o mode=0755 tmpfs "$ch/mnt"
mkdir -p "$ch/mnt/"{source,target,rust,registry}
mount --bind "$source" "$ch/mnt/source"
mount -o remount,bind,ro "$ch/mnt/source"
mount --bind "$out" "$ch/mnt/target"
mount --bind "$(dirname -- "$toolchain")" "$ch/mnt/rust"
mount -o remount,bind,ro "$ch/mnt/rust"
mount --bind "$registry" "$ch/mnt/registry"
mount -o remount,bind,ro "$ch/mnt/registry"
mount -t proc -o ro proc "$ch/proc"
mount --bind /dev "$ch/dev"
mount -o remount,bind,ro "$ch/dev"
chroot "$ch" /usr/bin/env -i PATH=/mnt/rust/bin:/usr/bin:/bin HOME=/mnt/target \
    LC_ALL=C CARGO_HOME=/mnt/target/cargo-home CARGO_TARGET_DIR=/mnt/target \
    TMPDIR=/mnt/target/tmp /bin/bash -euo pipefail -c '
    baseline=$(getconf GNU_LIBC_VERSION)
    [[ $baseline == "glibc 2.31" ]] || { echo "linux-bootstrap: expected glibc 2.31 builder, got $baseline" >&2; exit 1; }
    mkdir -p "$CARGO_HOME" "$TMPDIR"
    if [[ ! -e $CARGO_HOME/registry ]]; then ln -s /mnt/registry "$CARGO_HOME/registry"; fi
    cd /mnt/source
    cargo build --locked --offline --release --bin ftesurf-launcher --target x86_64-unknown-linux-gnu
    cargo metadata --locked --offline --format-version 1 --filter-platform x86_64-unknown-linux-gnu > /mnt/target/metadata.json
    getconf GNU_LIBC_VERSION > /mnt/target/builder-glibc.txt
    rustc -vV > /mnt/target/compiler.txt
    readelf -V /mnt/target/x86_64-unknown-linux-gnu/release/ftesurf-launcher > /mnt/target/versions.txt
    grep -o "GLIBC_[0-9][0-9.]*" /mnt/target/versions.txt | sort -Vu > /mnt/target/glibc-symbols.txt
    floor=$(tail -1 /mnt/target/glibc-symbols.txt)
    [[ $(printf "%s\n" GLIBC_2.31 "$floor" | sort -V | tail -1) == GLIBC_2.31 ]] || { echo "linux-bootstrap: floor $floor exceeds 2.31" >&2; exit 1; }
    /mnt/target/x86_64-unknown-linux-gnu/release/ftesurf-launcher --help > /mnt/target/help-baseline.txt
    grep -q -- --manifest-url /mnt/target/help-baseline.txt
    echo "BOOTSTRAP glibc 2.31; measured $floor; --help acted on baseline"
'
