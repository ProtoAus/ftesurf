#!/bin/bash
# One-time setup of the Linux build root, run as root in the Ubuntu-22.04 WSL distro:
#   wsl.exe -d Ubuntu-22.04 -u root --exec /bin/bash /mnt/c/FTESurf/tools/linux/chroot-setup.sh
# Debian bullseye = glibc 2.31, the floor the release binary is built against (upstream's
# ftechrootbuild.sh uses Debian oldstable for the same reason).  Idempotent.
set -eu
CH=/srv/ftebuild-bullseye
MIRROR=/srv/fteqw-mirror.git
SRC=/mnt/c/msys64/home/Lex/fteqw

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq debootstrap debian-archive-keyring >/dev/null

if [ ! -x "$CH/bin/bash" ]; then
	# bullseye moves to archive.debian.org once its LTS ends
	debootstrap --variant=buildd --keyring=/usr/share/keyrings/debian-archive-keyring.gpg \
		bullseye "$CH" http://deb.debian.org/debian ||
	debootstrap --variant=buildd --keyring=/usr/share/keyrings/debian-archive-keyring.gpg \
		bullseye "$CH" http://archive.debian.org/debian
fi

cp /etc/resolv.conf "$CH/etc/resolv.conf"
mountpoint -q "$CH/proc" || mount -t proc proc "$CH/proc"
trap 'umount "$CH/proc" 2>/dev/null; rm -f "$CH/etc/resolv.conf"' EXIT

# Headers only for what the engine dlopens (X11, GL/EGL, Wayland, audio, GnuTLS).  Deliberately
# no png/jpeg/freetype/vorbis/opus/speex/zlib -dev: those come from `make makelibs` as static
# archives, and a missing one must fail the link rather than pick up a system .so.
chroot "$CH" apt-get update -qq
chroot "$CH" apt-get install -y -qq --no-install-recommends \
	git ca-certificates pkg-config zip unzip file python3 autoconf automake libtool wget \
	mesa-common-dev libgl-dev libegl-dev libgles-dev libwayland-dev libxkbcommon-dev \
	libx11-dev libxcursor-dev libxi-dev libxrandr-dev libxss-dev \
	libasound2-dev libpulse-dev libgnutls28-dev

[ -d "$MIRROR" ] || git -c safe.directory='*' clone --mirror "$SRC" "$MIRROR"
echo "chroot-setup: $(chroot "$CH" sh -c 'ldd --version | head -1; gcc --version | head -1')"
