#!/usr/bin/env python3
"""
mapmedia_publish.py -- copy this PC's map media to the Pi for the menu (P1099).
tools/mapscan_6h.ps1 runs it after mapmedia_refresh.py.

The menu fetches mapmeta.txt and mapdeps.txt from play.proto.bar/ftesurf/media/
once a session, and a map's thumbnail from media/thumbs/<uuid>.jpg when no atlas
page it has holds that map's cell (tiers and pictures for maps a release has not
caught up with).  nginx serves the directory with snippets/ftesurf-media.conf.

Thumbnails go first and tables last, each through a temp name and a rename, so
the Pi never serves a table naming a picture it does not have, or half a table.
A table without a 14-digit `# stamp` (one mapmedia_refresh.py did not write) is
not sent: the menu would keep it but never prefer it.

Exit: 0 done, 1 the Pi did not answer, 2 a table was not sent.
"""
import argparse
import hashlib
import io
import os
import re
import subprocess
import sys
import tarfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
SURFDIR = os.path.dirname(TOOLS)
PI = "proto@192.168.1.102"
MEDIA = "/srv/nvme/ftesurf-site/media"
THUMB_MAX = 120 * 1024           # the engine's r_image_downloadsizelimit is 131072
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", PI]


def say(s):
    print(s, flush=True)


def pi(cmd, data=None):
    r = subprocess.run(SSH + [cmd], input=data, capture_output=True, timeout=600)
    if r.returncode != 0:
        raise OSError("ssh %r: %s" % (cmd[:60], r.stderr.decode(errors="replace").strip()[:200]))
    return r.stdout.decode(errors="replace")


def stamped(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, l in zip(range(40), fh):
            if l.startswith("# stamp "):
                return bool(re.fullmatch(r"\d{14}", l[8:].strip()))
    return False


def thumbs(gamedir):
    """uuid -> small JPEG path, for every mapmeta row whose picture is on disk."""
    out = {}
    shots = os.path.join(gamedir, "gfx", "mapshots")
    for l in open(os.path.join(gamedir, "data", "mapmeta.txt"), encoding="utf-8", errors="replace"):
        t = l.split()
        if len(t) > 8 and t[0] == "meta" and UUID.match(t[8]):
            p = os.path.join(shots, t[8] + "-small.jpg")
            if os.path.isfile(p) and 0 < os.path.getsize(p) <= THUMB_MAX:
                out[t[8]] = p
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--gamedir", default=os.path.join(SURFDIR, "ftesurf"))
    a = ap.parse_args()
    g = os.path.abspath(a.gamedir)
    rc = 0
    try:
        pi("mkdir -p %s/thumbs" % MEDIA)
        have = set(pi("ls %s/thumbs" % MEDIA).split())
        want = thumbs(g)
        send = sorted(u for u in want if u + ".jpg" not in have)
        if send:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                for u in send:
                    tar.add(want[u], arcname=u + ".jpg")
            # Two passes: one find with two `-exec +` batches let mv move files chmod had
            # not reached yet (the first publish, 28 Oct).
            pi("set -e; T=$(mktemp -d %s/.in.XXXXXX); trap 'rm -rf \"$T\"' EXIT; tar -xf - -C \"$T\"; "
               "find \"$T\" -name '*.jpg' -exec chmod 644 {} +; "
               "find \"$T\" -name '*.jpg' -exec mv -f -t %s/thumbs {} +"
               % (MEDIA, MEDIA), buf.getvalue())
        say("  publish: %d thumbnail(s) sent, %d already on the Pi" % (len(send), len(want) - len(send)))

        for name in ("mapmeta.txt", "mapdeps.txt"):
            src = os.path.join(g, "data", name)
            if not os.path.exists(src) or not stamped(src):
                say("  publish: %s NOT SENT -- no stamp from mapmedia_refresh.py" % name)
                rc = 2
                continue
            data = open(src, "rb").read()
            there = pi("sha256sum %s/%s 2>/dev/null || true" % (MEDIA, name)).split()
            if there and there[0] == hashlib.sha256(data).hexdigest():
                say("  publish: %s already the Pi's" % name)
                continue
            pi("set -e; cat > %s/.%s.new; chmod 644 %s/.%s.new; mv -f %s/.%s.new %s/%s"
               % (MEDIA, name, MEDIA, name, MEDIA, name, MEDIA, name), data)
            say("  publish: %s sent (%d bytes)" % (name, len(data)))
    except (OSError, subprocess.TimeoutExpired) as e:
        say("  publish: the Pi did not take it (%s)" % e)
        return 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
