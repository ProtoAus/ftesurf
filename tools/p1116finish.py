#!/usr/bin/env python3
"""Patch 1116: what a finish costs the client's main thread, with a real-sized journal.

    python tools/p1116finish.py --out <dir under an owned root> --client <ftesurf64.exe> [--synth 30]

bhop_eazy on a local dedicated lobby at run_evidence_ul 2 (the live setting), so a
finish stages the journal, signs the receipt and is asked for the journal, which goes to
a local receiver (rec_hid_testurl) that acknowledges it the way the collector does.
The journal is grown inside the run with `in_journal_synth 1000` every 0.2 s for --synth
seconds (~55 KB/s; sensitivity 0, so the view does not turn), then the client walks into END.

Graded on the client's own lines: in_journal_end / rec_sign / rec_ul_send timings
(developer prints, Patch 1116), the http close line (Patch 1114's poll totals) and
cl_debug_spikes frames from the END touch until the acknowledgement; then each receipt's
signed hid digest against sha256 of the staged file and of the bytes received.
Needs the rig lock and an announcement to peers (tools/p840clock.py's take_lock).

RESULT 2026-10-29, --quiet --synth 60 (3.2 MB journal), 2 runs each: control 2875e7f7 had
command frames of 20.0-20.6 ms (journal end) and 16.8-16.9 ms (upload read+hash); P1116
bb642a67 has neither (largest 9.5 ms). A build dropping one byte from the running hash fails
the digest check. TRAPS: headless draws no frame, so the recorder starts no journal; with
developer 1 every printed line costs 4-6 ms here (log_enable reopens the file per line), so
judge frame costs with --quiet; a stdin line over 255 bytes wedges the -plugin reader.
"""
import argparse
import hashlib
import http.server
import json
import re
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p840clock as P  # noqa: E402
from spec_chat_smoke import Peer  # noqa: E402


class Receiver(http.server.BaseHTTPRequestHandler):
    got = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        t0 = time.monotonic()
        body = self.rfile.read(n)
        digest = hashlib.sha256(body[1024:]).hexdigest()
        Receiver.got.append(dict(bytes=n, secs=round(time.monotonic() - t0, 3), sha256=digest))
        reply = ("stored %s %d\n" % (digest, n - 1024)).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *a):
        pass


def grade(text):
    """The finish's own lines and every slow frame between END and the acknowledgement."""
    out = {}
    for key, pat in (("end", r"in_journal_end: data/staged/\S+, .*?(\d+)k, digest ([\d.]+) ms, write ([\d.]+) ms"),
                     ("sign", r"rec_sign: \S+ on .* ([\d.]+) ms\n"),
                     ("read", r"rec_ul_send: read ([\d.]+) ms, hash ([\d.]+) ms(?: on a loader thread)?, sign ([\d.]+) ms"),
                     ("http", r"http: \S+/api/hid closed: ([\d.]+) ms on the main thread over (\d+) frame polls, the longest ([\d.]+) ms"),
                     ("ack", r"rec_ul_send: journal HTTP (stored and digest acknowledged|not acknowledged)")):
        m = re.findall(pat, text)
        out[key] = m[-1] if m else None
    spikes = re.findall(r"\[engine-spike\] frame=(\d+) total=([\d.]+)ms .*?early=([\d.]+) cap=[\d.]+ work=([\d.]+) "
                        r"input=([\d.]+) protocol=([\d.]+) server=[\d.]+ postread=[\d.]+ clienttime=([\d.]+) gfx=([\d.]+)", text)
    out["spikes"] = [dict(frame=int(s[0]), total=float(s[1]), early=float(s[2]), work=float(s[3]),
                          input=float(s[4]), protocol=float(s[5]), clienttime=float(s[6]), gfx=float(s[7]))
                     for s in spikes]
    return out


def profile_top(text, n=15):
    """The first profile_csqc dump in text, costliest self time first (ms)."""
    rows, seen = [], False
    for ln in text.splitlines():
        if "ops self-time total-time" in ln:
            if seen:
                break
            seen = True
            continue
        m = re.search(r"^\S+ \S+\s+(\d+)\s+([\d.]+)\s+([\d.]+): (\S+)", ln)
        if seen and m:
            rows.append((round(float(m.group(2)) * 1000, 2), round(float(m.group(3)) * 1000, 2), m.group(4)))
    return sorted(rows, reverse=True)[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--client", type=Path, required=True)
    ap.add_argument("--progs", type=Path, default=Path("C:/FTESurf/ftesurf"))
    ap.add_argument("--port", type=int, default=27631)
    ap.add_argument("--hport", type=int, default=27632)
    ap.add_argument("--synth", type=float, default=30, help="seconds of 5000 synthetic events/s (~55 KB/s)")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--pre", type=float, default=1.5, help="seconds in the run before the synthetic input")
    ap.add_argument("--profwin", action="store_true", help="profile the walk and finish frame only")
    ap.add_argument("--threaded", type=int, default=0, help="cl_threadedphysics: 1 takes the whole-buffer hash")
    ap.add_argument("--quiet", action="store_true", help="developer 0: what a player pays (no timing lines)")
    a = ap.parse_args()
    P.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    for port, kind in ((a.port, socket.SOCK_DGRAM), (a.hport, socket.SOCK_STREAM)):
        with socket.socket(socket.AF_INET, kind) as s:
            s.bind(("127.0.0.1", port))
    phys, commit = P.free_mb()
    print("free physical %d MB, commit %d MB" % (phys, commit), flush=True)
    if phys < 1500 or commit < 2200:
        raise SystemExit("not enough free memory for a server and a client")
    report = dict(client=hashlib.sha256(a.client.read_bytes()).hexdigest()[:16],
                  server=hashlib.sha256(Path("C:/FTEQuake/fteqwsv64.exe").read_bytes()).hexdigest()[:16],
                  qwprogs=hashlib.sha256((a.progs / "qwprogs.dat").read_bytes()).hexdigest()[:16],
                  csprogs=hashlib.sha256((a.progs / "csprogs.dat").read_bytes()).hexdigest()[:16],
                  synth=a.synth, quiet=a.quiet, runs=[])
    print("hashes", report, flush=True)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", a.hport), Receiver)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    common = ["cfg_save_auto 0", "con_savehistory 0", "log_enable 1", "log_dir logs",
              "log_name probe", "log_readable 1", "set cl_idlefps 0", "set cl_maxfps 250",
              "set run_resume 0", 'set lobby_dir ""', 'set lobby_master ""',
              "set cl_run_upload 0", 'set cl_board_url ""', "set sv_public 0"]
    P.take_lock("p1116finish")
    sv = cl = None
    try:
        sv_base = P.prepare(a.out, "server", a.progs, a.progs / "csprogs.dat")
        (sv_base / "ftesurf/probe.cfg").write_text("\n".join(common + [
            f"sv_port {a.port}", "sv_playerslots 2", "sv_maxclients 2", "set sv_gamemode surf",
            # a lobby: no PBs, so every finish stages and uploads its journal
            "set lobby_enable 1", "set lobby_nopb 1", "set lobby_norec 0",
            "set rec_enable 1", "set run_evidence_ul 2", f"map {P.MAP}"]) + "\n")
        sv = Peer(Path(r"C:\FTEQuake\fteqwsv64.exe"), sv_base, "probe.cfg", True)
        sv.wait(r"Server spawned\.", timeout=90)
        base = P.prepare(a.out, "client", a.progs, a.progs / "csprogs.dat")
        (base / "ftesurf/data/consent.txt").write_text("version 8\n")
        shutil.copy2(a.client, base / "client.exe")
        (base / "ftesurf/probe.cfg").write_text("\n".join(common + [
            *([] if a.quiet else ["developer 1", "log_developer 1"]), "cl_debug_spikes 1", "cl_debug_spike_ms 8",
            "set rec_upload 1", "set rec_hid_upload 1", "set rec_hid 1", "set sensitivity 0",
            f'set rec_hid_testurl "http://127.0.0.1:{a.hport}/api/hid"',   # quoted: // is a comment
            "cl_threadedphysics %d" % a.threaded, 'name "p1116"', f"connect 127.0.0.1:{a.port}"]) + "\n")
        cl = Peer(base / "client.exe", base, "probe.cfg")    # windowed: headless draws no frame, so no journal
        cl.wait("FTESurf CSQC loaded", timeout=120)
        time.sleep(3)
        cl.send("menu_restart; ui_close")
        time.sleep(1)
        for line in ("set cl_forwardspeed 70", "set run_prestrafe 0", "set m_accel 0"):
            cl.send(line)
        # the harness's own cost: log_enable opens, appends to and closes the file per line
        off = len(cl.text())
        cl.send("; ".join(["echo lc"] * 20))    # under 255 bytes: a longer stdin line wedges the -plugin reader
        time.sleep(2)
        report["logcost20"] = grade(cl.text()[off:])["spikes"][:2]
        for i in range(a.runs):
            Receiver.got.clear()
            cl.send("cmd zone_goto 0")
            time.sleep(2)
            cl.send("+forward")
            t0 = time.monotonic()
            while time.monotonic() - t0 < 40:
                x = float(cl.query("cmd viewpos", r"setpos ([-\d.]+) [-\d.]+ [-\d.]+", 10).group(1))
                if x > -345:
                    cl.send("-forward")
                    break
                time.sleep(0.1)
            time.sleep(a.pre)    # standing adds little journal: only a small-HASHSTEP build marks hashed bytes
            t1 = time.monotonic()
            while time.monotonic() - t1 < a.synth:    # batches under the 3072-event ring
                cl.send("in_journal_synth 1000")
                time.sleep(0.2)
            time.sleep(3.0)
            cl.send("profile_csqc")     # first call enables, later ones print and reset
            time.sleep(0.5)
            off = len(cl.text())
            cl.send("+forward")
            if a.profwin:               # the profile covers the walk and the finish frame only
                cl.wait(r"saved on your PC|main saved", off, 30)
                time.sleep(0.3)
                prof = len(cl.text())
                cl.send("profile_csqc")
            found = cl.wait(r"journal HTTP (stored|not acknowledged|not started)|in_journal_end: discarded", off, 60)
            cl.send("-forward")
            time.sleep(1.0)
            poff = len(cl.text())
            if not a.profwin:
                prof = poff
                cl.send("profile_csqc")
                time.sleep(1.5)
            got = grade(cl.text()[off:poff])
            got["profile"] = profile_top(cl.text()[prof:])
            got["received"] = list(Receiver.got)
            got["result"] = found.group(0)
            report["runs"].append(got)
            print("run %d" % i, json.dumps(got), flush=True)
            time.sleep(2)
        focus = re.findall(r"\[focus\][^\n]*", cl.text())
        report["focus_lines"] = focus[:5]
    finally:
        if cl is not None and cl.proc.poll() is None:
            cl.send("condump p1116_condump.txt")    # the console, if the log stopped (one failed open disables it)
            time.sleep(1.5)
        for peer in (cl, sv):
            if peer is not None:
                peer.stop()
        httpd.shutdown()
        P.drop_lock()
    # the signed journal digest against the staged file it describes, and the bytes received
    sent = {g["sha256"] for r in report["runs"] for g in r["received"]}
    report["digests"] = []
    for rc in sorted((a.out / "server/ftesurf/data/evidence").rglob("*.rcpt")):
        t = rc.read_text()
        nonce = re.search(r"^signed nonce (\w+)", t, re.M).group(1)
        hexd, size = re.search(r"^signed hid (\w+) (\d+)", t, re.M).groups()
        f = a.out / "client/ftesurf/data/staged" / (nonce + ".hid")
        b = f.read_bytes() if f.exists() else b""
        report["digests"].append(dict(rcpt=rc.name, file=f.exists(), size_ok=len(b) == int(size),
                                      sha_ok=hashlib.sha256(b).hexdigest() == hexd, uploaded=hexd in sent))
    print("digests", report["digests"], flush=True)
    (a.out / "report.json").write_text(json.dumps(report, indent=1))
    print("report", a.out / "report.json")


if __name__ == "__main__":
    main()
