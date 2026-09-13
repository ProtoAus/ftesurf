#!/bin/sh
# =============================================================================
#  publish.sh -- swap a freshly-uploaded page into place.  NO SUDO.
#
#      sh /srv/nvme/ftesurf-site/publish.sh 0.1.0
#
#  release.ps1 scp's the rendered page to $SITE/.incoming/<version>/ and then
#  runs this.  Every path it touches is under /srv/nvme, which proto owns, so
#  routine releases never need a password.  install.sh does the one-time
#  /etc/nginx wiring separately.
#
#  Layout:
#      $SITE/.incoming/<v>/   scp lands here
#      $SITE/releases/<v>/    renamed into here once permissions are proven
#      $SITE/static           a SYMLINK to releases/<v>, swapped atomically
#
#  Rollback is two lines:
#      ln -sfn releases/0.1.0 /srv/nvme/ftesurf-site/.static.new
#      mv -T /srv/nvme/ftesurf-site/.static.new /srv/nvme/ftesurf-site/static
# =============================================================================
set -eu

SITE=/srv/nvme/ftesurf-site
KEEP=5

V="${1:-}"
# The version arrives from a Windows command line and lands next to `rm -rf`
# below.  release.ps1 validates it too; validating on both sides is cheaper
# than quoting correctly everywhere.
case "$V" in
    '' ) echo "usage: sh publish.sh <version>   e.g. 0.1.0" >&2; exit 1 ;;
esac
if ! echo "$V" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "refusing version '$V': must be MAJOR.MINOR.PATCH" >&2; exit 1
fi

IN="$SITE/.incoming/$V"
DST="$SITE/releases/$V"

[ -d "$IN" ]             || { echo "nothing staged at $IN" >&2; exit 1; }
[ -f "$IN/index.html" ]  || { echo "$IN has no index.html -- refusing to publish an empty release" >&2; exit 1; }

# -----------------------------------------------------------------------------
#  Permissions FIRST, and prove them.
#
#  scp -r from Windows creates drwx------ / -rw------- : OpenSSH's SFTP path has
#  no POSIX mode to copy from NTFS.  www-data then cannot traverse or read, and
#  the deploy "succeeds" into a 403.  Doing this before the symlink swap means
#  the tree is already correct at the instant it goes live.
#
#  The find is not decoration: a chmod that silently did nothing looks exactly
#  like one that worked.
# -----------------------------------------------------------------------------
chmod -R a+rX "$IN"
BAD=$(find "$IN" \( -type d ! -perm -o+x \) -o \( -type f ! -perm -o+r \) | head -20)
if [ -n "$BAD" ]; then
    echo "FAILED: these are still unreadable by nginx after chmod:" >&2
    echo "$BAD" >&2
    exit 1
fi

mkdir -p "$SITE/releases"
# Republishing the same version is normal while iterating on the page.
if [ -d "$DST" ]; then
    case "$DST" in
        "$SITE/releases/"*) rm -rf "$DST" ;;
        *) echo "refusing to remove '$DST': not under $SITE/releases" >&2; exit 1 ;;
    esac
fi
# Same filesystem, so this is a rename(2): nothing ever serves a half-copied tree.
mv "$IN" "$DST"

# -----------------------------------------------------------------------------
#  Atomic swap.  `mv -T` over an existing symlink is a rename(2), so there is no
#  instant at which `static` does not exist.  No open_file_cache is configured
#  anywhere on this box, so nginx resolves the alias per request and picks the
#  new target up immediately -- no reload needed.
# -----------------------------------------------------------------------------
if [ -e "$SITE/static" ] && [ ! -L "$SITE/static" ]; then
    echo "FAILED: $SITE/static exists and is not a symlink." >&2
    echo "        Move it aside first; this script will not delete a real directory there." >&2
    exit 1
fi
ln -sfn "releases/$V" "$SITE/.static.new"
mv -T "$SITE/.static.new" "$SITE/static"

echo "published $V  ->  $(readlink "$SITE/static")"

# -----------------------------------------------------------------------------
#  Keep the last $KEEP releases so a rollback target always exists.  Sorted by
#  parsed version, never by mtime: republishing an old version would reorder it.
# -----------------------------------------------------------------------------
CUR=$(readlink "$SITE/static" | sed 's|^releases/||')
ls -1 "$SITE/releases" 2>/dev/null \
  | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' \
  | sort -t. -k1,1n -k2,2n -k3,3n -r \
  | tail -n +$((KEEP + 1)) \
  | while read -r old; do
        [ "$old" = "$CUR" ] && continue
        rm -rf "$SITE/releases/$old"
        echo "  pruned old release $old"
    done

rmdir "$SITE/.incoming/$V" 2>/dev/null || true
exit 0
