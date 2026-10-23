#!/usr/bin/env python3
"""Check surfd/story.txt and put it on the Pi as surfd's data/story.txt (Patch 854).

  python tools/story_push.py [--file surfd/story.txt] [--check] [--force] [--host proto@192.168.1.102]

The check is surfd's own parser (imported against a throwaway home), then every
map against the board's live map list (/api/board?maps=1, else the menu's
cached copy, said which): a map the Pi does not serve stops the push unless
--force (a typo looks exactly like that); no zones or disabled is only
reported, and so is a `via` whose spot the file never marks.  Without --check the file is copied over ssh (temp name, then rename)
and the live board is asked which revision it serves: the push is done only
when that is this file's sha256[:12].
"""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
REMOTE = "/srv/nvme/surfd/data/story.txt"


def promotion_command(stage, want, expected=None):
    """One guarded rename; never overwrite a catalogue changed since inspection."""
    if not re.fullmatch(r"[0-9a-f]{64}", want) or (expected is not None and
            not re.fullmatch(r"[0-9a-f]{64}", expected)):
        raise ValueError("expected a full SHA256")
    s, dst = shlex.quote(stage), shlex.quote(REMOTE)
    check = f'test "$(sha256sum -- {s} | cut -d " " -f1)" = {shlex.quote(want)}'
    cleanup = (f'if test -f {s}; then if {check}; then rm -- {s}; '
               'else echo "owned Story stage changed; retained" >&2; fi; fi')
    guard = ""
    if expected is not None:
        guard = (f'if test -L {dst} || ! test -f {dst} || '
                 f'test "$(sha256sum -- {dst} | cut -d " " -f1)" != {shlex.quote(expected)}; '
                 'then echo "Story predecessor changed; refusing promotion" >&2; exit 23; fi; ')
    return (f'set -e; trap {shlex.quote(cleanup)} EXIT; test ! -L {s}; {check}; '
            f'{guard}chmod 600 {s}; mv -f -- {s} {dst}; sha256sum -- {dst}')


def parse(text):
    home = tempfile.mkdtemp(prefix="story-push-")
    try:
        os.environ.update(SURFD_HOME=home, SURFD_ENV=os.path.join(home, "surfd.env"))
        sys.path[:0] = [str(ROOT / "surfd"), str(ROOT / "tools")]
        logging.disable(logging.CRITICAL)
        import surfd
        lists, problems = surfd.story_parse(text)
        return lists, problems, surfd.story_unspotted(lists)
    finally:
        logging.disable(logging.NOTSET)
        shutil.rmtree(home, ignore_errors=True)


def served(board):
    """({map: (zoned, enabled)}, where it came from), or (None, why).
    Row: dl <name> <mode> <src> <tier> <kb> <first> <new> <mtier> <ktier> <of> <zoned> <enabled>."""
    def rows(text):
        out = {}
        for ln in text.splitlines():
            w = ln.split()
            if len(w) == 13 and w[0] == "dl":
                out[w[1].lower()] = (w[11] == "1", w[12] == "1")
        return out
    try:
        with urllib.request.urlopen("%s/api/board?maps=1" % board, timeout=20) as r:
            got = rows(r.read().decode("utf-8", "replace"))
        if got:
            return got, "the board's live list"
    except OSError as exc:
        print("(live map list unavailable: %s)" % exc)
    for p in (ROOT / "ftesurf" / "data" / "mapdl.net.txt", Path("C:/FTESurf/ftesurf/data/mapdl.net.txt")):
        try:
            got = rows(p.read_text(encoding="utf-8", errors="replace"))
            if got:
                return got, "the menu's cached copy %s" % p
        except OSError:
            pass
    return None, "no map list"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=str(ROOT / "surfd" / "story.txt"))
    ap.add_argument("--check", action="store_true", help="check only, copy nothing")
    ap.add_argument("--force", action="store_true", help="push maps the Pi does not serve yet")
    ap.add_argument("--expected-live-sha256", help="refuse if the inspected live catalogue changed")
    ap.add_argument("--host", default="proto@192.168.1.102")
    ap.add_argument("--board", default="https://play.proto.bar")
    a = ap.parse_args()
    if a.expected_live_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", a.expected_live_sha256):
        ap.error("--expected-live-sha256 requires a full lowercase SHA256")

    data = Path(a.file).read_bytes()
    lists, problems, unspotted = parse(data.decode("utf-8", "replace"))
    for p in problems:
        print("PROBLEM", p)
    for lid, m, spot in unspotted:          # legal: shown "coming soon" until marked
        print("NO SPOT     %s  %s  via %s (add: spot %s <x> <y> <z> [radius])" % (lid, m, spot, spot))
    have, source = served(a.board)
    print("maps checked against %s" % source)
    unserved = 0
    for L in lists:
        n = soon = 0
        for c in L["chapters"]:
            for lv in c["levels"]:
                n += 1
                if not lv["map"]:
                    soon += 1
                    continue
                z = None if have is None else have.get(lv["map"])
                if have is not None and z is None:
                    print("NOT SERVED  %s  %s" % (L["id"], lv["map"]))
                    unserved += 1
                elif z is not None and not z[1]:
                    print("DISABLED    %s  %s" % (L["id"], lv["map"]))
                elif z is not None and not z[0]:
                    print("NO ZONES    %s  %s" % (L["id"], lv["map"]))
        print("%s: %d chapters, %d levels (%d coming soon)" % (L["id"], len(L["chapters"]), n, soon))
    if problems or not lists:
        sys.exit("not pushed: fix the problems above")
    if (unserved or have is None) and not a.force:
        sys.exit("not pushed: %s; check the names, or --force for maps on their way to the Pi"
                 % ("%d map(s) the Pi does not serve" % unserved if unserved else "no map list to check"))
    rev = hashlib.sha256(data).hexdigest()[:12]
    if a.check:
        print("checked, rev %s; not copied" % rev)
        return
    tmp = REMOTE + ".push-" + secrets.token_hex(8)
    subprocess.run(["scp", "-q", "-o", "BatchMode=yes", a.file, "%s:%s" % (a.host, tmp)], check=True)
    subprocess.run(["ssh", "-o", "BatchMode=yes", a.host,
                    promotion_command(tmp, hashlib.sha256(data).hexdigest(), a.expected_live_sha256)], check=True)
    for _ in range(20):
        try:
            with urllib.request.urlopen("%s/api/board?story=list" % a.board, timeout=10) as r:
                live = json.load(r).get("rev")
        except (OSError, ValueError) as exc:
            live = "(%s)" % exc
        if live == rev:
            print("live: the board serves rev %s" % rev)
            return
        time.sleep(3)
    sys.exit("copied, but the board still serves %s, not %s" % (live, rev))


if __name__ == "__main__":
    main()
