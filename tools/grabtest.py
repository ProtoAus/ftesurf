#!/usr/bin/env python3
"""Does mapgrab's one.sh install ONLY what hashes right?

Runs the real script against a scratch dir on the Pi with four cases whose
outcomes must differ.  A fetcher that installs on a bad hash is worse than no
fetcher, and an arm where every case succeeds proves nothing.
"""
import os
import subprocess
import sys

sys.path.insert(0, r"C:\FTESurf\tools")
import mapgrab                                            # noqa: E402

HOST = mapgrab.PI_HOST
DEST = "/tmp/grabtest/maps"
WORK = "/tmp/grabtest"
SC = os.path.dirname(os.path.abspath(__file__))

# bhop_landmark2: real url, and its real sha1 (verified by hand earlier).
URL = "https://cdn.momentum-mod.org/maps/94d3e6ba-5709-403c-a059-8c4ab03fb4f2.bsp"
GOOD = "293dd4223a351f6182de214764f012597b93eb79"
BAD = "0000000000000000000000000000000000000000"

CASES = [
    ("good_hash", GOOD, URL, "OK", True),
    ("bad_hash", BAD, URL, "HASHFAIL", False),
    ("dead_url", GOOD, "https://cdn.momentum-mod.org/maps/does-not-exist.bsp",
     "CURLFAIL", False),
    # written by the test before the run: must be left alone, not re-fetched
    ("already_here", BAD, URL, "SKIP", True),
]


def sh(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


one = os.path.join(SC, "one_test.sh")
with open(one, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(mapgrab.ONE_SH % {"dest": DEST})
man = os.path.join(SC, "man_test.txt")
with open(man, "w", encoding="utf-8", newline="\n") as fh:
    for n, h, u, _, _ in CASES:
        fh.write("%s %s %s\n" % (n, h, u))

rc, out = sh(["ssh", "-o", "BatchMode=yes", HOST,
              "rm -rf %s && mkdir -p %s && echo not-a-real-bsp > %s/already_here.bsp"
              % (WORK, DEST, DEST)])
if rc:
    sys.exit("setup failed: " + out)

for src, dst in ((one, "one.sh"), (man, "manifest.txt")):
    rc, out = sh(["scp", "-q", src, "%s:%s/%s" % (HOST, WORK, dst)])
    if rc:
        sys.exit("scp failed: " + out)

rc, out = sh(["ssh", "-o", "BatchMode=yes", HOST,
              "chmod +x %s/one.sh && xargs -n3 -P2 %s/one.sh < %s/manifest.txt"
              % (WORK, WORK, WORK)], timeout=300)
print("--- one.sh said ---")
print(out.strip())

rc, listing = sh(["ssh", "-o", "BatchMode=yes", HOST,
                  "ls -a %s" % DEST])
print("--- %s afterwards ---" % DEST)
print(listing.strip())

said = {}
for ln in out.splitlines():
    f = ln.split()
    if len(f) >= 2:
        said[f[1]] = f[0]

files = set(listing.split())
ok = True
print()
for n, h, u, want_verdict, want_file in CASES:
    got = said.get(n, "(nothing)")
    have = ("%s.bsp" % n) in files
    good = (got == want_verdict) and (have == want_file)
    ok &= good
    print("  %-14s verdict %-9s (want %-9s)  file %-5s (want %-5s)  %s"
          % (n, got, want_verdict, have, want_file, "ok" if good else "WRONG"))

# No .part may survive any case -- that is the Patch 465 failure shape.
leftovers = [f for f in files if ".part" in f]
print("  leftover .part files: %s" % (leftovers or "none"))
ok &= not leftovers

# The skipped file must be BYTE-IDENTICAL: a re-fetch that overwrote it would
# still report SKIP if the message came before the work.
rc, o = sh(["ssh", "-o", "BatchMode=yes", HOST,
            "cat %s/already_here.bsp" % DEST])
print("  already_here.bsp content: %r" % o.strip())
ok &= (o.strip() == "not-a-real-bsp")

sh(["ssh", "-o", "BatchMode=yes", HOST, "rm -rf %s" % WORK])
print()
print("GRABTEST: %s" % ("all four cases behaved differently and correctly"
                        if ok else "NOT as expected"))
sys.exit(0 if ok else 1)
