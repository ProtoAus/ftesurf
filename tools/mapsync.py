#!/usr/bin/env python3
"""
mapsync.py -- copy the maps a lobby server needs from the local Momentum install
to the NanoPi, and nothing it does not need.

WHY THIS EXISTS.  build.ps1 -Pi ships qwprogs.dat and csprogs.dat, which is the
pair a dedicated server loads, and deliberately nothing else.  Maps are a
different problem: 1312 BSPs totalling 45 GB live in the player's Steam install,
the Pi has no Steam install, and the always-online model needs a server able to
host any map somebody picks.  That is a bulk one-way copy with a disk-space
ceiling, not a deploy, so it does not belong in build.ps1's atomic-rename dance.

WHAT A SERVER ACTUALLY NEEDS, which is less than a client.
  * The BSP.  Collision, entities and the static-prop lump all come from it.
  * The zone JSON, maps/zones/online/<map>.json.  WITHOUT IT THE MAP LOADS AND
    CANNOT BE TIMED -- there is no start, no end and no checkpoints, so the run
    timer never arms.  A BSP copied without its zone is a map you can walk
    around in and cannot set a time on, which looks like a broken game rather
    than a missing file.  So the two are always copied together.
  * NOT the CS:S/HL2 material VPKs.  Textures are client-side.  Prop COLLISION
    is not -- VBSP_LoadStaticProps is commented "present on server, because
    they're potentially solid" and props collide against their .phy hulls -- but
    those models resolve out of game/cstrike/'s VPKs, which are already on the
    Pi.  game/hl2/ is empty, which is a latent gap for maps using HL2 props.
    Watch server<N>.log's per-map census line for it:
        "<map>.bsp: collision shapes -- N .phy hull (T tris), ... M models with
         no .phy"
    M counts genuinely hull-less props too, exactly as Source does, so M > 0 is
    not by itself evidence of missing content.  A load ERROR is.

THE TIER THAT MATTERS IS ZONE COVERAGE, not map name or size.  Measured on this
install: 1312 BSPs / 45.0 GB, of which 531 / 13.5 GB have a zone file and 781 /
31.5 GB do not.  So seventy percent of the bulk cannot produce a ranked run at
all, and --zoned-only copies the competitively meaningful third.  That is the
option to reach for when the Pi is tight; when it is not, copy everything,
because an unzoned map still works as a place to play.

WHY THIS REFUSES BY DEFAULT.  It prints the plan and exits unless --go is
passed.  A 45 GB copy onto a disk that had 58 GB free is the kind of thing that
should be looked at once by a human before it runs, and re-running the preview
costs nothing.

Idempotent: it compares both sides every run and copies only what is absent, so
it is safe to re-run after an interrupted transfer.  Comparison is
case-insensitive, because the library contains at least one map whose file is
capitalised (Bhop_Mukiology) and the Pi's filesystem is case-sensitive while
Windows' is not.
"""

import argparse
import os
import re
import shlex
import subprocess
import sys

MOMENTUM = r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum\maps"
PI_HOST = "proto@192.168.1.102"
PI_MAPS = "/srv/nvme/ftesurf-server/game/momentum/maps"

# scp takes many sources per invocation; batching amortises the ssh handshake
# without building a command line long enough to hit the shell's limit.
BATCH = 25

# Leave this much free on the Pi no matter what.  /srv/nvme also holds surfd's
# database and five running lobbies; filling it does not just fail the copy.
HEADROOM_GB = 5.0


def sh(args, **kw):
    """Run a command, returning (rc, stdout). stderr is folded in: ssh writes
    host-key notices there and they are not failures."""
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, **kw)
    return p.returncode, p.stdout


def ssh_cmd(host, remote, timeout=60):
    rc, out = sh(["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
                  host, remote], timeout=timeout)
    if rc != 0:
        raise SystemExit("ssh failed (%d):\n%s" % (rc, out))
    return out


def local_inventory(mapsdir):
    """-> ({name: size}, {names with a zone file})"""
    bsps, zones = {}, set()
    for f in os.listdir(mapsdir):
        if f.lower().endswith(".bsp"):
            p = os.path.join(mapsdir, f)
            if os.path.isfile(p):
                bsps[f[:-4]] = os.path.getsize(p)
    zdir = os.path.join(mapsdir, "zones", "online")
    if os.path.isdir(zdir):
        zones = {f[:-5] for f in os.listdir(zdir) if f.lower().endswith(".json")}
    return bsps, zones


def remote_inventory(host, maps):
    """One ssh round trip for both lists, and the free space, so a preview is
    one handshake rather than three."""
    q = shlex.quote(maps)
    out = ssh_cmd(host,
                  "find %s -maxdepth 1 -name '*.bsp' -printf '%%f\\n' 2>/dev/null | sed 's/\\.bsp$//'; "
                  "echo '---ZONES---'; "
                  "ls %s/zones/online/*.json 2>/dev/null | xargs -r -n1 basename | sed 's/\\.json$//'; "
                  "echo '---FREE---'; "
                  "df -B1 --output=avail %s | tail -1" % (q, q, q))
    bsp_part, _, rest = out.partition("---ZONES---")
    zone_part, _, free_part = rest.partition("---FREE---")
    bsps = {l.strip() for l in bsp_part.splitlines() if l.strip()}
    zones = {l.strip() for l in zone_part.splitlines() if l.strip()}
    free = 0
    for l in free_part.splitlines():
        if l.strip().isdigit():
            free = int(l.strip())
    return bsps, zones, free


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--momentum", default=MOMENTUM, help="local Momentum maps dir")
    ap.add_argument("--host", default=PI_HOST)
    ap.add_argument("--maps", default=PI_MAPS, help="maps dir on the Pi")
    ap.add_argument("--zoned-only", action="store_true",
                    help="copy only maps that have a zone file, i.e. the ones "
                         "that can actually be timed (531 of 1312 here)")
    ap.add_argument("--only", metavar="FILE",
                    help="copy only the map names listed in this file, one per line")
    ap.add_argument("--go", action="store_true",
                    help="actually copy; without it this previews and exits")
    args = ap.parse_args()

    if not re.match(r"^([A-Za-z0-9_][A-Za-z0-9._-]*@)?[A-Za-z0-9_][A-Za-z0-9.-]*$", args.host):
        raise SystemExit("--host %r is not a plain user@host" % args.host)
    if not re.match(r"^/[A-Za-z0-9._/-]+$", args.maps):
        raise SystemExit("--maps %r is not a plain absolute path" % args.maps)
    if not os.path.isdir(args.momentum):
        raise SystemExit("local maps dir not found: %s" % args.momentum)

    bsps, zones = local_inventory(args.momentum)
    print("local : %d bsp, %d zone" % (len(bsps), len(zones)))
    rbsps, rzones, free = remote_inventory(args.host, args.maps)
    print("pi    : %d bsp, %d zone, %.1f GB free" % (len(rbsps), len(rzones), free / 2**30))

    want = set(bsps)
    if args.zoned_only:
        want &= zones
    if args.only:
        with open(args.only) as fh:
            want &= {l.strip() for l in fh if l.strip()}

    have = {b.lower() for b in rbsps}
    hz = {z.lower() for z in rzones}
    todo = sorted(m for m in want if m.lower() not in have)
    ztodo = sorted(m for m in want & zones if m.lower() not in hz)
    need = sum(bsps[m] for m in todo)

    print("\nto copy: %d bsp (%.2f GB), %d zone" % (len(todo), need / 2**30, len(ztodo)))
    if not todo and not ztodo:
        print("nothing to do -- the Pi already has everything selected.")
        return
    for m in todo[:15]:
        print("   %8.1f MB  %s" % (bsps[m] / 2**20, m))
    if len(todo) > 15:
        print("   ... and %d more" % (len(todo) - 15))

    after = (free - need) / 2**30
    print("\nfree after: %.1f GB (floor %.1f GB)" % (after, HEADROOM_GB))
    if after < HEADROOM_GB:
        raise SystemExit("REFUSED: that copy would leave %.1f GB, below the %.1f GB floor.\n"
                         "Free space on the Pi, or use --zoned-only." % (after, HEADROOM_GB))
    if not args.go:
        print("\npreview only -- pass --go to copy.")
        return

    # scp is run with the maps dir as cwd and relative filenames, so no Windows
    # path with a drive letter is ever handed to scp, whose argument parser
    # would read "C:" as a hostname.
    sent = 0
    for kind, names, sub, ext in (("bsp", todo, "", ".bsp"),
                                  ("zone", ztodo, "zones/online", ".json")):
        if not names:
            continue
        cwd = os.path.join(args.momentum, *([sub] if sub else []))
        dest = "%s:%s/%s" % (args.host, args.maps, sub) if sub else "%s:%s/" % (args.host, args.maps)
        if sub:
            ssh_cmd(args.host, "mkdir -p %s" % shlex.quote("%s/%s" % (args.maps, sub)))
        for i in range(0, len(names), BATCH):
            chunk = [n + ext for n in names[i:i + BATCH]]
            rc, out = sh(["scp", "-q", "-o", "ConnectTimeout=10",
                          "-o", "BatchMode=yes"] + chunk + [dest], cwd=cwd)
            if rc != 0:
                print("scp failed on %s batch %d:\n%s" % (kind, i // BATCH, out))
                raise SystemExit(1)
            sent += len(chunk)
            print("  %s %d/%d" % (kind, min(i + BATCH, len(names)), len(names)))

    rb, rz, free2 = remote_inventory(args.host, args.maps)
    print("\ndone: %d files sent. pi now %d bsp, %d zone, %.1f GB free"
          % (sent, len(rb), len(rz), free2 / 2**30))
    still = sorted(m for m in want if m.lower() not in {b.lower() for b in rb})
    if still:
        print("STILL MISSING (%d): %s" % (len(still), ", ".join(still[:10])))


if __name__ == "__main__":
    main()
