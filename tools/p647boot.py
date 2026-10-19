#!/usr/bin/env python3
"""p647boot.py -- the first-boot screens, driven as a player drives them.  (Patch 647)

    python tools/p647boot.py --progs <dir with the three .dat> [--offline | --later]

p615link's rig: a basedir of its own with NO consent file, surfd in this
process, a lobby on a free port that heartbeats to it, one client.  The
client's keys are real ones (WM_KEYDOWN on its own window, as p615link's):
an answer to the terms is a key or a click on the screen, never a command.

The default path, as a new player who wants it all:
  T  the terms come up by themselves; D then Enter takes "play online":
     data/consent.txt says the current online tier, and uploads are enabled
  S  on the offer, D then Enter takes "Sign in with Steam": the menu joins the
     rig's lobby, with the name still the factory default (the gate is waved
     through once)
  G  on the lobby the game's own box comes up, asking for Enter
--later takes ESC on the offer instead: no join, and the game is told not to
ask again this session.  --offline takes Enter on the terms' default button:
tier 1, no offer, nothing asked of the directory.
Three screenshots are kept for looking at.  Exit 1 on any miss.
"""
import argparse
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import p615link as L


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("C:/FTESurf"))
    ap.add_argument("--client", type=pathlib.Path)
    ap.add_argument("--server", type=pathlib.Path, default=pathlib.Path("C:/FTEQuake/fteqwsv64.exe"))
    ap.add_argument("--output-dir", type=pathlib.Path)
    ap.add_argument("--map", default="bhop_eazy")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--later", action="store_true")
    ap.add_argument("--previous-online", action="store_true",
                    help="seed the previous online tier; it must not grant the new permission")
    ap.add_argument("--blocked-consent", action="store_true",
                    help="make the consent path a directory to exercise write refusal")
    ap.add_argument("--deferred-synth", action="store_true",
                    help="queue synthetic confirmation while minimized beyond its quarantine")
    ap.add_argument("--hover-synth", action="store_true",
                    help="park helper-selected focus, then try a real confirmation after quarantine")
    ap.add_argument("--batch-nav-confirm", action="store_true",
                    help="queue native navigation and confirmation before one redraw")
    ap.add_argument("--journal-optout", action="store_true",
                    help="untick the short page's proposed journal choice using real navigation")
    a = ap.parse_args()
    if a.batch_nav_confirm:
        if a.deferred_synth:
            ap.error("--batch-nav-confirm and --deferred-synth are separate arms")
        a.hover_synth = True
    a.client = a.client or a.content / "ftesurf64.exe"
    a.progs = a.progs.resolve()
    a.output_dir = (a.output_dir or pathlib.Path(tempfile.gettempdir())).resolve()
    if a.blocked_consent and (a.previous_online or a.offline):
        ap.error("--blocked-consent needs a fresh online answer")
    tag = "blocked" if a.blocked_consent else "previous" if a.previous_online else "offline" if a.offline else "later" if a.later else "signin"
    online_tier = int(re.search(r"^#define FS_TERMS_ONLINE (\d+)",
                                (L.ROOT / "src/shared/sh_defs.qc").read_text(), re.M).group(1))

    rig, gd, junctions = L.build_rig(a)
    if a.previous_online:
        (gd / "data").mkdir(exist_ok=True)
        (gd / "data/consent.txt").write_text("FTESURF-CONSENT 1\nversion %d\n" % (online_tier - 1))
    if a.blocked_consent:
        (gd / "data/consent.txt").mkdir(parents=True)
    print("rig", rig)
    server = client = web = None
    try:
        gport = None
        for cand in range(27601, 27620):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                try:
                    probe.bind(("127.0.0.1", cand))
                    gport = cand
                    break
                except OSError:
                    continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            hport = probe.getsockname()[1]
        web, _db = L.start_surfd(rig, hport, "127.0.0.1")
        # What a CLIENT asks the directory (the lobby's own heartbeats are not it).
        asked = []
        S = sys.modules["surfd"]
        inner = S.app.wsgi_app

        def noting(environ, start_response):
            if environ.get("PATH_INFO") in ("/lobbies.json", "/api/join", "/api/board"):
                asked.append(environ.get("PATH_INFO"))
            return inner(environ, start_response)
        S.app.wsgi_app = noting

        common = ["-basedir", str(rig), "-manifest", str(rig / "default.fmf"),
                  "+set", "cfg_save_auto", "0", "+set", "log_enable", "1", "+set", "log_dir", "logs"]
        server = subprocess.Popen(
            [str(a.server), *common, "+set", "log_name", "p647sv", "+set", "developer", "1",
             "+set", "sv_public", "0", "+set", "sv_port", str(gport),
             "+set", "sv_guidkey", "p647-probe", "+set", "sv_maxrate", "0",
             "+set", "sv_maxdownloadrate", "0",
             "+set", "lobby_master", "http://127.0.0.1:%d" % hport,
             "+set", "lobby_master_key", L.KEY, "+set", "lobby_master_rate", "30",
             "+map", a.map], cwd=a.content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)
        if server.poll() is not None:
            raise RuntimeError("the server exited at start (code %s)" % server.returncode)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4                      # shown, focus left alone (a minimised one may not draw)
        client = subprocess.Popen(
            [str(a.client), "-plugin", "-nobrowse", *common, "+set", "log_name", "p647cl",
             "-window", "-nosound", "+set", "con_savehistory", "0", "+set", "cl_idlefps", "0",
             "+set", "cl_maxfps", "100", "+set", "rec_hid_upload", "0",
             # P823: an online answer turns updates on; never let it fetch the real feed
             # (the title menu's ten-minute recheck is forced and ignores autocheck).
             "+set", "update_autocheck", "0", "+set", "update_allow_insecure", "1",
             "+set", "update_manifest_url", "http://127.0.0.1:9/p823-no-feed.json"],
            cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)

        def send(line):
            client.stdin.write(line.encode("ascii") + b"\n")
            client.stdin.flush()

        def shot(name):
            send("screenshot " + name)
            end = time.time() + 15
            while time.time() < end:
                found = list((gd / "screenshots").glob(name + ".*"))
                if found:
                    time.sleep(0.8)
                    from PIL import Image
                    flat = len(Image.open(found[0]).convert("RGB").getcolors(1 << 22) or [0, 0]) < 2
                    shutil.copyfile(found[0], a.output_dir / ("%s-%s%s" % (name, tag, found[0].suffix)))
                    return not flat
                time.sleep(0.5)
            return False

        cl, sv = L.Log(gd / "logs/p647cl.log"), L.Log(gd / "logs/p647sv.log")
        time.sleep(12)                          # the menu is up; a line read while starting is dropped
        send('set lobby_dir "http://127.0.0.1:%d"' % hport)
        send('set lobby_hosts "127.0.0.1"')
        time.sleep(1)
        L.Keys.VK.update(a=0x41, d=0x44, w=0x57, s=0x53)
        keys = L.Keys(client.pid)
        consent = gd / "data" / "consent.txt"
        permission = rig / ".ftesurf-updater" / "consent"

        def updates():
            return permission.read_text().strip() if permission.exists() else None

        def raw_value():
            send("echo JOURNAL_PERMISSION_QUERY")
            if not cl.wait("JOURNAL_PERMISSION_QUERY", 6):
                return None
            send("rec_hid_upload")
            m = cl.wait(r'"rec_hid_upload" is "(\d)"', 6)
            return m.group(1) if m else None

        def native_batch():
            # Freeze ONLY this owned fixture's window thread long enough to put
            # all four native messages on its queue before its next input pump.
            import ctypes
            from ctypes import wintypes as W
            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.OpenThread.argtypes = (W.DWORD, W.BOOL, W.DWORD)
            k.OpenThread.restype = W.HANDLE
            k.GetProcessIdOfThread.argtypes = (W.HANDLE,)
            k.GetProcessIdOfThread.restype = W.DWORD
            k.SuspendThread.argtypes = k.ResumeThread.argtypes = (W.HANDLE,)
            k.SuspendThread.restype = k.ResumeThread.restype = W.DWORD
            k.CloseHandle.argtypes = (W.HANDLE,)
            pid = W.DWORD()
            tid = keys.u.GetWindowThreadProcessId(keys.hwnd, ctypes.byref(pid))
            if pid.value != client.pid or client.poll() is not None:
                raise RuntimeError("batch target is not our live fixture")
            h = k.OpenThread(0x42, False, tid)  # SUSPEND_RESUME | QUERY_INFORMATION
            if not h:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if k.GetProcessIdOfThread(h) != client.pid:
                    raise RuntimeError("batch thread does not belong to our fixture")
                prior = k.SuspendThread(h)
                if prior == 0xFFFFFFFF:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if prior != 0:
                        raise RuntimeError("fixture thread was already suspended")
                    for name in ("a", "enter"):
                        keys._post(keys.VK[name], True)
                        keys._post(keys.VK[name], False)
                finally:
                    resumed = k.ResumeThread(h)
                    if resumed != prior + 1:
                        raise RuntimeError("fixture thread resume count changed")
            finally:
                k.CloseHandle(h)
            return prior, resumed

        if a.previous_online:
            L.check("T  an older online answer grants neither uploads nor directory access",
                    (re.findall(r"version (\d+)", consent.read_text()), raw_value(), asked, updates()),
                    ([str(online_tier - 1)], "0", [], None))
            send("ui_strip_test screen terms")
            L.check("T  opening terms does not upgrade the old answer",
                    (bool(cl.wait("ui_strip_test: screen terms", 6)), raw_value(),
                     re.findall(r"version (\d+)", consent.read_text())),
                    (True, "0", [str(online_tier - 1)]))
        expected_path = (a.previous_online or a.blocked_consent)
        L.check("T  terms draw with the expected fixture consent path",
                (consent.exists(), shot("p647_1_terms")), (expected_path, True))
        n0 = len(asked)
        send("ui_key d")
        time.sleep(0.3)                         # navigation must draw before confirmation
        if a.deferred_synth:
            keys.u.ShowWindow(keys.hwnd, 6)      # only this fixture window
            time.sleep(0.4)
            L.check("T  the fixture is minimized before synthetic input",
                    bool(keys.u.IsIconic(keys.hwnd)), True)
        if a.hover_synth:
            send("ui_hover @tm_online")
            L.check("T  the helper actually parked the pointer on the online answer",
                    bool(cl.wait("ui_hover:", 6)), True)
            time.sleep(2.2)
            if a.batch_nav_confirm:
                L.check("T  native navigation/confirmation queued before the fixture resumes",
                        native_batch(), (0, 1))
            else:
                keys.press("enter")             # real confirmation cannot inherit helper aim
        else:
            send("ui_key enter")
        if a.deferred_synth:
            acted = cl.wait("ui_key: enter", 6)
            start = time.monotonic()
            time.sleep(2.2)
            L.check("T  commands acted while drawing stayed suspended beyond quarantine",
                    (bool(acted), bool(keys.u.IsIconic(keys.hwnd)), time.monotonic() - start > 1.5),
                    (True, True, True))
            keys.u.ShowWindow(keys.hwnd, 4)      # restore without activation
        refused = cl.wait("the terms take a real key or click, not ui_key or ui_click", 6)
        synthetic = (bool(refused), raw_value(), consent.exists())
        L.check("T  synthetic online answer acts but grants no permission",
                synthetic, (True, "0", expected_path))
        L.check("U  P823: ...nor the update permission", updates(), None)
        if synthetic != (True, "0", expected_path):
            return 1                           # never drive a mistakenly accepted offer
        send("ui_hover @tm_accept")             # consistent offline focus after every arm
        time.sleep(2)                           # time alone cannot authorize helper aim

        if a.blocked_consent:
            keys.press("d")
            time.sleep(0.4)
            keys.press("enter")
            L.check("T  a real online answer whose write fails cannot enable uploads",
                    (bool(cl.wait("could not write data/consent.txt", 6)), raw_value(),
                     consent.is_dir(), asked[n0:]), (True, "0", True, []))
            return 1 if L.FAILED else 0
        if a.offline:
            keys.press("a")                    # real navigation replaces helper-selected focus
            time.sleep(0.3)
            keys.press("d")
            time.sleep(0.3)
            keys.press("enter")
            time.sleep(2)
            tier = re.findall(r"version (\d+)", consent.read_text()) if consent.exists() else None
            L.check("T  Enter on the default button is the offline answer: tier 1 on disk, no "
                    "Steam offer, and nothing was asked of the directory",
                    (tier, "Steam sign-in is offered" in cl.text(), asked[n0:]), (["1"], False, []))
            L.check("T  offline answer leaves uploads disabled", raw_value(), "0")
            L.check("U  P823: the offline answer leaves the update permission alone", updates(), None)
            L.check("...and the main menu draws", shot("p647_2_main"), True)
        else:
            if a.journal_optout:
                keys.press("w")                # checkbox above the default offline answer
                time.sleep(0.3)
                keys.press("enter")
                time.sleep(0.3)
                keys.press("s")
                time.sleep(0.3)
            keys.press("d")
            time.sleep(0.4)
            keys.press("enter")
            offered = cl.wait("the terms are taken with lobbies on; the Steam sign-in is offered", 10)
            tier = re.findall(r"version (\d+)", consent.read_text()) if consent.exists() else None
            L.check("T  real online answer records the new tier and enables uploads",
                    (tier, bool(offered), raw_value()),
                    ([str(online_tier)], True, "0" if a.journal_optout else "1"))
            L.check("U  P823: the online answer turns updates on", updates(), "1")
            end = time.time() + 12              # the offer polls the directory for a lobby
            while time.time() < end and "/lobbies.json" not in asked[n0:]:
                time.sleep(0.5)
            time.sleep(2)
            L.check("S  the offer asks the directory for lobbies (it could not before the "
                    "answer), and draws", ("/lobbies.json" in asked[n0:], shot("p647_2_steam")),
                    (True, True))
            if a.later:
                keys.press("esc")
                later = cl.wait("Steam sign-in: not now", 8)
                time.sleep(2)
                send("_acct_prompted")
                held = cl.wait(r'"_acct_prompted" is "(\d)"', 6)
                L.check("S  ESC is the offer's \"not now\": said, no join, and the game is told "
                        "not to ask again this session",
                        (bool(later), "joining" in cl.text(), held.group(1) if held else None),
                        (True, False, "1"))
                L.check("...and the main menu draws", shot("p647_3_main"), True)
            else:
                keys.press("d")
                time.sleep(0.4)
                keys.press("enter")
                went = cl.wait(r"Steam sign-in: joining 127\.0\.0\.1:%d, (\d+) maps known" % gport, 10)
                up = cl.wait("FTESurf CSQC loaded", 60)
                L.check("S  D then Enter joins the rig's lobby, the name still the factory "
                        "default (no name screen in the way)", (bool(went), bool(up)), (True, True))
                # The map list is PLAY's to load and a first boot has not been
                # there; the join's own map check reads it.  Its loader's line
                # must fall between the offer and the join.  (How many maps is
                # the rig's business: its maps are in no mounted game, so 0.)
                text = cl.text()
                # The list also loads at boot now: the load that counts is the one after the offer.
                offer = text.find("the Steam sign-in is offered")
                at = [offer, text.find("duplicate entries coalesced", max(offer, 0)),
                      text.find("Steam sign-in: joining")]
                L.check("S  ...and the map list was loaded for that join's map check",
                        (min(at) >= 0, at == sorted(at)), (True, True))
                box = cl.wait("press Enter to link your Steam account", 30)
                L.check("G  on the lobby the game's own box comes up, asking for Enter",
                        bool(box), True)
                time.sleep(2)
                L.check("...and it draws", shot("p647_3_prompt"), True)
        L.check("no VM error or unknown command in the client's log",
                [w for w in ("Unknown command", "QC VM error", "Cannot call", "stack overflow")
                 if w in cl.text()], [])
        try:
            send("quit")
            client.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return 1 if L.FAILED else 0
    finally:
        for process in (client, server):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        if web is not None:
            web.shutdown()
        for path in junctions:
            if not path.lstat().st_file_attributes & 0x400:
                raise RuntimeError("refusing removal: not our junction: %s" % path)
            path.rmdir()
        print("\nrig kept (junctions removed):", rig)
        if L.FAILED:
            print("%d FAILURE(S):" % len(L.FAILED))
            for f in L.FAILED:
                print("  " + f)


if __name__ == "__main__":
    raise SystemExit(main())
