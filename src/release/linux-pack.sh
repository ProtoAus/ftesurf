#!/bin/sh
# The WSL half of release.ps1 -Linux. Always invoked as
#   wsl.exe -d <distro> --exec sh linux-pack.sh <command> <args...>
#
#   tools                                     exit 1 naming any missing tool
#   inspect <file>...                         N <file> <needed lib> / G <file> GLIBC_x.y / HOST / OS
#   pack <stage-root> <top> <out> <exec>...   modes set on an ext4 copy (drvfs reports 777), owner 0/0
#   verify <archive> <top>                    T <tar -tv line> / H <sha256sum line> / L <ldd not-found line>
#
# dash has no pipefail, so nothing whose failure matters goes through a pipe.
set -u
umask 022
die() { echo "linux-pack: $*" >&2; exit 1; }
tmp() { t=$(mktemp -d "/tmp/ftesurf-$1.XXXXXX") || die "mktemp failed"; trap 'rm -rf "$t"' EXIT; }
prefix() { while IFS= read -r l; do printf '%s %s\n' "$1" "$l"; done < "$2"; }

cmd=${1-}
[ $# -gt 0 ] && shift
case $cmd in
tools)
	rc=0
	for c in tar xz sha256sum readelf ldd mktemp cp find chmod getconf grep sed sort; do
		command -v "$c" >/dev/null 2>&1 || { echo "missing: $c"; rc=1; }
	done
	exit $rc
	;;
inspect)
	tmp inspect
	for f in "$@"; do
		b=$(basename -- "$f")
		readelf -d -- "$f" > "$t/d" 2>&1 || die "readelf -d $f: $(cat "$t/d")"
		sed -n 's/^.*(NEEDED).*\[\(.*\)\].*$/\1/p' "$t/d" > "$t/n"
		prefix "N $b" "$t/n"
		readelf -V -- "$f" > "$t/v" 2>&1 || die "readelf -V $f: $(cat "$t/v")"
		grep -o 'GLIBC_[0-9][0-9.]*' "$t/v" > "$t/g" || true
		sort -u "$t/g" > "$t/gs" || die "sort"
		prefix "G $b" "$t/gs"
	done
	v=$(getconf GNU_LIBC_VERSION) || die "getconf GNU_LIBC_VERSION failed"
	echo "HOST ${v#glibc }"
	( . /etc/os-release && echo "OS ${PRETTY_NAME:-unknown}" )
	;;
pack)
	[ $# -ge 3 ] || die "usage: pack <stage-root> <top> <out> <exec-relpath>..."
	stage=$1 top=$2 out=$3
	shift 3
	[ -d "$stage/$top" ] || die "no directory $stage/$top"
	tmp pack
	cp -R --preserve=timestamps -- "$stage/$top" "$t/" || die "copy to ext4 failed"
	find "$t/$top" -type d -exec chmod 0755 {} + || die "chmod of directories failed"
	find "$t/$top" -type f -exec chmod 0644 {} + || die "chmod of files failed"
	for e in "$@"; do
		[ -f "$t/$top/$e" ] || die "exec path is not a file in the stage: $e"
		chmod 0755 "$t/$top/$e" || die "chmod $e failed"
	done
	find "$t/$top" ! -type f ! -type d > "$t/odd" || die "find failed"
	[ -s "$t/odd" ] && die "neither file nor directory: $(cat "$t/odd")"
	tar --sort=name --format=gnu --owner=0 --group=0 --numeric-owner -C "$t" -cf "$t/a.tar" "$top" || die "tar failed"
	xz -9 -T1 "$t/a.tar" || die "xz failed"
	{ cp "$t/a.tar.xz" "$out.part" && mv -f "$out.part" "$out"; } || die "cannot write $out"
	echo "PACKED $out"
	;;
verify)
	[ $# -eq 2 ] || die "usage: verify <archive> <top>"
	a=$1 top=$2
	tmp verify
	xz -t -- "$a" || die "xz -t failed: $a"
	tar --numeric-owner -tvJf "$a" > "$t/list" || die "tar -t failed"
	prefix T "$t/list"
	mkdir "$t/x" || die "mkdir"
	tar -xJf "$a" -C "$t/x" || die "extract failed"
	( cd "$t/x" && find "$top" -type f -exec sha256sum {} + ) > "$t/h" || die "sha256sum failed"
	prefix H "$t/h"
	for f in "$top/ftesurf64" "$top/fteplug_hl2_amd64.so"; do
		[ -f "$t/x/$f" ] || continue
		ldd "$t/x/$f" > "$t/l" 2>&1 || true
		grep 'not found' "$t/l" > "$t/nf" || true
		prefix "L $f:" "$t/nf"
	done
	echo "VERIFIED"
	;;
*)
	die "unknown command '$cmd' (tools, inspect, pack, verify)"
	;;
esac
