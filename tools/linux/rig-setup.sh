#!/bin/bash
# One-time setup of the clean "player" distro for Linux tests (WSL Debian, runtime libraries only):
#   wsl.exe -d Debian -u root --exec /bin/bash /mnt/c/FTESurf/tools/linux/rig-setup.sh
# User surf (uid 1000, which owns the WSLg runtime dir) runs every test; nothing -dev is installed,
# so a library the release binary only finds through a -dev symlink shows up as a failure here.
set -eu
export DEBIAN_FRONTEND=noninteractive
id surf >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash surf
grep -q '^default=surf' /etc/wsl.conf 2>/dev/null || printf '[user]\ndefault=surf\n' >> /etc/wsl.conf

pick() { for p in "$@"; do apt-cache show "$p" >/dev/null 2>&1 && { echo "$p"; return; }; done; }
apt-get update -qq
apt-get install -y -qq --no-install-recommends ca-certificates file binutils xz-utils \
	libgl1 libegl1 libgles2 libgl1-mesa-dri libx11-6 libx11-xcb1 libxi6 libxcursor1 libxrandr2 \
	libxxf86vm1 libxss1 libwayland-client0 libwayland-egl1 libxkbcommon0 libpulse0 \
	"$(pick libasound2t64 libasound2)" "$(pick libgnutls30t64 libgnutls30)" \
	x11-xserver-utils xinput xdotool xvfb

# Gate: a runtime-only system, or the soname tests do not discriminate.
dev=$(dpkg-query -W -f '${Package}\n' | grep -- '-dev$' || true)
[ -z "$dev" ] || { echo "rig-setup: -dev packages present: $dev" >&2; exit 1; }
for l in libEGL libGLESv2 libXrandr libXxf86vm libXxf86dga; do
	[ ! -e "/usr/lib/x86_64-linux-gnu/$l.so" ] || { echo "rig-setup: unversioned $l.so exists" >&2; exit 1; }
done
. /etc/os-release; echo "rig-setup: $PRETTY_NAME, $(ldd --version | head -1)"
