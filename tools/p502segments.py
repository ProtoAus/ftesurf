#!/usr/bin/env python3
"""Patch 502: isolated rewind/save trail, replay and cold-load falsifiers.

python tools/p502segments.py [--dedicated] [--exe ftesurf64.exe]
The rig borrows content through junctions; writes/saves/logs are isolated.
It is retained for inspection, never recursively cleaned through junctions.
Only processes created by this driver are stopped. No owner fixtures are moved.
"""
import argparse
import json
import time
import pathlib
import re
import shutil
import socket
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent


def section(text, name):
    match = re.search(r"==== P502 " + re.escape(name) + r" ====([\s\S]*?)(?===== P502 |\Z)", text)
    return match.group(1) if match else ""


def samples(text):
    return [int(x) for x in re.findall(r"trail: run (\d+) samples", text)]


def timer_report(text):
    reports = re.split(r"timer: ", text)
    if len(reports) < 2:
        return None
    text = reports[-1]
    tick = re.search(r"tick: counted (\d+) sampled (\d+).*?frz (\d+)/([\d.]+)", text)
    clock = re.search(r"clock: want freeze (\d+), frozen (\d+) at ([\d.]+)s", text)
    recording = re.search(r"pb .*?practice (\d+)  recording (\d+)", text)
    if not (tick and clock and recording):
        return None
    return {"ticks": int(tick[1]), "frzticks": int(tick[3]),
            "frozen": int(clock[2]), "elapsed": float(clock[3]),
            "recording": int(recording[2]), "running": text.startswith("running on"),
            "segmented": "class: segmented" in text}


def pose(text):
    matches = re.findall(r"setpos ([\d.+-]+) ([\d.+-]+) ([\d.+-]+)", text)
    return list(map(float, matches[-1])) if matches else None


def near(a, b, tolerance=0.25):
    return a is not None and b is not None and sum((x-y)**2 for x, y in zip(a, b)) <= tolerance**2


def grade(gd):
    text = (gd / "logs/p502segments.log").read_text(encoding="utf-8", errors="replace")
    cold = (gd / "logs/p502cold.log").read_text(encoding="utf-8", errors="replace")
    faults = 0

    def check(name, passed, detail):
        nonlocal faults
        faults += not passed
        print(("PASS" if passed else "FAIL"), name, detail)

    a, b, _, d = [section(text, n) for n in ("A", "B", "C", "D")]
    c = text.split("==== P502 C ====", 1)[-1].split("==== P502 D ====", 1)[0]
    sa, sb, sc = samples(a), samples(b), samples(c)
    check("acted", len(sa) >= 2 and sa[0] > 20 and sa[-1] > sa[0], f"live samples {sa}")
    check("load-prefix", len(sb) >= 3 and 20 < sb[1] < sb[0] and sb[2] > sb[1], f"before/load/continue {sb}")
    check("load-class", "class: segmented" in b and "recording 1" in b, "timed, segmented and recording")
    check("rewind", "rewind: on 1" in c and "rewind: save 3" in c and len(sc) >= 2 and sc[0] > 20 and sc[-1] > sc[0], f"rewind/resume samples {sc}")
    released = timer_report(section(text, "C RELEASE"))
    advancing = timer_report(section(text, "C ADVANCE"))
    check("rewind-class", released and advancing and all(r["running"] and r["segmented"] and r["recording"] and not r["frozen"] for r in (released, advancing)) and advancing["ticks"] > released["ticks"], f"post-countdown reports {released}, {advancing}")
    check("replace-go", "the last resume point, makes way" in c and "save 3 (slot 003)" in c, "implicit timed row replaced; explicit save kept")
    check("eye", "camera height 64.00 chase 0" in c and "camera height 47.00 chase 0" in c, "sampled stand/duck eye heights, independent of pinned posture")
    board = re.findall(r"scores: (pinned\+held|pinned|held|closed)", d)
    check("board-bind", "scan 9 down 1 took 0" in d and "scan 9 down 0 took 0" in d and board[:2] == ["held", "closed"], f"TAB passes; actual edge states {board}")
    check("replay-replace", "replay: data/saves/surf_dune/save002/run.rec" in d and "replay: data/saves/surf_dune/save001/run.rec" in d, "two successful opens, without closing first")
    loaded = re.search(r"saveloc: event \d+ op 2 id (\d+) ack \d+ tag \d+", d)
    check("replay-save-load", "rewind: save 4" in d and "replay: nothing loaded" in d and loaded, "replay save; authoritative load event; viewer closed")
    forbidden = ("no loads mid-run", "save-lock waits", "close the replay or rewind first", "let go of the load key first", "cannot read", "nothing kept at that time")
    check("no-veto", not any(x in text + cold for x in forbidden), "no obsolete save/load/viewer veto")
    saves = gd / "data/p502-control"
    if not saves.exists():
        saves = gd / "data/saves/surf_dune"
    ids = {int(row): int(slot) for row, slot in re.findall(r"rewind: save (\d+) \(slot (\d+)\)", c + d)}
    goid, replayid = ids.get(3, 3), ids.get(4, 4)
    path = saves / f"save{replayid:03}/state.txt"
    replay_state = dict(line.split(" ", 1) for line in path.read_text().splitlines() if " " in line) if path.exists() else {}
    origin = list(map(float, replay_state.get("origin", "0 0 0").split()))
    check("replay-load-body", loaded and int(loaded[1]) == replayid and near(pose(d), origin) and "timer: idle" in d and "practice 1  recording 0" in d, f"authoritative practice body {pose(d)}, expected {origin}")
    for slot in (1, 2, goid):
        path = saves / f"save{slot:03}/state.txt"
        state = path.read_text(encoding="utf-8") if path.exists() else ""
        check(f"state-{slot}", "state 2\n" in state and "demoted" not in state and re.search(r"reclines [1-9]\d*", state), "authoritative timed prefix, not demoted placement")
        mark = re.search(r"^reclines (\d+)$", state, re.M)
        rec = saves / f"save{slot:03}/run.rec"
        rows = rec.read_text(encoding="utf-8").splitlines() if rec.exists() else []
        check(f"prefix-{slot}", mark is not None and len(rows) == int(mark.group(1)), f"saved line mark matches {len(rows)} prefix rows")
    path = saves / "save001/state.txt"
    state = path.read_text(encoding="utf-8") if path.exists() else ""
    velocity = re.search(r"^velocity (.*)$", state, re.M)
    speed = sum(float(x) ** 2 for x in velocity.group(1).split()) ** 0.5 if velocity else 0
    check("moving-save", speed > 10, f"saved speed {speed:.1f}")
    for slot in (1, 2, goid, replayid):
        path = saves / f"save{slot:03}/trail.txt"
        rows = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        check(f"persist-{slot}", len(rows) > 15 and all(len(s.split()) == 14 for s in rows[1:]), f"persisted raw visual samples {max(0, len(rows)-1)}")
    path = saves / f"save{replayid:03}/trail.txt"
    rows = path.read_text(encoding="utf-8").splitlines()[1:] if path.exists() else []
    endt = float(rows[-1].split()[0]) if rows else -1
    check("replay-prefix-cut", 0.3 < endt < 0.6, f"captured cursor prefix ends at {endt:.3f}, despite a later list ack")
    cc = section(cold, "COLD")
    ss = samples(cc)
    check("cold-timed", len(ss) >= 2 and ss[0] > 25 and ss[1] > ss[0] and "recording 1" in cc, f"new VM restored prefix and grew {ss}")
    pp = section(cold, "PRACTICE")
    ss = samples(pp)
    check("cold-practice", len(ss) >= 4 and ss[0] > 15 and ss[1] > ss[0] and 10 < ss[2] < ss[1] and ss[-1] > ss[2], f"replay-prefix/load/rewind/continue {ss}")
    check("countdown-save", "rewind: on 1 counting 1" in pp and "save 7 (slot 007)" in pp and "rewind: on 0 counting 0" in pp, "save during countdown; hold releases")
    print(f"{faults} failed")
    return bool(faults)


def grade_edges(gd):
    text = (gd / "logs/p502edges.log").read_text(errors="replace")
    faults = 0
    def check(name, ok, detail):
        nonlocal faults
        passed = bool(ok)
        print(("PASS" if passed else "FAIL"), name, detail)
        faults += not passed
    h1, h2, released, advancing = (timer_report(section(text, "EDGE " + x)) for x in ("HOLD1", "HOLD2", "RELEASE", "ADVANCE"))
    go = section(text, "EDGE GO")
    check("ack-save", "on 1 counting 1 sent 0" in go and "save " in go, "same-frame go/save reaches countdown and saves held body")
    check("timed-hold", h1 and h2 and all(r["running"] and r["segmented"] and r["recording"] and r["frozen"] for r in (h1, h2)) and h1["ticks"] > 0 and h1["ticks"] == h2["ticks"] and h1["elapsed"] == h2["elapsed"] and h2["frzticks"] > h1["frzticks"], f"nonzero held clocks {h1}, {h2}")
    check("timed-release", h2 and released and advancing and all(r["running"] and r["segmented"] and r["recording"] and not r["frozen"] for r in (released, advancing)) and advancing["ticks"] > released["ticks"] > h2["ticks"] and "on 0 counting 0 sent 0" in section(text, "EDGE RELEASE"), f"released clocks {released}, {advancing}")
    data = gd / "data/saves/surf_dune"
    overlap = re.findall(r"rewind: save \d+ \(slot (\d+)\)", section(text, "EDGE OVERLAP"))
    maxima = []
    for sid in overlap:
        p = data / f"save{int(sid):03d}/trail.txt"
        rows = p.read_text().splitlines()[1:] if p.exists() else []
        maxima.append(max((float(x.split()[0]) for x in rows), default=-1))
    check("overlap-prefix", len(maxima) == 2 and all(0 <= end - actual <= .03 for end, actual in zip((.2, .5), maxima)), f"two requested cutoffs .2/.5: persisted {maxima}")
    counts = samples(section(text, "EDGE MISSING"))
    check("missing-picture", len(counts) >= 2 and counts[-2] > 60 and counts[-1] < 60 and not (data / "save001/trail.txt").exists(), f"unrelated B samples {counts}; A's missing picture stays absent")
    ended = section(text, "EDGE ENDED")
    saved = re.search(r"rewind: save \d+ \(slot (\d+)\)", ended)
    cursor = re.search(r"rewind: at (\d+)", ended)
    p = data / f"save{int(saved[1]):03d}" if saved else data / "missing"
    rows = (p / "trail.txt").read_text().splitlines() if (p / "trail.txt").exists() else []
    last = max((float(x.split()[0]) for x in rows[1:]), default=-1)
    header = rows[0].split() if rows else []
    st = dict(x.split(" ", 1) for x in (p / "state.txt").read_text().splitlines() if " " in x) if (p / "state.txt").exists() else {}
    origin = list(map(float, st.get("origin", "0 0 0").split()))
    check("ended-prefix", cursor and len(header) == 5 and header[4] == "0" and 0 <= last <= int(cursor[1]) * .015 + .03 and near(pose(ended), origin), f"ended cursor {cursor[1] if cursor else None}, prefix max {last}, loaded body {pose(ended)}")
    vote = section(text, "EDGE VOTE")
    counts = re.findall(r"vote key: scan 49 down [01] took \d+ pick 1 capture \d+ saves (\d+)", vote)
    check("vote-priority", len(counts) == 2 and len(set(counts)) == 1 and "rewind: save" not in vote and "pick 1" in vote, f"vote down/up pick 1, save counts {counts}")
    board = re.findall(r"scores: (pinned\+held|pinned|held|closed)", section(text, "EDGE BOARD"))
    check("board-edges", board == ["held", "closed", "held", "closed"], f"down/up/repress/up board states {board}")
    warm_first = timer_report(section(text, "EDGE WARMSETUP"))
    warm = section(text, "EDGE WARM")
    report = timer_report(warm)
    resumed = re.search(r"run resumed at (\d+):([\d.]+)", warm)
    resumed_at = int(resumed[1]) * 60 + float(resumed[2]) if resumed else None
    check("warm-prefix-history", warm_first and warm_first["frozen"] and warm_first["recording"] and report and report["running"] and report["segmented"] and report["recording"] and resumed_at is not None and resumed_at + .5 < warm_first["elapsed"] and "nothing kept" not in warm, f"second authoritative cut {resumed_at}, first cut {warm_first['elapsed'] if warm_first else None}")
    order = section(text, "EDGE ORDER")
    positions = [list(map(float, x)) for x in re.findall(r"setpos ([\d.+-]+) ([\d.+-]+) ([\d.+-]+)", order)]
    sid = re.search(r"save \d+ \(slot (\d+)\)", order)
    p = data / f"save{int(sid[1]):03}/state.txt" if sid else data / "missing"
    st = dict(x.split(" ", 1) for x in p.read_text().splitlines() if " " in x) if p.exists() else {}
    origin = list(map(float, st.get("origin", "0 0 0").split()))
    check("save-load-order", len(positions) == 2 and near(positions[0], positions[1]) and near(positions[0], origin) and " op 2 id " in order, f"pre-save/loaded {positions}, new save {origin}")
    ordered = section(text, "EDGE SAVELOAD")
    ids = re.findall(r"rewind: save \d+ \(slot (\d+)\)", ordered)
    maxima = []
    for sid in ids:
        p = data / f"save{int(sid):03}/trail.txt"
        rows = p.read_text().splitlines()[1:] if p.exists() else []
        maxima.append(max((float(x.split()[0]) for x in rows), default=-1))
    check("save-save-load", len(maxima) == 2 and all(0 <= end - actual <= .03 for end, actual in zip((.2, .5), maxima)) and "replay: nothing loaded" in ordered and " op 2 id " in ordered and "lost its acknowledgement" not in text, f"ordered viewer saves retain both pictures {maxima}")
    warm_id = re.search(r"rewind: save \d+ \(slot (\d+)\)", warm)
    p = data / f"save{int(warm_id[1]):03}/state.txt" if warm_id else data / "missing"
    st = dict(x.split(" ", 1) for x in p.read_text().splitlines() if " " in x) if p.exists() else {}
    check("cold-keeps-other-go", float(st.get("ticks", 0)) > 0 and float(st.get("rewindgo", 0)) > 0 and (p.parent / "run.rec").exists(), "cold continuation/next go retains run A's earlier timed implicit row")
    for label in ("HOLDCTRL", "HOLDQUEUE"):
        one, two, released = (section(text, "EDGE " + label + x) for x in ("1", "2", "RELEASE"))
        r1, r2, r3 = (timer_report(x) for x in (one, two, released))
        check(label.lower(), r1 and r2 and r3 and r1["ticks"] > 0 and r1["ticks"] == r2["ticks"] and r1["frozen"] and r2["frozen"] and r1["recording"] and r2["recording"] and near(pose(one), pose(two)) and all("hold 1 holding 1" in x for x in (one, two)) and "hold 0 holding 0" in released and not r3["frozen"] and r3["ticks"] > r2["ticks"], f"low-FPS actual hold/frozen clocks {r1}, {r2}; release {r3}")
    control = gd / "data/p502-stale-picture-control.json"
    seeded = json.loads(control.read_text()) if control.exists() else {}
    off = section(text, "EDGE OFF")
    sid = re.search(r"rewind: save \d+ \(slot (\d+)\)", off)
    p = data / f"save{int(sid[1]):03}/trail.txt" if sid else data / "missing"
    check("display-reset-save", sid and seeded.get("id") == int(sid[1]) and seeded.get("bytes", 0) > 0 and not p.exists() and "save answer " in off and " op 2 id " in off and "replay: nothing loaded" in off, "ACTED stale practice picture seeded after server write; correlated client answer invalidates it")
    print(f"{faults} edge failures")
    return bool(faults)


def wait_edges(process, gd, timeout):
    """Seed a valid stale client picture after the private server write.

    The OFF arm drops to 1 client FPS, leaving a full frame for this mutation
    before its save answer is consumed. This models independent client files.
    """
    deadline = time.monotonic() + timeout
    before = None
    seeded = False
    log = gd / "logs/p502edges.log"
    saves = gd / "data/saves/surf_dune"
    while process.poll() is None:
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired(process.args, timeout)
        if log.exists():
            text = log.read_text(errors="replace")
            if before is None and "==== P502 EDGE OFF ====" in text:
                before = set(saves.glob("save*/state.txt"))
            if before is not None and not seeded:
                for state in set(saves.glob("save*/state.txt")) - before:
                    try:
                        body = state.read_text(errors="replace")
                    except (FileNotFoundError, PermissionError):
                        continue  # not yet a completed private server write
                    if "origin " not in body or "rewound 1" not in body or "demoted 1" not in body:
                        continue
                    picture = state.with_name("trail.txt")
                    payload = "FTESURF-TRAIL 1 0.015 -1 0\n0 1234 5678 9012 0 0 0 1\n0.015 1235 5678 9012 0 0 0 0\n"
                    picture.write_text(payload)
                    proof = {"id": int(state.parent.name[4:]), "bytes": picture.stat().st_size,
                             "seeded_utc": time.time(), "after_server_state": state.stat().st_mtime}
                    (gd / "data/p502-stale-picture-control.json").write_text(json.dumps(proof))
                    seeded = True
                    break
        time.sleep(.02)
    return process.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", default=str(ROOT / "ftesurf64.exe"))
    ap.add_argument("--dedicated", action="store_true")
    ap.add_argument("--stream", action="store_true", help="exercise streamed authoritative prefixes")
    ap.add_argument("--server", default="C:/FTEQuake/fteqwsv64.exe")
    ap.add_argument("--progs", type=pathlib.Path, default=ROOT / "ftesurf", help="compiled control/subject progs directory")
    ap.add_argument("--content", type=pathlib.Path, default=ROOT, help="installed content root for source-only worktrees")
    ap.add_argument("--port", type=int, default=27559)
    ap.add_argument("--grade-only", type=pathlib.Path, help="existing rig root")
    ap.add_argument("--output-dir", type=pathlib.Path, help="parent for retained private test artifacts")
    args = ap.parse_args()
    if args.grade_only:
        gd = args.grade_only / "ftesurf"
        result = grade(gd)
        if (gd / "logs/p502edges.log").exists():
            result |= grade_edges(gd)
        return result
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    rig = pathlib.Path(tempfile.mkdtemp(prefix="ftesurf-p502-", dir=args.output_dir))
    gd = rig / "ftesurf"
    gd.mkdir()
    shutil.copyfile(ROOT / "default.fmf", rig / "default.fmf")
    for name in ("maps", "gfx", "glsl", "models", "particles", "scripts"):
        subprocess.run(["cmd", "/c", "mklink", "/J", str(gd / name), str(args.content / "ftesurf" / name)], check=True, capture_output=True)
    for name in ("qwprogs.dat", "csprogs.dat", "menu.dat"):
        shutil.copyfile(args.progs / name, gd / name)
    shutil.copyfile(ROOT / "ftesurf/fs_addons.default.txt", gd / "fs_addons.default.txt")
    # Do not copy ignored local configs/credentials into a test artifact.
    cfgs = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "ftesurf/cfg"], text=True).splitlines()
    cfgs += ["ftesurf/cfg/test/p502segments.cfg", "ftesurf/cfg/test/p502cold.cfg", "ftesurf/cfg/test/p502edges.cfg"]
    for name in cfgs:
        src = ROOT / name
        if src.is_file():
            dst = rig / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    (gd / "downloads/csprogsvers").mkdir(parents=True)
    subprocess.run(["python", str(ROOT / "tools/seed_csprogs.py"), str(gd / "csprogs.dat")], check=True, capture_output=True)
    server = None
    common = ["-basedir", str(rig), "-manifest", str(rig / "default.fmf")]
    try:
        if args.dedicated:
            if not 27520 <= args.port <= 27620:
                raise ValueError("use a dedicated lobby-range test port")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(("127.0.0.1", args.port))
            server = subprocess.Popen([args.server, *common, "+sv_public", "0", "-port", str(args.port), "+log_enable", "1", "+log_name", "p502server", "+set", "rec_stream", str(int(args.stream)), "+map", "surf_dune"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = False
        for name in ("p502segments", "p502cold", "p502edges"):
            if name == "p502edges":
                result = grade(gd)
                shutil.copytree(gd / "data/saves/surf_dune", gd / "data/p502-control")
                picture = gd / "data/saves/surf_dune/save001/trail.txt"
                if picture.exists():
                    picture.rename(picture.with_name("trail.control.missing"))
            cfg = gd / f"cfg/test/{name}.cfg"
            text = cfg.read_text(encoding="utf-8")
            if args.dedicated:
                text = text.replace("map surf_dune\n", f"connect 127.0.0.1:{args.port}\n")
            else:
                text = text.replace("map surf_dune\n", f"set rec_stream {int(args.stream)}\nmap surf_dune\n")
            text = text.replace("cfg_save_auto 0\n", "cfg_save_auto 0\nname P502Control\n")
            cfg.write_text(text, encoding="utf-8")
            client = subprocess.Popen([args.exe, *common, "-window", "+exec", f"cfg/test/{name}.cfg"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                if name == "p502edges":
                    wait_edges(client, gd, 150)
                else:
                    client.wait(timeout=150)
            finally:
                if client.poll() is None:
                    client.terminate()
                    client.wait(timeout=10)
            if not (gd / f"logs/{name}.log").exists():
                raise RuntimeError(f"{name} did not produce its log")
        result |= grade_edges(gd)
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            server.wait(timeout=10)
        # Remove only our junctions, not their content or the retained logs/data.
        for name in ("maps", "gfx", "glsl", "models", "particles", "scripts"):
            path = gd / name
            if path.lstat().st_file_attributes & 0x400:
                path.rmdir()
            else:
                raise RuntimeError(f"expected a content junction: {path}")
        print("Retained isolated artifacts (content junctions removed):", rig)
        print("Generated identities/logs are private; review before sharing.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
