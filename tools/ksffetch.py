#!/usr/bin/env python3
"""
ksffetch.py -- fetch the surf maps KSF has and this install does not, from KSF's
own public Drive, and put the BSP where the rest of the toolchain expects it.

WHY THIS EXISTS.  `tools/maproster.py` works out which maps are missing and which
KSF archive holds each one; it does not download anything.  This is the other
half, kept separate because one is a read and the other writes into a Steam
install.  Measured 2026-09-28: of KSF's 929-map roster, 894 were already on disk
and 31 were genuinely absent, every one of them present in the Drive.

NO CREDENTIAL IS ON THIS PATH.  Both KSF folders and the roster sheet answer an
anonymous GET.  There is no API key, no OAuth and no token here, and there should
never be one -- if the Drive ever stops answering anonymously, this tool should
say so and stop, not start authenticating as somebody.

WHERE THE BSP GOES, and it is not arbitrary.  The Momentum install's `maps/`,
because `tools/mapsync.py` mirrors FROM there to the Pi and `fs_addons.txt`
mounts it first.  Dropping them anywhere else gets a map you can play locally and
cannot host.  These 31 exist in neither install, so nothing is shadowed -- and
that is checked per file rather than assumed, because a name collision here would
silently replace the build the engine loads.

WHAT THE ARCHIVES CONTAIN.  One bare `.bsp`, flat, no directory structure --
checked on surf_004_fix.rar (16,221,912 bytes from 5,317,211 compressed).  They
are RAR5, so Python's stdlib cannot read them and 7-Zip does the extracting.
Anything in an archive that is NOT a .bsp is left alone and reported, because a
map that needs its own materials is a different job from a map that does not.

THE DRIVE'S LARGE-FILE INTERSTITIAL is the one trap.  Under about 100 MB the
download URL returns the bytes; over it, Google returns an HTML scan warning and
the real file needs the form's own parameters replayed.  A fetcher that does not
handle it writes an HTML page to disk named `surf_x.rar` and reports success, so
every download is checked for the RAR magic before it is believed.
"""

import argparse
import http.cookiejar
import io
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(HERE, "ftesurf")
DATA = os.path.join(GAME, "data")
ROSTERFILE = os.path.join(DATA, "maproster.txt")
KSFDRIVE = os.path.join(DATA, "ksf_drive.txt")

STEAM = r"C:\Program Files (x86)\Steam\steamapps\common"
DEST = os.path.join(STEAM, "Momentum Mod Playtest", "momentum", "maps")
CSS = os.path.join(STEAM, "Counter-Strike Source", "cstrike", "maps")
STAGE = os.path.join(DATA, "ksf_incoming")

SEVENZIP = r"C:\Program Files\7-Zip\7z.exe"
UA = "FTESurf-ksffetch/1.0 (+local surf map mirror)"
DELAY = 0.5                      # between files; they are somebody else's bytes
RAR_MAGIC = (b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00")
ZIP_MAGIC = b"PK\x03\x04"


def read_wanted():
    """-> [(map, archive)] for every roster row that names a KSF archive."""
    out = []
    for ln in io.open(ROSTERFILE, encoding="utf-8", errors="replace"):
        if not ln.startswith("roster "):
            continue
        f = ln.split()
        if len(f) >= 10 and f[9] != "-":
            out.append((f[1], f[9]))
    return out


def read_ids():
    ids = {}
    for ln in io.open(KSFDRIVE, encoding="utf-8", errors="replace"):
        if ln.startswith("#"):
            continue
        p = ln.rstrip("\n").split("\t")
        if len(p) >= 2:
            ids[p[0].strip()] = p[1].strip()
    return ids


CHUNK = 1 << 20


def _stream(resp, dest):
    """Copy a response to disk a megabyte at a time, returning its first bytes.

    STREAMED RATHER THAN BUFFERED ON PURPOSE.  These maps reach 335 MB
    uncompressed (surf_expel) and 216 MB (surf_crank); reading a run of them
    into memory with .read() is hundreds of megabytes of resident buffer for no
    reason, and the first version of this tool did exactly that."""
    head = b""
    with open(dest, "wb") as fh:
        while True:
            b = resp.read(CHUNK)
            if not b:
                break
            if len(head) < 16:
                head += b[:16]
            fh.write(b)
    return head


def drive_get(opener, fid, dest, timeout=300):
    """Download a public Drive file to `dest`, following the large-file
    interstitial.  -> the file's first bytes, for the magic check."""
    url = "https://drive.google.com/uc?export=download&id=" + fid
    head = _stream(opener.open(url, timeout=timeout), dest)
    if head.lstrip()[:5].lower() != b"<html":
        return head
    # An interstitial is small, so reading this one into memory is fine.
    with open(dest, "rb") as fh:
        body = fh.read(65536)
    m = re.search(rb'action="([^"]+)"', body)
    fields = dict(re.findall(rb'name="([^"]+)"\s+value="([^"]*)"', body))
    if not m:
        raise RuntimeError("interstitial with no form")
    act = m.group(1).decode().replace("&amp;", "&")
    q = urllib.parse.urlencode({k.decode(): v.decode() for k, v in fields.items()})
    return _stream(opener.open(act + ("&" if "?" in act else "?") + q,
                               timeout=timeout), dest)


def extract_bsp(archive, dest):
    """-> (installed, skipped_non_bsp).  7-Zip because these are RAR5."""
    if not os.path.exists(SEVENZIP):
        raise RuntimeError("7-Zip not found at %s" % SEVENZIP)
    listing = subprocess.run([SEVENZIP, "l", "-ba", archive],
                             capture_output=True, text=True)
    members = [ln.split()[-1] for ln in listing.stdout.splitlines() if ln.strip()]
    bsps = [m for m in members if m.lower().endswith(".bsp")]
    other = [m for m in members if not m.lower().endswith(".bsp")]
    done = []
    for b in bsps:
        base = os.path.basename(b)
        # A collision would silently replace the build the engine loads.
        if os.path.exists(os.path.join(dest, base)):
            print("      SKIP %s -- already present, not overwriting" % base)
            continue
        r = subprocess.run([SEVENZIP, "e", "-y", "-o" + dest, archive, b],
                           capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(os.path.join(dest, base)):
            print("      FAIL extracting %s: %s" % (base, r.stdout[-200:]))
            continue
        done.append(base)
    return done, other


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--go", action="store_true", help="actually write")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--keep", action="store_true", help="keep the .rar files")
    a = ap.parse_args()

    wanted = read_wanted()
    ids = read_ids()
    if a.limit:
        wanted = wanted[:a.limit]
    print("%d maps to fetch, dest %s" % (len(wanted), DEST))
    missing_id = [m for m, arc in wanted if arc not in ids]
    if missing_id:
        print("  no Drive id for: %s" % ", ".join(missing_id))
    if not a.go:
        for m, arc in wanted:
            print("  would fetch %-26s %s" % (m, arc))
        print("\n(dry run; pass --go)")
        return 0

    os.makedirs(STAGE, exist_ok=True)
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA)]

    got = failed = 0
    extras = {}
    for i, (mapname, arc) in enumerate(wanted, 1):
        fid = ids.get(arc)
        if not fid:
            failed += 1
            continue
        local = os.path.join(STAGE, arc)
        print("  [%2d/%d] %s" % (i, len(wanted), arc), flush=True)
        try:
            head = drive_get(op, fid, local + ".part")
        except Exception as e:
            print("      download failed: %s" % e)
            failed += 1
            continue
        # A page of HTML written as surf_x.rar would otherwise read as success.
        if not (head.startswith(RAR_MAGIC) or head.startswith(ZIP_MAGIC)):
            print("      NOT AN ARCHIVE (%d bytes, starts %r) -- skipped"
                  % (os.path.getsize(local + ".part"), head[:16]))
            os.remove(local + ".part")
            failed += 1
            continue
        os.replace(local + ".part", local)
        try:
            done, other = extract_bsp(local, DEST)
        except Exception as e:
            print("      extract failed: %s" % e)
            failed += 1
            continue
        for b in done:
            print("      -> %s (%.1f MB)"
                  % (b, os.path.getsize(os.path.join(DEST, b)) / 1048576.0))
            got += 1
        if other:
            extras[arc] = other
        if not a.keep:
            os.remove(local)
        time.sleep(DELAY)

    print("\ninstalled %d bsp, %d failed" % (got, failed))
    if extras:
        print("archives carrying more than a bare .bsp (left unextracted):")
        for arc, o in extras.items():
            print("  %-28s %s" % (arc, ", ".join(o[:6])))
    print("next: tools/maproster.py hash && tools/maproster.py build")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
