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

Idempotent: it compares both sides every run and copies what is absent OR a
different size, so it is safe to re-run after an interrupted transfer.
Comparison is case-insensitive, because the library contains at least one map
whose file is capitalised (Bhop_Mukiology) and the Pi's filesystem is
case-sensitive while Windows' is not.

WHY SIZE AND NOT JUST PRESENCE -- this was a live bug, measured 2026-09-14.
Until then this tool compared NAMES.  That makes it idempotent by presence, so
a map already on the Pi under the right name was never looked at again however
wrong its bytes were, and the Pi had maps predating this tool.  Result: 323 of
1312 BSPs on the server were a DIFFERENT BUILD from the one the client loads --
same name, different geometry.  surf_kitsune is the worked example: the Pi held
the CS:S build (4,418,529 bytes, md5 ab1a0012) while the client loads Momentum's
recompile (3,952,402, fbb9eb7c), and `pm_dettest` read mapcrc 9f259c44 against
the client's f7871fad, with the Patch 318 bevel census counting 1244 brushes on
one side and 1235 on the other.  A player on such a map is predicting against
different walls from the ones the server is sweeping, and QC build 73's TF_NOMAP
correctly demotes the run -- silently, on a quarter of the library.

So the comparison has to be over CONTENT, and size is the cheap proxy: it costs
one `find -printf` on each side and no reads.  It is a proxy, not a proof -- two
builds can coincide in length -- but a sample of 12 same-size pairs hashed
identical on both machines, and the real check is the one that matters anyway:
mapcrc agreement between a client and the server, which is what TF_NOMAP reports
per run.  Reach for hashes here only if a same-size pair is ever caught
differing; hashing 45 GB on a NanoPi is not free.
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
    """-> ({name: size}, {name: size} for maps with a zone file)"""
    bsps, zones = {}, {}
    for f in os.listdir(mapsdir):
        if f.lower().endswith(".bsp"):
            p = os.path.join(mapsdir, f)
            if os.path.isfile(p):
                bsps[f[:-4]] = os.path.getsize(p)
    zdir = os.path.join(mapsdir, "zones", "online")
    if os.path.isdir(zdir):
        for f in os.listdir(zdir):
            if f.lower().endswith(".json"):
                p = os.path.join(zdir, f)
                if os.path.isfile(p):
                    zones[f[:-5]] = os.path.getsize(p)
    return bsps, zones


def _sized(part):
    """'<size> <name>' lines -> {name: size}.  Split from the RIGHT is wrong
    here and rsplit is wrong too: sizes come first precisely because map names
    are the half that could contain a space."""
    out = {}
    for l in part.splitlines():
        l = l.strip()
        if not l:
            continue
        size, _, name = l.partition(" ")
        if size.isdigit() and name:
            out[name] = int(size)
    return out


def remote_inventory(host, maps):
    """One ssh round trip for both lists, and the free space, so a preview is
    one handshake rather than three.

    Returns SIZES, not just names -- see the --- drift note in the module
    docstring.  `find -printf` puts the size first so the name can be taken
    verbatim as the remainder of the line."""
    q = shlex.quote(maps)
    out = ssh_cmd(host,
                  "find %s -maxdepth 1 -name '*.bsp' -printf '%%s %%f\\n' 2>/dev/null | sed 's/\\.bsp$//'; "
                  "echo '---ZONES---'; "
                  "find %s/zones/online -maxdepth 1 -name '*.json' -printf '%%s %%f\\n' 2>/dev/null | sed 's/\\.json$//'; "
                  "echo '---FREE---'; "
                  "df -B1 --output=avail %s | tail -1" % (q, q, q))
    bsp_part, _, rest = out.partition("---ZONES---")
    zone_part, _, free_part = rest.partition("---FREE---")
    bsps = _sized(bsp_part)
    zones = _sized(zone_part)
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

    # Case-insensitive, because Bhop_Mukiology is capitalised and the Pi's
    # filesystem is case-sensitive while Windows' is not.
    have = {b.lower(): s for b, s in rbsps.items()}
    hz = {z.lower(): s for z, s in rzones.items()}

    missing = sorted(m for m in want if m.lower() not in have)
    stale = sorted(m for m in want
                   if m.lower() in have and have[m.lower()] != bsps[m])
    todo = sorted(missing + stale)
    zmissing = sorted(m for m in want & set(zones) if m.lower() not in hz)
    zstale = sorted(m for m in want & set(zones)
                    if m.lower() in hz and hz[m.lower()] != zones[m])
    ztodo = sorted(zmissing + zstale)
    need = sum(bsps[m] for m in todo)

    print("\nto copy: %d bsp (%.2f GB), %d zone" % (len(todo), need / 2**30, len(ztodo)))
    print("   bsp : %d absent, %d present but DIFFERENT SIZE" % (len(missing), len(stale)))
    print("   zone: %d absent, %d present but DIFFERENT SIZE" % (len(zmissing), len(zstale)))
    if not todo and not ztodo:
        print("nothing to do -- the Pi already has everything selected.")
        return
    for m in todo[:15]:
        tag = "replace" if m in stale else "new"
        print("   %8.1f MB  %-7s %s" % (bsps[m] / 2**20, tag, m))
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
    #
    # EVERY BATCH LANDS IN A STAGING DIR AND IS THEN `mv`d INTO PLACE, and that
    # is not tidiness.  Before the size comparison above this tool only ever
    # wrote files that were ABSENT, so it could not disturb a running server.
    # Now that it replaces files, it can overwrite a BSP a live lobby is in the
    # middle of loading -- a truncate-then-write under a reader.  A rename on
    # the same filesystem is atomic and leaves the old inode alive for anyone
    # still holding it, which is the same rule the plugin .so install follows.
    # The cost is one extra ssh per batch and `need` bytes of transient space.
    sent = 0
    stage = "%s/.incoming" % args.maps
    for kind, names, sub, ext in (("bsp", todo, "", ".bsp"),
                                  ("zone", ztodo, "zones/online", ".json")):
        if not names:
            continue
        cwd = os.path.join(args.momentum, *([sub] if sub else []))
        final = "%s/%s" % (args.maps, sub) if sub else args.maps
        ssh_cmd(args.host, "mkdir -p %s %s" % (shlex.quote(stage), shlex.quote(final)))
        for i in range(0, len(names), BATCH):
            chunk = [n + ext for n in names[i:i + BATCH]]
            rc, out = sh(["scp", "-q", "-o", "ConnectTimeout=10",
                          "-o", "BatchMode=yes"] + chunk + ["%s:%s/" % (args.host, stage)],
                         cwd=cwd)
            if rc != 0:
                print("scp failed on %s batch %d:\n%s" % (kind, i // BATCH, out))
                raise SystemExit(1)
            # mv -f rather than mv: the destination usually exists now.
            ssh_cmd(args.host, "mv -f %s/* %s/" % (shlex.quote(stage), shlex.quote(final)))
            sent += len(chunk)
            print("  %s %d/%d" % (kind, min(i + BATCH, len(names)), len(names)))
    ssh_cmd(args.host, "rmdir %s 2>/dev/null || true" % shlex.quote(stage))

    rb, rz, free2 = remote_inventory(args.host, args.maps)
    print("\ndone: %d files sent. pi now %d bsp, %d zone, %.1f GB free"
          % (sent, len(rb), len(rz), free2 / 2**30))
    still = sorted(m for m in want if m.lower() not in {b.lower() for b in rb})
    if still:
        print("STILL MISSING (%d): %s" % (len(still), ", ".join(still[:10])))


if __name__ == "__main__":
    main()
