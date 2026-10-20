"""Name the functions in crashaddr.txt records (written beside the exe by sys_win.c's crash logger).

  python tools/crashmap.py <unstripped exe or .db> [crashaddr.txt] [-n N] [--check <exe that crashed>]

The records carry no exe identity, so map them with the symbols of the build that wrote them, or of
a rebuild of its stamped commit: --check compares the first six bytes of every function in both and
says how many match (Patch 883: 12,369 of 12,691 against e1cf5c31, the rest RIP-relative loads of
shifted data).
Records are appended, newest last; -n reads the last N (default 4). A chain whose callers do not
call their callees was written by a different build."""
import argparse
import bisect
import re
import struct
import subprocess

NM = "C:/msys64/ucrt64/bin/nm.exe"
BASE = 0x140000000


def functions(db):
    out = subprocess.run([NM, "--defined-only", db], capture_output=True, text=True, check=True).stdout
    fn = []
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 3 and p[1] in "tT" and p[2] != ".text":
            fn.append((int(p[0], 16) - BASE, p[2]))
    return sorted(fn)


def reader(path):
    b = open(path, "rb").read()
    pe = struct.unpack_from("<I", b, 0x3c)[0]
    n = struct.unpack_from("<H", b, pe + 6)[0]
    s = pe + 24 + struct.unpack_from("<H", b, pe + 20)[0]
    secs = [struct.unpack_from("<IIII", b, s + 40 * i + 8) for i in range(n)]

    def at(rva, k):
        for vs, va, rs, ro in secs:
            if va <= rva < va + max(vs, rs):
                return b[ro + rva - va: ro + rva - va + k]
    return at


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("db")
    ap.add_argument("records", nargs="?", default="C:/FTESurf/crashaddr.txt")
    ap.add_argument("-n", type=int, default=4)
    ap.add_argument("--check")
    a = ap.parse_args()
    fn = functions(a.db)
    starts = [r for r, _ in fn]
    if a.check:
        x, y = reader(a.check), reader(a.db)
        same = sum(1 for r, _ in fn if x(r, 6) == y(r, 6))
        print("layout: %d of %d function starts identical" % (same, len(fn)))

    def name(rva):
        i = bisect.bisect_right(starts, rva) - 1
        return "?" if i < 0 or rva - starts[i] > 0x40000 else "%s+0x%x" % (fn[i][1], rva - starts[i])

    recs = [r for r in re.split(r"(?=^code=)", open(a.records, errors="replace").read(), flags=re.M)
            if r.startswith("code=")]
    print("%d records, showing the last %d" % (len(recs), min(a.n, len(recs))))
    for r in recs[-a.n:]:
        print("CRASH at", name(int(re.search(r"rva=0x([0-9a-f]+)", r).group(1), 16)), "--", r.splitlines()[0])
        for f in re.finditer(r"frame\[(\d+)\] rva=0x([0-9a-f]+)", r):
            v = int(f.group(2), 16)
            if v < 0x1000000:   # frames in system DLLs come out as huge module-relative values
                print("   #%s %s" % (f.group(1), name(v)))
        print()


if __name__ == "__main__":
    main()
