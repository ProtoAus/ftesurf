#!/usr/bin/env python3
"""Patch 1581: pm_verify names the prop models a lobby failed to load beside a state/physents HOLD.

Phase 1, the verifier: one windowed listen-server client on bhop_eazy (cfg/test/p1581skew.cfg) verifies
P349's b88fin.rec (S), its one-sample edit p349_samp.rec (N), and each with `propmiss 2 models/a.mdl
models/b.mdl` added to the header (SM, NM). Graded on the engine's VERIFY lines: N HOLDs on `state:`; NM
carries "may be content skew" and the two names; S, SM and N do not.
Phase 2, the lobby's detector (--progs with P1581's QC): a generated box map with three props whose model
files do not exist -- two solid with one model between them, one non-solid -- must report exactly one
missing model file (the solid one, counted once) on the server's `props:` line.
--control (an engine and progs before 1581): neither phase shows the text.
Run under the rig lock. Writes only under --out.
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from p808rewind import INSTALL, prepare, unjunction  # noqa: E402

MISS = "propmiss 2 models/a.mdl models/b.mdl"


def with_propmiss(src, dst):
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    at = next(i for i, l in enumerate(lines) if l.strip() == "begin")
    lines.insert(at, MISS + "\n")
    dst.write_text("".join(lines), encoding="utf-8")


def section(text, name):
    m = re.search(r"==== P1581 " + name + r" ====([\s\S]*?)(?===== P1581 |\Z)", text)
    return m.group(1) if m else ""


def verdict(sec):
    m = re.findall(r"VERIFY \S+ (PASS|HOLD|REFUSE)\s*(.*)", sec)
    return m[-1] if m else None


def detector(a, out):
    """Phase 2: the lobby's own count, from the props report a map load prints."""
    from p1576keys import prepare as box_prepare
    from p762keys import Client
    base = box_prepare(INSTALL, out / "detector")
    game = base / "ftesurf"
    for leaf in ("qwprogs.dat", "csprogs.dat", "menu.dat"):
        shutil.copy2(a.progs / leaf, game / leaf)
    world = (game / "maps/p1576box.map").read_text()
    props = "".join('{\n"classname" "prop_dynamic"\n"model" "%s"\n"solid" "%s"\n"origin" "%d 0 32"\n}\n'
                    % (m, sol, x) for m, sol, x in (("models/p1581/gone_a.mdl", "6", -200),
                                                     ("models/p1581/gone_a.mdl", "6", -100),
                                                     ("models/p1581/gone_b.mdl", "0", 100)))
    (game / "maps/p1576box.map").write_text(world + props)
    cl = Client(a.exe, base, "probe.cfg")
    try:
        time.sleep(14)
        text = cl.text()
    finally:
        cl.stop()
    line = next((l for l in text.splitlines() if "props:" in l), "")
    print("     subject: " + line.strip())
    return line


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--progs", type=pathlib.Path, default=INSTALL / "ftesurf")
    ap.add_argument("--control", action="store_true")
    a = ap.parse_args()
    a.exe, a.out = a.exe.resolve(), a.out.resolve()
    rig = a.out / time.strftime("p1581-%Y%m%dT%H%M%S")
    made = []
    try:
        gd, made = prepare(rig, a.progs, ["p1581skew"], 27561)
        data = gd / "data"
        data.mkdir(exist_ok=True)
        for name in ("b88fin.rec", "p349_samp.rec"):
            shutil.copyfile(INSTALL / "ftesurf/data" / name, data / name)
        with_propmiss(data / "b88fin.rec", data / "p1581_s.rec")
        with_propmiss(data / "p349_samp.rec", data / "p1581_n.rec")
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4
        cl = subprocess.Popen([str(a.exe), "-basedir", str(rig), "-manifest", str(rig / "default.fmf"), "-window",
                               "+exec", "cfg/test/p1581skew.cfg"], cwd=INSTALL, startupinfo=si,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            cl.wait(timeout=180)
        finally:
            if cl.poll() is None:
                cl.terminate()
                cl.wait(timeout=10)
    finally:
        unjunction(made)
    det = detector(a, rig)
    log = (rig / "ftesurf/logs/p1581skew.log")
    if not log.exists():
        print("FAIL no client log", log)
        return 1
    text = log.read_text(errors="replace")
    v = {k: verdict(section(text, k)) for k in ("S", "SM", "N", "NM")}
    for k in v:
        print("     subject %-2s %s" % (k, v[k]))
    faults = 0

    def check(ok, name):
        nonlocal faults
        faults += not ok
        print(("PASS " if ok else "FAIL ") + name, flush=True)

    skew = lambda x: x is not None and "may be content skew" in x[1]
    check(v["N"] is not None and v["N"][0] == "HOLD" and v["N"][1].startswith("state:"),
          "the one-sample edit HOLDs on state (the subject still discriminates)")
    check(v["S"] is not None and v["SM"] is not None and v["S"][0] == v["SM"][0] and not skew(v["S"]),
          "a propmiss header changes no verdict, and an unmarked file says nothing about skew")
    check(not skew(v["N"]), "the edit without propmiss: no skew text")
    if a.control:
        check(not skew(v["NM"]), "control (before 1581): no skew text anywhere")
        check("missing model file" not in det, "control (before 1581): no missing-model count")
    else:
        check(skew(v["NM"]) and "models/a.mdl models/b.mdl" in v["NM"][1] and "lacked 2" in v["NM"][1],
              "the edit with propmiss: HOLD names the two models as possible content skew")
        check("1 solid with a missing model file" in det and "gone_a.mdl" in det and "gone_b" not in det,
              "detector: one missing solid model file, counted once; the non-solid prop is not listed")
        check(v["SM"][0] != "HOLD" or v["SM"][1].startswith(("state:", "physents:")) == skew(v["SM"]),
              "skew text only on a state/physents HOLD")
    print("%d failed" % faults)
    return faults


if __name__ == "__main__":
    raise SystemExit(main())
