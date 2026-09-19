#!/bin/bash
# Portable Linux x86_64 build of the FTESurf engine fork at one commit, inside the bullseye chroot
# made by chroot-setup.sh.  Run as root in Ubuntu-22.04 WSL (build-linux.ps1 wraps this):
#   bash tools/linux/build.sh <engine commit> [--expect-sonames]
# Output (Windows-visible): C:\FTESurf\dist\linux-build\  -- fteqw64, fteplug_hl2_amd64.so,
# fteqw-sv64, BUILDINFO.txt, db/ (unstripped, for crash symbolising), logs/.
set -eu
COMMIT=${1:?usage: build.sh <engine commit> [--expect-sonames]}
EXPECT=${2:-}
HERE=$(cd "$(dirname "$0")" && pwd)
CH=/srv/ftebuild-bullseye
MIRROR=/srv/fteqw-mirror.git
CACHE=/srv/ftebuild-cache
SRC=/mnt/c/msys64/home/Lex/fteqw
OUT=/mnt/c/FTESurf/dist/linux-build
ZSTDVER=1.5.6
JOBS=$(nproc)

die() { echo "build.sh: $*" >&2; exit 1; }
[ -x "$CH/bin/bash" ] || die "no chroot at $CH -- run chroot-setup.sh first"

# 1. The commit, from the Windows repo, into the mirror (tags too: the revision stamp uses describe).
git -C "$MIRROR" -c safe.directory='*' fetch -q --prune "$SRC" '+refs/heads/*:refs/heads/*' '+refs/tags/*:refs/tags/*'
COMMIT=$(git -C "$MIRROR" rev-parse --verify "$COMMIT^{commit}") || die "unknown commit"

# 2. A fresh full clone at the commit: a clean tree is what makes the embedded revision honest.
W=$CH/build/fteqw
rm -rf "$CH/build" && mkdir -p "$CH/build"
git clone -q "$MIRROR" "$W"
git -C "$W" -c advice.detachedHead=false checkout -q --detach "$COMMIT"
[ -z "$(git -C "$W" status --porcelain)" ] || die "clone is not clean"
touch "$W/plugins/hl2/mat_vmt_progs.h"	# tracked; newer than its glsl so nothing regenerates it
REVPREFIX="git-$(( $(git -C "$W" rev-list --count HEAD) + 29 ))-"
SHORT=$(git -C "$W" rev-parse HEAD | cut -c1-7)	# describe abbreviates to >= 7

# 3. Pinned third-party tarballs (the chroot has no network).  Seed from the Windows engine tree's
#    own copies when present, else download on the host; every file must match tarballs.sha256.
mkdir -p "$CACHE"
while read -r sha file url; do
	case $sha in ''|\#*) continue ;; esac
	if [ ! -f "$CACHE/$file" ]; then
		if [ -f "$SRC/engine/$file" ]; then cp "$SRC/engine/$file" "$CACHE/$file"
		else wget -q -O "$CACHE/$file.part" "$url" && mv "$CACHE/$file.part" "$CACHE/$file"; fi
	fi
	echo "$sha  $CACHE/$file" | sha256sum -c --quiet - || die "$file does not match tarballs.sha256"
	case $file in zstd-*) cp "$CACHE/$file" "$CH/build/" ;; *) cp "$CACHE/$file" "$W/engine/" ;; esac
done < "$HERE/tarballs.sha256"

mountpoint -q "$CH/proc" || mount -t proc proc "$CH/proc"
trap 'umount "$CH/proc" 2>/dev/null || true' EXIT
LOGS=$CH/build/logs; mkdir -p "$LOGS"
inch() { chroot "$CH" /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/root LANG=C /bin/bash -c "$1"; }

# 4. Static third-party libs.  -j1: libz.a/libz.pc, libpng.a/libpng.pc and libfreetype.a/ft2build.h
#    are two-target rules with one recipe (engine/Makefile makelibs), which race under -j.
inch "cd /build/fteqw/engine && make -j1 makelibs FTE_TARGET=linux64" > "$LOGS/makelibs.log" 2>&1 || die "makelibs failed (logs/makelibs.log)"
for a in libjpeg.a libz.a libz9.a libpng.a libogg.a libvorbis.a libvorbisfile.a libopus.a libspeex.a libspeexdsp.a libfreetype.a ft2build.h vulkan/vulkan.h; do
	[ -e "$W/engine/libs-x86_64-linux-gnu/$a" ] || die "makelibs did not produce $a"
done

# 5. zstd for the hl2 plugin (Strata's VTF 7.6 auxiliary compression, Patch 292): decompression
#    only, PIC, static -- the plugin is a shared object.
inch "cd /build && tar -xzf zstd-$ZSTDVER.tar.gz && make -C zstd-$ZSTDVER/lib -j$JOBS libzstd.a CFLAGS='-O2 -fPIC' ZSTD_LIB_COMPRESSION=0 ZSTD_LIB_DICTBUILDER=0 ZSTD_LIB_DEPRECATED=0 ZSTD_LEGACY_SUPPORT=0" > "$LOGS/zstd.log" 2>&1 || die "zstd failed (logs/zstd.log)"

# 6. The engine, the dedicated server and the hl2 plugin.
inch "cd /build/fteqw/engine && make -j$JOBS m-rel FTE_TARGET=linux64" > "$LOGS/m-rel.log" 2>&1 || die "m-rel failed (logs/m-rel.log)"
inch "cd /build/fteqw/engine && make -j$JOBS sv-rel FTE_TARGET=linux64" > "$LOGS/sv-rel.log" 2>&1 || die "sv-rel failed (logs/sv-rel.log)"
inch "cd /build/fteqw/engine && make -j$JOBS plugins-rel FTE_TARGET=linux64 NATIVE_PLUGINS=hl2 HL2_ZSTD_CFLAGS='-DHAVE_ZSTD -I/build/zstd-$ZSTDVER/lib' HL2_ZSTD_LDFLAGS=/build/zstd-$ZSTDVER/lib/libzstd.a" > "$LOGS/plugins.log" 2>&1 || die "plugins-rel failed (logs/plugins.log)"
[ -z "$(git -C "$W" status --porcelain --untracked-files=no)" ] || die "the build modified tracked files"

R=$W/engine/release
bash "$HERE/gates.sh" "$R" "$REVPREFIX" "$SHORT" $EXPECT > "$LOGS/gates.log" 2>&1; GATES=$?
cat "$LOGS/gates.log"

# 7. Publish: previous build kept under linux-build-archive/, new one swapped in whole.
STAGE=$OUT.tmp
rm -rf "$STAGE" && mkdir -p "$STAGE/db" "$STAGE/logs"
cp "$R/fteqw64" "$R/fteqw-sv64" "$R/fteplug_hl2_amd64.so" "$STAGE/"
cp "$R/fteqw64.db" "$R/fteqw-sv64.db" "$STAGE/db/" 2>/dev/null || true
cp "$LOGS"/*.log "$STAGE/logs/"
REV=$(grep -a -o -m1 "git-[0-9]*-[A-Za-z0-9._-]*" "$R/fteqw64" || true)
{
	echo "FTESURF-LINUX-BUILD 1"
	echo "commit    $COMMIT"
	echo "revision  $REV"
	echo "builder   $(. "$CH/etc/os-release" && echo "$PRETTY_NAME")"
	echo "cc        $(inch 'cc --version | head -1')"
	echo "built     $(date -u +%Y-%m-%dT%H:%M:%SZ)"
	if [ $GATES -eq 0 ]; then echo "gates     all PASS"; else echo "gates     FAIL $(grep -c 'FAIL' "$LOGS/gates.log")"; fi
	for f in fteqw64 fteplug_hl2_amd64.so fteqw-sv64; do
		echo "sha256    $(sha256sum "$STAGE/$f" | cut -d' ' -f1)  $f"
	done
} > "$STAGE/BUILDINFO.txt"
if [ -d "$OUT" ]; then
	mkdir -p "$OUT-archive"
	mv "$OUT" "$OUT-archive/$(sed -n 's/^commit *\(.\{12\}\).*/\1/p' "$OUT/BUILDINFO.txt" 2>/dev/null || echo old)-$(date -u +%Y%m%dT%H%M%SZ)"
fi
mv "$STAGE" "$OUT"
cat "$OUT/BUILDINFO.txt"
exit $GATES
