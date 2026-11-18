#!/usr/bin/env python3
"""P1616: the look and the knife follow the Steam account (Linux rig, headless clients).

Two dedicated servers on loopback sharing one gamedir (as the 12 lobbies do), a loopback mock of surfd's
social routes, two clients run one after the other with different local looks. A fixture-only server command (`look_fixture <who>`, compiled into a shadow
sv_player.qc, never deployed) binds a linked account through the real Social_Set, as tools/inventory_smoke.py
does: account proof is not under test.

  A  on lobby 1: local look -> bind (no account look) -> saved; change -> saved; change + map restart within
     the settle time -> flushed by SV_Shutdown; a change on the next map while unbound, another restart, bind:
     the change is kept and saved; a change and an immediate quit -> flushed at disconnect.
  B  on lobby 2, whose name cache predates the file: a different local look -> bind -> the account's look is
     applied (its own console line, its cvars), nothing saved back.
  knife: the mock must see /api/social/viewmodel get and set (P970 posted to `lobby_url`, set nowhere).

--control builds the same arm from a ref without P1616 (default origin/main): no look file, no knife post.
The client's poll runs from CSQC_UpdateView, which the headless renderer never calls: --nest runs each client
with GL in a hidden headless labwc (FTESurf-worktrees/wlfs-20261118-c5/artifacts/nest.py's recipe).

  python3 tools/p1616look.py --out <owned dir> [--nest] [--control [--ref REF]]
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT.parents[2] / "ftesurf" if (ROOT.parents[2] / "ftesurf").is_dir() else ROOT
sys.path.insert(0, str(ROOT / "tools"))
from test_ui_modern import make_map  # noqa: E402

WHO = "1a2b3c4d"
TOKEN = "a" * 64
LAST = "1,11,,255 0 255,,,,,,20,0.9,20,1"


def fixture_src(dst, ref):
    """src/ of the working tree, or of `ref`, with the fixture command in a shadow sv_player.qc."""
    if ref:
        dst.mkdir(parents=True)
        tar = subprocess.run(["git", "-C", str(ROOT), "archive", ref, "src", "VERSION"], check=True,
                             stdout=subprocess.PIPE).stdout
        subprocess.run(["tar", "-xf", "-", "-C", str(dst)], input=tar, check=True)
    else:
        shutil.copytree(ROOT / "src", dst / "src", ignore=shutil.ignore_patterns("*.dat", "*.lno"))
    player = dst / "src/server/sv_player.qc"
    text = player.read_text()
    marker = '\tif (!strcmp(c, "inventory_equip"))'
    hook = ('\tif (!strcmp(c, "look_fixture"))\n\t{\n\t\tself.acct_state = 2;\n'
            '\t\tSocial_Set(self, "%s", argv(1));\n\t\treturn;\n\t}\n' % TOKEN)
    if text.count(marker) != 1:
        raise RuntimeError("dispatch seam changed")
    player.write_text(text.replace(marker, hook + marker))
    return dst / "src"


def build(src, game, qcc):
    ver = (src.parent / "VERSION").read_text().strip() if (src.parent / "VERSION").exists() else "0"
    for name, extra in (("sv_progs", []), ("cl_progs", ["-Fomitarraydefs"]),
                        ("m_progs", ['-DUI_MENU_VERSION="%s"' % ver, "-DUI_MENU_DEVELOPMENT=1"])):
        lines = (src / (name + ".src")).read_text().splitlines()
        out = game / {"sv_progs": "qwprogs.dat", "cl_progs": "csprogs.dat", "m_progs": "menu.dat"}[name]
        lines[0] = os.path.relpath(out, src)
        (src / (name + "-rig.src")).write_text("\n".join(lines) + "\n")
        r = subprocess.run([str(qcc), "-max_strings", "4194304", "-srcfile", name + "-rig.src"] + extra,
                           cwd=src, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (game.parent / (name + "-compile.log")).write_text(r.stdout)
        if r.returncode or "Done. 0 warnings" not in r.stdout:
            raise RuntimeError("%s: compile failed or warned (see %s-compile.log)" % (name, name))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--nest", action="store_true")
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--qcc", type=Path, default=ROOT.parents[2] / "ftequakers/engine/release/fteqcc64")
    ap.add_argument("--client", type=Path, default=INSTALL / "ftesurf64")
    ap.add_argument("--server", type=Path, default=INSTALL / "fteqw-sv64")
    a = ap.parse_args()
    out = a.out.resolve()
    if not any((p / "OWNER.md").is_file() for p in out.parents):
        ap.error("--out must be inside an owned task root (OWNER.md)")
    if out.exists():
        ap.error("--out exists: inspect it, then pick a fresh one")
    rig = out / "rig"
    game = rig / "ftesurf"
    for d in ("cfg", "maps", "logs", "models", "home"):
        (game / d if d != "home" else rig / d).mkdir(parents=True)
    (game / "cfg/default.cfg").write_text("cfg_save_auto 0\n")
    (game / "maps/look_smoke.map").write_text(make_map())
    for folder in ("glsl", "scripts", "gfx/fonts"):
        if (INSTALL / "ftesurf" / folder).is_dir():
            shutil.copytree(INSTALL / "ftesurf" / folder, game / folder, dirs_exist_ok=True)
    for p in (INSTALL / "ftesurf/models").glob("player*"):
        if p.is_file():
            shutil.copy2(p, game / "models" / p.name)
    (rig / "default.fmf").write_text('FTEMANIFEST 1\nGAME LookRig\nNAME "Look rig"\nBASEGAME ftesurf\n'
                                     'DISABLEHOMEDIR 1\nMAINCONFIG lookrig-unused\n')
    build(fixture_src(out / "build", a.ref if a.control else None), game, a.qcc)

    ports = []
    for cand in range(27620, 27519, -1):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.bind(("127.0.0.1", cand))
            except OSError:
                continue
            ports.append(cand)
        if len(ports) == 2:
            break
    if len(ports) < 2:
        raise RuntimeError("no two free lobby ports")

    wire = {"viewmodel_get": 0, "viewmodel_set": 0, "polls": 0, "other": []}
    knife = {"rev": 0, "setup": ""}

    class Backend(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode(), keep_blank_values=True).items()}
            path = urlsplit(self.path).path
            reply = {"ok": 0}
            if path == "/api/social/poll":
                wire["polls"] += 1
                rows = json.loads(form.get("roster", "[]") or "[]")
                reply = {"ok": 1, "players": [{"token": r.get("token", ""), "hash": "", "messages": []}
                                              for r in rows], "invalid": []}
            elif path == "/api/social/viewmodel" and form.get("token") == TOKEN:
                if form.get("op") == "set" and int(form.get("revision", "-1")) == knife["rev"]:
                    knife["rev"] += 1
                    knife["setup"] = form.get("setup", "")
                    wire["viewmodel_set"] += 1
                else:
                    wire["viewmodel_get"] += 1
                reply = {"viewmodel": 1, "ok": 1, "revision": knife["rev"], "setup": knife["setup"]}
            else:
                wire["other"].append(path)
            body = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    backend = HTTPServer(("127.0.0.1", 0), Backend)
    url = "http://127.0.0.1:%d" % backend.server_port
    common = ["cfg_save_auto 0", "set log_enable 1", "set log_dir logs", "set log_readable 1",
              "set cl_idlefps 0", "set cl_maxfps 100", "set lobby_dir \"\"", "set cl_board_url \"\"",
              "set ui_serverbgm 0", "waitms 800", "ui_close"]
    show = ["cl_lobbycolor", "cl_lobbymark", "cl_lobbybody", "paint_size", "viewmodel_setup"]
    cfgs = {
        "clientA": ['seta cl_lobbycolor "5"', 'seta cl_lobbymark "255 0 255"', 'seta paint_size "20"',
                    "set name LookA"] + common + ["connect 127.0.0.1:%d" % ports[0], "waitms 6000",
                    "cmd look_fixture " + WHO, "waitms 4000", "set cl_lobbycolor 7", "waitms 3500",
                    "set cl_lobbycolor 9", "waitms 700", "rcon_password rig1616", "rcon map look_smoke.map",
                    "waitms 6000", "set cl_lobbycolor 10", "waitms 1500", "rcon map look_smoke.map",
                    "waitms 6000", "cmd look_fixture " + WHO, "waitms 4000", "set cl_lobbycolor 11",
                    "waitms 700"] + show + ["echo LOOK A FINISHED", "quit"],
        "clientB": ['seta cl_lobbycolor "3"', 'seta paint_size "16"', "set name LookB"] + common +
                   ["connect 127.0.0.1:%d" % ports[1], "waitms 6000", "cmd look_fixture " + WHO,
                    "waitms 4000"] + show + ["echo LOOK B FINISHED", "quit"],
    }
    for label, lines in cfgs.items():
        (game / (label + ".cfg")).write_text("\n".join(["set log_name " + label] + lines) + "\n")
    env = dict(os.environ, HOME=str(rig / "home"))
    def svcmd(i):
        return ["nice", "-n", "19", str(a.server), "-basedir", str(rig), "-nohome", "-port", str(ports[i]),
                "+set", "cfg_save_auto", "0", "+set", "sv_public", "0", "+set", "lobby_master", url,
                "+set", "lobby_master_key", "rigkey", "+set", "lobby_dir", "", "+set", "lobby_enable", "1",
                "+set", "rcon_password", "rig1616", "+set", "log_enable", "1", "+set", "log_dir", "logs",
                "+set", "log_name", "server%d" % (i + 1), "+map", "look_smoke.map"]
    actors = []
    report = {"control": a.control, "ref": a.ref if a.control else "worktree", "ports": ports, "nest": a.nest}
    lab = None
    clenv = dict(env)
    render = ["+set", "vid_renderer", "headless"]
    try:
        if a.nest:
            nest = out / "labwc"
            nest.mkdir()
            (nest / "rc.xml").write_text('<?xml version="1.0"?>\n<labwc_config><core><decoration>server'
                                         '</decoration></core></labwc_config>\n')
            (nest / "autostart").write_text("")
            (nest / "inner.sh").write_text("#!/bin/sh\necho \"$WAYLAND_DISPLAY\" > %s\nexec sleep 3600\n"
                                           % (nest / "ready"))
            (nest / "inner.sh").chmod(0o755)
            lenv = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
            lenv.update(WLR_BACKENDS="headless", WLR_LIBINPUT_NO_DEVICES="1", WLR_RENDERER="gles2")
            lab = subprocess.Popen(["nice", "-n", "19", "labwc", "-C", str(nest), "-s", str(nest / "inner.sh")],
                                   env=lenv, stdout=open(out / "labwc.log", "wb"), stderr=subprocess.STDOUT,
                                   start_new_session=True)
            t0 = time.time()
            while not (nest / "ready").exists() or not (nest / "ready").read_text().strip():
                if lab.poll() is not None or time.time() - t0 > 15:
                    raise RuntimeError("nested labwc did not start")
                time.sleep(0.1)
            clenv.pop("DISPLAY", None)
            clenv["WAYLAND_DISPLAY"] = (nest / "ready").read_text().strip()
            render = ["+set", "vid_renderer", "gl", "-window", "+set", "vid_width", "640", "+set",
                      "vid_height", "480", "+set", "vid_fullscreen", "0", "+set", "vid_winmaximize", "0",
                      "+set", "cl_maxfps", "60"]
        threading.Thread(target=backend.serve_forever, daemon=True).start()
        for i in (0, 1):                # both up (name caches built) before any look file exists
            with (out / ("server%d-launch.log" % (i + 1))).open("w") as so:
                actors.append(subprocess.Popen(svcmd(i), cwd=rig, env=env, stdin=subprocess.DEVNULL, stdout=so,
                                               stderr=subprocess.STDOUT))
        time.sleep(3)
        if actors[0].poll() is not None or actors[1].poll() is not None:
            raise RuntimeError("a server exited")
        look = game / "data/looks" / (WHO + ".txt")
        for label in ("clientA", "clientB"):
            with (out / (label + "-launch.log")).open("w") as co:
                cl = subprocess.Popen(["nice", "-n", "19", str(a.client), "-basedir", str(rig), "-nohome",
                                       "-nosound"] + render + ["+set", "cfg_save_auto",
                                       "0", "+set", "plug_loaddefault", "0", "+exec", label + ".cfg"],
                                      cwd=rig, env=clenv, stdin=subprocess.DEVNULL, stdout=co,
                                      stderr=subprocess.STDOUT)
                actors.append(cl)
                cl.wait(timeout=90)
            report[label + "_exit"] = cl.returncode
            report["look_after_" + label] = look.read_text().strip() if look.exists() else None
            report["mtime_after_" + label] = look.stat().st_mtime_ns if look.exists() else None
    finally:
        for p in reversed(actors):
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=10)
        backend.shutdown()
        backend.server_close()
        if lab is not None:
            os.killpg(lab.pid, signal.SIGTERM)
            lab.wait(timeout=10)

    def log(name):
        p = game / "logs" / (name + ".log")
        return p.read_text(errors="replace") if p.exists() else ""

    ca, cb = log("clientA"), log("clientB")
    report["wire"] = wire
    # The flush at an rcon-driven map change prints into the rcon reply, not the server log.
    report["server_look_lines"] = sorted((ln for ln in (log("server1") + log("rcon")).splitlines()
                                          if " look: data/looks/" in ln), key=lambda ln: ln[:19])
    report["server2_look_lines"] = [ln for ln in log("server2").splitlines() if " look: data/looks/" in ln]
    report["clientB_lines"] = [ln for ln in cb.splitlines() if "hud_player:" in ln or ln.startswith('"')]
    checks = {}
    if a.control:
        checks["no look file"] = report["look_after_clientB"] is None
        checks["no knife post"] = wire["viewmodel_get"] + wire["viewmodel_set"] == 0
        checks["clients ran"] = "LOOK A FINISHED" in ca and "LOOK B FINISHED" in cb
    else:
        colours = [ln.split(": ")[-1].split(",")[1] for ln in report["server_look_lines"]
                   if " saved for LookA: " in ln]
        report["A_saved_colours"] = colours
        checks["A: saved at bind, change and map-end flush (5, 7, 9)"] = colours[:3] == ["5", "7", "9"]
        checks["A: the unbound change survives the next bind (10)"] = colours[3:4] == ["10"]
        checks["A: change then quit is flushed at disconnect (11)"] = (colours[4:] == ["11"]
                                                                       and report["look_after_clientA"] == LAST)
        checks["B: lobby 2 loaded the account look"] = any(" loaded for LookB" in ln
                                                           for ln in report["server2_look_lines"])
        checks["B: client printed it"] = "hud_player: your look from your Steam account" in cb
        checks["B: cvars are the account's"] = all(s in cb for s in (
            '"cl_lobbycolor" is "11"', '"cl_lobbymark" is "255 0 255"', '"paint_size" is "20"'))
        checks["B: nothing saved back"] = (report["mtime_after_clientB"] == report["mtime_after_clientA"]
                                           and not any(" saved for LookB" in ln
                                                       for ln in report["server2_look_lines"]))
        checks["knife: account get and set reached the backend"] = (wire["viewmodel_get"] >= 1
                                                                    and wire["viewmodel_set"] >= 1)
    report["checks"] = checks
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    for k, v in checks.items():
        print(("ok    " if v else "FAIL  ") + k)
    print("report:", out / "report.json")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
