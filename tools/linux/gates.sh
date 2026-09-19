#!/bin/bash
# Static checks on a Linux build: bash gates.sh <release dir> <revision prefix> <short sha> [--expect-sonames]
# Prints "GATE <name> PASS|FAIL <detail>" per check; exits 1 if any gate failed.
R=${1:?release dir}; REVPREFIX=${2:?}; SHORT=${3:?}; EXPECT=${4:-}
EXE=$R/fteqw64; SV=$R/fteqw-sv64; PLUG=$R/fteplug_hl2_amd64.so
FAILS=0
gate() { if [ "$2" = PASS ]; then echo "GATE $1 PASS $3"; else echo "GATE $1 FAIL $3"; FAILS=$((FAILS+1)); fi; }
has() { grep -a -q -F -- "$2" "$1"; }

for f in "$EXE" "$SV" "$PLUG"; do [ -f "$f" ] || { echo "GATE files FAIL missing $f"; exit 1; }; done

# G1 shared libraries: libc/libm plus what glibc 2.31 still splits out; everything else is static or dlopened
bad=
for f in "$EXE" "$SV" "$PLUG"; do
	for lib in $(readelf -d "$f" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p'); do
		case $lib in libc.so.6|libm.so.6|libdl.so.2|libpthread.so.0|ld-linux-x86-64.so.2) ;; *) bad="$bad $(basename "$f"):$lib" ;; esac
	done
done
[ -z "$bad" ] && gate G1-needed PASS "libc/libm/libdl/libpthread only" || gate G1-needed FAIL "$bad"

# G2 glibc floor: bullseye's 2.31
max=$(for f in "$EXE" "$SV" "$PLUG"; do objdump -T "$f" | grep -o 'GLIBC_[0-9][0-9.]*'; done | sort -uV | tail -1)
if [ "$(printf '%s\n%s\n' "$max" GLIBC_2.31 | sort -V | tail -1)" = GLIBC_2.31 ]; then gate G2-glibc PASS "$max"; else gate G2-glibc FAIL "$max > GLIBC_2.31"; fi

# G3 no RPATH/RUNPATH on the executables (the plugin's /usr/local/lib RUNPATH is upstream's and harmless)
if readelf -d "$EXE" "$SV" | grep -q 'RPATH\|RUNPATH'; then gate G3-rpath FAIL "exe has RPATH/RUNPATH"; else gate G3-rpath PASS "none"; fi

# G4 GnuTLS compiled in (https lobby directory and board); loaded at runtime as libgnutls.so.30
has "$EXE" libgnutls.so.30 && has "$EXE" gnutls_certificate_allocate_credentials && gate G4-gnutls PASS "" || gate G4-gnutls FAIL "built without GnuTLS"

# G5 Wayland backend present (auto-fallback when GLX fails)
has "$EXE" "OpenGL (Wayland)" && has "$EXE" libwayland-client.so.0 && gate G5-wayland PASS "" || gate G5-wayland FAIL "no Wayland backend"

# G6 the plugin decodes zstd VTFs (5,589 of 6,748 Momentum mount textures)
has "$PLUG" "needs a build with zstd" && gate G6-zstd FAIL "plugin built without zstd" || gate G6-zstd PASS ""

# G7 embedded revision names this commit, clean
rev=$(grep -a -o -m1 "git-[0-9]*-[A-Za-z0-9._-]*" "$EXE")
case $rev in "$REVPREFIX"*-g"$SHORT"*-dirty*) gate G7-revision FAIL "$rev (dirty)" ;;
             "$REVPREFIX"*-g"$SHORT"*) gate G7-revision PASS "$rev" ;;
             *) gate G7-revision FAIL "'$rev' does not match ${REVPREFIX}...-g$SHORT" ;; esac

# G8 versioned sonames for libraries that exist unversioned only with -dev packages (Patch 386)
if [ "$EXPECT" = --expect-sonames ]; then
	miss=; for s in libEGL.so.1 libGLESv2.so.2 libXrandr.so.2 libXxf86vm.so.1 libXxf86dga.so.1; do has "$EXE" "$s" || miss="$miss $s"; done
	[ -z "$miss" ] && gate G8-sonames PASS "" || gate G8-sonames FAIL "missing$miss"
fi

# G9 format; G10 plugin entry point
file -b "$EXE" | grep -q 'ELF 64-bit.*x86-64' && readelf -l "$EXE" | grep -q '/lib64/ld-linux-x86-64.so.2' && gate G9-elf PASS "" || gate G9-elf FAIL "$(file -b "$EXE")"
nm -D --defined-only "$PLUG" | grep -q ' FTEPlug_Init$' && gate G10-plugin PASS "" || gate G10-plugin FAIL "no FTEPlug_Init"

[ $FAILS -eq 0 ]
