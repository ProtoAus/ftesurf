#!/usr/bin/env python3
"""Patch 840: a slow-motion client against a real dedicated socket.

    python tools/p840clock.py actor --out <dir>        # build the test actor csprogs
    python tools/p840clock.py run --out <dir> --progs <build dir> --csprogs <actor>
    python tools/p840clock.py run ... --control --arms slow   # pre-patch qwprogs

bhop_eazy with cfg/test/p840.zones.json: a smaller start box and an END 80 u past it,
both on the start platform (the map teleports a body that walks on past x -200).
One client at a time walks out at cl_forwardspeed 70, stops between the zones,
stands ~5 s, walks into the END:

  honest  normal pace, its process SUSPENDED --stall s while it stands (a hitch)
  slow    the actor's p840_slow 0.5 (usercmd msec halved) + cl_netfps 33.33 (half
          the packets), i.e. a slowed process clock, the shape of the 19 Oct lobby
          runs: one sample per tick, so reccheck's sample-rate fault stays quiet --
          and m_accel 1, so the profile verdict has something to name.
  retry   honest, with a `retry` (map restart, run kept) while it stands: the save's
          `clock` carries the sums across and the restart adds nothing
  partial the actor slowed only for the 5 s it stands: the steady rise catches it

THE ACTOR IS TEST-ONLY: the repo's client code plus a CSQC_Input_Frame scale, built
under --out and never shipped.  The server publishes it as its csprogs, so both
clients run it; only `slow` sets p840_slow.  It prints its own action.

Graded on the server's own recording (flags, inprof, prof, clk; reccheck) and on
`cmd timer`'s clock/tick lines.  The pre-existing `tick:` line (counted vs sampled)
is the independent witness that the slow run was slow.  RESULT 2026-10-20, bound 2,
the deploy candidate on main d077d30f (artifacts final-a/b/c in the P840 task root):
  honest   a 1.5 s client freeze: behind 0 (the stall credited 0.5 s), no bit; the same at
           --surftics
  slow     behind 4.42 s -> TF_SLOWCLOCK; inprof/prof m_accel; reccheck clean (as are the
           19 Oct lobby files)
  retry    behind 0; partial 2.32 s -> bit; rewind (TF_SEGMENT) 2.12 s -> bit
  pace     --surftics, half speed every ~90 ms: 4.39 s -> bit
Controls on earlier builds: pre-patch qwprogs -- no clk, no bit, flags 133124, unranked
only by TF_NOPROFILE, tick gap 356 (the lobby's 19 Oct outcome); review round 2's build --
a rewind's go zeroed the measure; round 3's -- a client pacing at sv_maxtic 0.1 went
unmeasured.
Needs the rig lock (C:/FTESurf-worktrees/rig.lock) and an announcement to peers.
"""
import argparse
import ctypes
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from spec_chat_smoke import Peer  # noqa: E402

CONTENT = Path("C:/FTESurf")
MAP = "bhop_eazy"
LOCK = Path(r"C:\FTESurf-worktrees\rig.lock")
TF_NOPROFILE, TF_SLOWCLOCK = 2048, 524288
SURFTICS = False
ACTOR_HOOK = """float p840_said;
void() CSQC_Input_Frame =
{
	// P840 TEST ACTOR ONLY: a slow-motion client, never shipped.
	if (cvar("p840_slow") > 0)
	{
		input_timelength = input_timelength * cvar("p840_slow");
		if (!p840_said)
			print(sprintf("p840 actor: usercmd time x %g\\n", cvar("p840_slow")));
		p840_said = TRUE;
	}
"""


def owned(out):
    if not any((p / "OWNER.md").is_file() for p in out.resolve().parents):
        raise SystemExit("--out must be beneath an owned task root (OWNER.md)")


def build_actor(out):
    owned(out)
    shutil.copytree(ROOT / "src", out / "src", ignore=shutil.ignore_patterns("*.dat", "*.lno"))
    (out / "ftesurf").mkdir()
    p = out / "src/client/cl_main.qc"
    s = p.read_bytes().decode("utf-8")
    old = "void() CSQC_Input_Frame =\n{\n"
    assert s.count(old) == 1
    p.write_bytes(s.replace(old, ACTOR_HOOK).encode("utf-8"))
    r = subprocess.run([str(ROOT / "src/fteqcc64.exe"), "-srcfile", "cl_progs.src"],
                       cwd=out / "src", capture_output=True, text=True)
    (out / "build.log").write_text(r.stdout + r.stderr)
    warn = [l for l in (r.stdout + r.stderr).splitlines()
            if "warning" in l.lower() and "0 warnings" not in l]
    print("fteqcc exit %d, warning lines %d -> %s" % (r.returncode, len(warn), out / "ftesurf/csprogs.dat"))
    return r.returncode or len(warn)


def free_mb():
    out = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                          "$o=Get-CimInstance Win32_OperatingSystem;"
                          "\"$($o.FreePhysicalMemory) $($o.FreeVirtualMemory)\""],
                         capture_output=True, text=True).stdout.split()
    return int(out[0]) // 1024, int(out[1]) // 1024


def take_lock(what):
    """Quiet first (no game process for 20 s), then the lock; never wait holding it."""
    quiet = None
    for _ in range(600):
        busy = subprocess.run(["tasklist"], capture_output=True, text=True).stdout
        if re.search(r"(?im)^(ftesurf64|fteqw64|fteqwsv64)\.exe", busy) or LOCK.exists():
            quiet = None
        elif quiet is None:
            quiet = time.monotonic()
        elif time.monotonic() - quiet >= 20:
            try:
                LOCK.mkdir()
            except FileExistsError:
                quiet = None
                continue
            (LOCK / "owner.txt").write_text("p840clock pid=%d since=%s for=%s\n" % (
                os.getpid(), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), what))
            return
        time.sleep(2)
    raise SystemExit("rig lock / quiet machine not reached in 20 min")


def drop_lock():
    (LOCK / "owner.txt").unlink()
    LOCK.rmdir()


def suspend(pid, on):
    h = ctypes.windll.kernel32.OpenProcess(0x0800, False, pid)      # PROCESS_SUSPEND_RESUME
    st = (ctypes.windll.ntdll.NtSuspendProcess if on else ctypes.windll.ntdll.NtResumeProcess)(h)
    ctypes.windll.kernel32.CloseHandle(h)
    return st


def prepare(out, name, progs, csprogs):
    base = out / name
    game = base / "ftesurf"
    for folder in ("glsl", "scripts", "models", "particles"):
        if (CONTENT / "ftesurf" / folder).is_dir():
            shutil.copytree(CONTENT / "ftesurf" / folder, game / folder)
    for folder in ("fonts", "ui"):
        if (CONTENT / "ftesurf/gfx" / folder).is_dir():
            shutil.copytree(CONTENT / "ftesurf/gfx" / folder, game / "gfx" / folder)
    for folder in ("cfg", "maps/zones/local", "logs", "data", "downloads/csprogsvers"):
        (game / folder).mkdir(parents=True)
    (game / "data/consent.txt").write_text("version 4\n")
    shutil.copy2(CONTENT / f"ftesurf/maps/{MAP}.bsp", game / f"maps/{MAP}.bsp")
    shutil.copy2(ROOT / "ftesurf/cfg/test/p840.zones.json", game / f"maps/zones/local/{MAP}.json")
    shutil.copy2(progs / "qwprogs.dat", game / "qwprogs.dat")
    shutil.copy2(progs / "menu.dat", game / "menu.dat")
    shutil.copy2(csprogs, game / "csprogs.dat")
    shutil.copy2(CONTENT / "ftesurf/cfg/default.cfg", game / "cfg/default.cfg")
    shutil.copy2(CONTENT / "fteplug_hl2_x64.dll", base / "fteplug_hl2_x64.dll")
    (base / "default.fmf").write_text(
        "FTEMANIFEST 1\nGAME FTESurfP840Fixture\nBASEGAME ftesurf\n"
        "DISABLEHOMEDIR 1\nMAINCONFIG p840-unused\n"
        + ("set sv_mintic 0\nset sv_maxtic 0.1\n" if SURFTICS else "set sv_mintic 0.015\nset sv_maxtic 0.015\n")
        + "set cl_netfps 66.6667\n")
    subprocess.run([sys.executable, str(ROOT / "tools/seed_csprogs.py"), str(game / "csprogs.dat")],
                   check=True, capture_output=True)
    return base


def recs(sv_base):
    return set(glob.glob(str(sv_base / "ftesurf/data/runs" / MAP / "*" / "*.rec")))


def last(pattern, text):
    found = re.findall(pattern, text)
    return found[-1] if found else None


def one_arm(a, sv_base, arm, common):
    base = prepare(a.out, arm, a.progs, a.csprogs)
    extra = ["set cl_forwardspeed 70", "set run_prestrafe 0"]
    extra += (["set p840_slow 0.5", "set m_accel 1", "set cl_netfps 33.3333"] if arm == "slow"
              else ["set p840_slow 0.5", "set cl_netfps 11", "set m_accel 0"] if arm == "pace"
              else ["set m_accel 0"])
    (base / "ftesurf/probe.cfg").write_text("\n".join(common + [
        "cl_threadedphysics 0", f'name "p840{arm}"', f"connect 127.0.0.1:{a.port}"]) + "\n")
    cl = Peer(CONTENT / "ftesurf64.exe", base, "probe.cfg")
    try:
        cl.wait("FTESurf CSQC loaded", timeout=120)
        time.sleep(3)
        cl.send("menu_restart; ui_close")
        time.sleep(1)
        for line in extra:          # after the map: Net_MatchTicrate pins cl_netfps at load
            cl.send(line)
        time.sleep(1)
        before = recs(sv_base)
        cl.send("cmd zone_goto 0")
        time.sleep(2)
        off = len(cl.text())

        def xpos():
            return float(cl.query("cmd viewpos", r"setpos ([-\d.]+) [-\d.]+ [-\d.]+", 10).group(1))

        # The start box's +x face is x -352 and the END begins at -272; at 70 u/s
        # the stop after the release takes ~10 u.
        cl.send("+forward")
        t0 = time.monotonic()
        left = None
        while time.monotonic() - t0 < 40:
            x = xpos()
            if x > -345:
                cl.send("-forward")
                left = x
                break
            time.sleep(0.1)
        time.sleep(1.0)
        stop_x = xpos()
        time.sleep(2.0)
        if arm == "honest":
            suspend(cl.proc.pid, True)
            time.sleep(a.stall)
            suspend(cl.proc.pid, False)
        if arm in ("partial", "rewind"):    # slow only while standing: ~2.5 s of game behind
            for line in ("set p840_slow 0.5", "set cl_netfps 33.3333"):
                cl.send(line)
            time.sleep(5.0)
            for line in ("set p840_slow 0", "set cl_netfps 66.6667"):
                cl.send(line)
        if arm == "rewind":             # a timed rewind's go: the ring must carry the measure
            for line in ("set hud_trail 1", "set rec_savelock 1", "rewind"):
                cl.send(line)
            time.sleep(0.4)
            cl.send("rewind")           # the first asks: "again to rewind -- ... segmented"
            time.sleep(0.5)
            cl.send("rewind seek -0.6")
            time.sleep(0.3)
            cl.send("rewind key 13")
            time.sleep(0.2)
            cl.send("rewind key 13 up")
            time.sleep(2.0)
        if arm == "retry":              # a map restart under a live run, the run kept
            mark = len(cl.text())
            cl.send("cmd rec_retry")    # cl_main.qc's `retry` sends this; the bare console
                                        # word reaches the engine's reconnect first
            cl.wait("FTESurf CSQC loaded", mark, timeout=120)
            time.sleep(3)
            for line in extra:
                cl.send(line)
        time.sleep(1.5)
        cl.query("cmd timer", r"rec plane", timeout=20)       # mid-run: the live clock line
        time.sleep(2.0)
        mid = cl.text()[off:]
        cl.send("+forward")
        new = set()
        while time.monotonic() - t0 < 90 and not new:
            new = recs(sv_base) - before
            time.sleep(0.05)
        cl.send("-forward")
        time.sleep(1.5)
        cl.query("cmd timer", r"rec plane", timeout=20)
        time.sleep(0.5)
        after = cl.text()[off:]
        r = {"left_x": left, "stop_x": stop_x, "recs": sorted(new),
             "actor_line": bool(re.search(r"p840 actor: usercmd time x 0\.5", cl.text())),
             "mid_state": last(r"\^5timer\^7: [^\n]*", mid),
             "mid_clock": last(r"clock: wall[^\n]*", mid),
             "mid_tick": last(r"tick: [^\n]*", mid),
             "clock": last(r"clock: wall[^\n]*", after),
             "tick": last(r"tick: [^\n]*", after),
             "inprof": last(r"inprof:  key[^\n]*", after)}
        if new:
            rec = sorted(new)[-1]
            shutil.copy2(rec, a.out / f"{arm}.rec")
            lines = Path(rec).read_text(encoding="utf-8", errors="replace").splitlines()
            r["flags"] = next((int(float(l.split()[1])) for l in lines if l.startswith("flags ")), None)
            r["head_inprof"] = next((l for l in lines if l.startswith("inprof ")), None)
            r["prof"] = [l for l in lines if l.startswith("prof ")]
            r["clk"] = [l for l in lines if l.startswith("clk ")]
            rc = subprocess.run([sys.executable, str(HERE / "reccheck.py"), "-v", rec],
                                capture_output=True, text=True)
            r["reccheck_ok"] = rc.returncode == 0
            (a.out / f"{arm}.reccheck.txt").write_text(rc.stdout)
        return r
    finally:
        cl.stop()


def run(a):
    owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", a.port))
    common = ["cfg_save_auto 0", "con_savehistory 0", "log_enable 1", "log_dir logs",
              "log_name probe", "log_readable 1", "set cl_idlefps 0", "set cl_maxfps 100",
              "set run_resume 0", 'set lobby_dir ""', 'set lobby_master ""',
              "set cl_run_upload 0", 'set cl_board_url ""', "set sv_public 0"]
    phys, commit = free_mb()
    print("free physical %d MB, commit %d MB" % (phys, commit), flush=True)
    if phys < 1500 or commit < 2200:
        raise SystemExit("not enough free memory for a server and a client")
    def sha(path):
        import hashlib
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    report = {"control": a.control, "arms": {}, "checks": [], "bound": a.bound,
              "qwprogs": sha(a.progs / "qwprogs.dat"), "csprogs": sha(a.csprogs),
              "client": sha(CONTENT / "ftesurf64.exe"),
              "server": sha(Path("C:/FTEQuake/fteqwsv64.exe"))}
    print("hashes", {k: report[k] for k in ("qwprogs", "csprogs", "client", "server")}, flush=True)
    take_lock("p840clock " + ("control" if a.control else "subject"))
    sv = None
    try:
        sv_base = prepare(a.out, "server", a.progs, a.csprogs)
        (sv_base / "ftesurf/probe.cfg").write_text("\n".join(common + [
            f"sv_port {a.port}", "sv_playerslots 2", "sv_maxclients 2", "set sv_gamemode surf",
            f"set run_slowclock {a.bound}",
            "developer 1", "log_developer 1", f"map {MAP}"]) + "\n")
        sv = Peer(Path(r"C:\FTEQuake\fteqwsv64.exe"), sv_base, "probe.cfg", True)
        sv.wait(r"Server spawned\.", timeout=90)
        for arm in a.arms.split(","):
            report["arms"][arm] = one_arm(a, sv_base, arm, common)
            print(arm, json.dumps(report["arms"][arm], indent=1), flush=True)
            time.sleep(2)
    finally:
        if sv is not None:
            sv.stop()
        drop_lock()

    def check(ok, name):
        report["checks"].append([name, bool(ok)])
        print(("PASS " if ok else "FAIL ") + name, flush=True)

    H, S = report["arms"].get("honest"), report["arms"].get("slow")
    if S:
        check(S["recs"], "slow: the run finished")
        check(S["actor_line"], "slow: the actor printed its own action")
        g = re.search(r"gap (-?\d+)", S["tick"] or "")
        check(g and int(g.group(1)) > 100, "slow: the old tick report sees the gap (%s)" % (g and g.group(1)))
        check(S.get("reccheck_ok"), "slow: reccheck passes the file (one sample per tick)")
    P = report["arms"].get("pace")
    if P:                               # half speed paced at ~90 ms: past the excuse only with the fix
        check(P["recs"], "pace: the run finished")
        check((P.get("flags") or 0) & TF_SLOWCLOCK if not a.control
              else not (P.get("flags") or 0) & TF_SLOWCLOCK,
              ("pace: a client pacing the server's frames is still TF_SLOWCLOCK (clk %s)" if not a.control
               else "control: a client pacing the server's frames goes unmeasured (clk %s)")
              % (P.get("clk"),))
    for name, R in (("retry", report["arms"].get("retry")), ("partial", report["arms"].get("partial")),
                    ("rewind", report["arms"].get("rewind"))):
        if R and a.control and name == "rewind":
            check(R["recs"] and R["flags"] & 128 and not R["flags"] & TF_SLOWCLOCK,
                  "control: a rewind's go wiped the measure (flags %s, clk %s)"
                  % (R.get("flags"), R.get("clk")))
        if not R or a.control:
            continue
        check(R["recs"], name + ": the run finished")
        m = re.search(r"clock: wall (-?[\d.]+) debt (-?[\d.]+) behind (-?[\d.]+)", R["mid_clock"] or "")
        check(m and float(m.group(1)) > 0 and abs(float(m.group(2))) < 3,
              name + ": the live clock line after the gesture is sane (%r)" % ((m and m.groups()),))
        check(R.get("reccheck_ok"), name + ": reccheck passes the file")
        clkv = [float(x) for x in R["clk"][0].split()[1:]] if R.get("clk") else None
        if name == "retry":
            check(clkv and clkv[7] < 0.5 and not R["flags"] & TF_SLOWCLOCK,
                  "retry: a retried honest run is not TF_SLOWCLOCK (clk %s)" % (R.get("clk"),))
        else:
            check(clkv and clkv[7] >= 1 and R["flags"] & TF_SLOWCLOCK,
                  name + ": slow only while standing is TF_SLOWCLOCK (clk %s)"
                  % (R.get("clk"),))
            if name == "rewind":        # the gesture acted: a rewound run is segmented
                check(R.get("flags") is not None and R["flags"] & 128,
                      "rewind: the run was rewound (TF_SEGMENT, flags %s)" % R.get("flags"))
    if a.control:
        if S:
            check(not S.get("clk") and not (S.get("flags", 0) & TF_SLOWCLOCK),
                  "control: the pre-patch server writes no clk and no TF_SLOWCLOCK")
    else:
        if H:
            check(H["recs"], "honest: the run finished")
            check(H.get("flags") is not None and not H["flags"] & TF_SLOWCLOCK,
                  "honest: a 1.5 s hitch is not TF_SLOWCLOCK")
            check(H.get("clk"), "honest: the finish wrote clk")
            check(H.get("reccheck_ok"), "honest: reccheck passes the file")
        if S:
            check(S.get("flags") is not None and S["flags"] & TF_SLOWCLOCK, "slow: TF_SLOWCLOCK set")
            check(S.get("flags") is not None and S["flags"] & TF_NOPROFILE, "slow: TF_NOPROFILE set")
            check((S.get("head_inprof") or "").startswith("inprof m_accel"), "slow: header inprof m_accel")
            check(S.get("prof") == ["prof m_accel"], "slow: finish prof m_accel")
    (a.out / "report.json").write_text(json.dumps(report, indent=1))
    return 1 if any(not ok for _n, ok in report["checks"]) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ac = sub.add_parser("actor")
    ac.add_argument("--out", type=Path, required=True)
    rn = sub.add_parser("run")
    rn.add_argument("--out", type=Path, required=True)
    rn.add_argument("--progs", type=Path, required=True)
    rn.add_argument("--csprogs", type=Path, required=True)
    rn.add_argument("--control", action="store_true")
    rn.add_argument("--port", type=int, default=27617)
    rn.add_argument("--stall", type=float, default=1.5)
    rn.add_argument("--arms", default="honest,slow")
    rn.add_argument("--bound", type=float, default=2.0)   # the lobby default is 5
    rn.add_argument("--surftics", action="store_true",      # a surf lobby's sv_mintic 0 / sv_maxtic 0.1
                    help="world ticks as a surf lobby: the server sleeps until a packet or 0.1 s")
    a = ap.parse_args()
    a.out = a.out.resolve()
    global SURFTICS
    SURFTICS = getattr(a, "surftics", False)
    return build_actor(a.out) if a.cmd == "actor" else run(a)


if __name__ == "__main__":
    sys.exit(main())
