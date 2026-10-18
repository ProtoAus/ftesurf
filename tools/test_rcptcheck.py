"""Receipt snapshot falsifiers. Only generated evidence in throwaway homes.

A close-time swap proves the path actually changed AFTER the captured read.
The verdict must describe those captured bytes, not a later open of that path.
"""
import builtins
import contextlib
import hashlib
import io
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "surfd"))
import test_sweep as fx
import hidcheck
import reccheck
import rcptcheck

FAILED = []
CHECKS = 0


def check(label, got, want):
    global CHECKS
    CHECKS += 1
    ok = got == want
    print("%-4s %-65s %s" % ("ok" if ok else "FAIL", label, ascii(got)))
    if not ok:
        FAILED.append(label)


@contextlib.contextmanager
def swap_after_close(path, replacement):
    """Rewrite after the FIRST read closes, using the unpatched open to write."""
    real_open = builtins.open
    state = {"reads": 0, "swaps": 0}

    class Swap:
        def __init__(self, fh):
            self.fh = fh

        def __enter__(self):
            return self.fh.__enter__()

        def __exit__(self, *args):
            result = self.fh.__exit__(*args)
            if not state["swaps"]:
                with real_open(path, "wb") as out:
                    out.write(replacement)
                state["swaps"] += 1
            return result

    def opening(p, *args, **kwargs):
        fh = real_open(p, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if p == path and "r" in mode:
            state["reads"] += 1
            return Swap(fh)
        return fh

    with mock.patch("builtins.open", side_effect=opening):
        yield state


def test_swap(kind, broken_first=False):
    surfd, sweep, _runs = fx.fresh()
    sweep.TOOLS = fx.TOOLS
    conn = surfd.connect()
    rid = "20261006-000200-0"
    rec, view = fx.angle_pair(rid)
    _rec, wrong_view = fx.angle_pair(rid, rot=0.5)
    clean = fx._journal_text().encode("utf-8")
    broken = fx._journal_text(break_pitch=True).encode("utf-8")
    first = broken if broken_first else clean
    rp, _pub = fx.make_receipt(surfd.EVIDENCE_DIR, rid, view=view.encode("utf-8"), hid=first, age=1)
    rc = fx.with_rec(surfd, sweep, rid, rec)
    path = rp[:-5] + "." + kind
    replacement = (clean if broken_first else broken) if kind == "hid" else wrong_view.encode("utf-8")
    try:
        with swap_after_close(path, replacement) as state:
            check("swap %s: sweep actually stores a receipt" % kind,
                  sweep.receipt_step(conn), (1, 0))
        row = conn.execute("SELECT verdict, sig, angles, journal, journal_reason FROM receipts").fetchone()
        check("swap %s: the substitution hook ACTED" % kind, state["swaps"], 1)
        check("swap %s: one captured read only" % kind, state["reads"], 1)
        check("swap %s: angle verdict uses the signed snapshot" % kind,
              tuple(row[:3]), ("VALID", 1, "OK"))
        check("swap %s: journal uses the signed snapshot" % kind,
              row[3], "FAULT" if broken_first else "OK")
        if broken_first:
            check("swap hid: signed pitch fault cannot be hidden by clean replacement",
                  "PITCH IDENTITY BROKEN" in row[4], True)
        # CONTROL: a NEW observation of the replacement must fault the digest.
        r = rcptcheck.read(rp)
        rcptcheck.join_uploaded(r, {})
        check("swap %s: CONTROL later observation catches replacement digest" % kind,
              kind in r.digest_bad, True)
    finally:
        rc.GAME = os.path.join(os.path.dirname(fx.TOOLS), "ftesurf")
        conn.close()


def test_rec_swap():
    surfd, sweep, _runs = fx.fresh()
    sweep.TOOLS = fx.TOOLS
    rid = "20261006-000201-0"
    nonce = "d6c6820bca16750c77166d96dcf02787"
    rec, view = fx.angle_pair(rid)
    rec = rec.replace("\nbegin\n", "\nnonce " + nonce + "\nbegin\n", 1)
    replacement = rec.replace(nonce, "0" * 32).replace(
        "\nend ", "\nnonce 1 " + "0" * 32 + "\nend ", 1).encode("utf-8")
    check("rec swap: intended later-session nonce mutation ACTED",
          b"\nnonce 1 " + b"0" * 32 + b"\n" in replacement, True)
    rp, _pub = fx.make_receipt(surfd.EVIDENCE_DIR, rid, view=view.encode("utf-8"))
    rc = fx.with_rec(surfd, sweep, rid, rec)
    path = os.path.join(rc.GAME, "data", "evidence", "bhop_eazy", rid + ".rec")
    try:
        with swap_after_close(path, replacement) as state:
            got = sweep.read_receipt(rp)
        check("rec swap: replacement ACTED", state["swaps"], 1)
        check("rec swap: identity, nonce and angles share one read", state["reads"], 1)
        check("rec swap: original nonce and angles still describe captured rec",
              (got[0], got[3]), ("VALID", "OK"))
        check("rec swap: CONTROL next observation catches changed nonce",
              sweep.read_receipt(rp)[0], "FAULT")
        body_only = rec.replace("\nend ", "\nnonce 1 " + "0" * 32 + "\nend ", 1)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body_only)
        r = rcptcheck.read(rp)
        rcptcheck.join_rec(r)
        check("rec swap: CONTROL only the final session nonce changes",
              len(r.faults) == 1 and "later one" in r.faults[0], True)
    finally:
        rc.GAME = os.path.join(os.path.dirname(fx.TOOLS), "ftesurf")


def test_absent_arrives_between_phases():
    surfd, sweep, _runs = fx.fresh()
    rid = "20261006-000202-0"
    hid = fx._journal_text().encode("utf-8")
    rp, _pub = fx.make_receipt(surfd.EVIDENCE_DIR, rid, hid=hid)
    path = rp[:-5] + ".hid"
    os.remove(path)
    r = rcptcheck.read(rp)
    rcptcheck.join_uploaded(r, {})
    with open(path, "wb") as fh:
        fh.write(hid)
    rcptcheck.join_journal(r)
    check("arrival between phases: CONTROL file now exists", os.path.exists(path), True)
    check("arrival between phases: not judged from an unhashed new file", r.journal, "ABSENT")
    r = rcptcheck.read(rp)
    rcptcheck.join_uploaded(r, {})
    rcptcheck.join_journal(r)
    check("arrival between phases: CONTROL next observation judges it", r.journal, "OK")


def test_explicit_view_and_bad_digest():
    surfd, sweep, _runs = fx.fresh()
    rid = "20261006-000203-0"
    rec, view = fx.angle_pair(rid)
    _rec, wrong = fx.angle_pair(rid, rot=0.5)
    rp, _pub = fx.make_receipt(surfd.EVIDENCE_DIR, rid, view=view.encode("utf-8"))
    rc = fx.with_rec(surfd, sweep, rid, rec)
    path = rp[:-5] + ".explicit.view"
    with open(path, "wb") as fh:
        fh.write(view.encode("utf-8"))
    try:
        with swap_after_close(path, wrong.encode("utf-8")) as state:
            r = rcptcheck.read(rp)
            rcptcheck.join_rec(r)
            rcptcheck.check_file(r, "view", path)
            rcptcheck.join_angles(r, {"view": path})
        check("explicit view: replacement ACTED and only one read", state, {"reads": 1, "swaps": 1})
        check("explicit view: angle parser uses explicitly hashed bytes", (r.angles, r.faults), ("OK", []))
        r = rcptcheck.read(rp)
        rcptcheck.join_rec(r)
        rcptcheck.check_file(r, "view", path)
        rcptcheck.join_angles(r, {"view": path})
        check("explicit view: wrong digest never claims signed-content angle OK", r.angles, "FAULT")
        check("explicit view: digest is the reason", "hashes to" in r.angles_detail, True)
    finally:
        rc.GAME = os.path.join(os.path.dirname(fx.TOOLS), "ftesurf")


def test_missing_view_and_io():
    surfd, sweep, _runs = fx.fresh()
    rid = "20261006-000205-0"
    rec, view = fx.angle_pair(rid)
    rp, _pub = fx.make_receipt(surfd.EVIDENCE_DIR, rid, view=view.encode("utf-8"))
    rc = fx.with_rec(surfd, sweep, rid, rec)
    path = rp[:-5] + ".view"
    try:
        os.remove(path)
        r = rcptcheck.read(rp)
        rcptcheck.join_rec(r)
        rcptcheck.join_uploaded(r, {})
        with open(path, "wb") as fh:
            fh.write(view.encode("utf-8"))
        rcptcheck.join_angles(r, {})
        check("view arrival: absence captured before upload remains unjudged", r.angles, "")
        check("view arrival: CONTROL next observation judges it", sweep.read_receipt(rp)[3], "OK")
        real_open = builtins.open
        attempts = []

        def eio(p, *args, **kwargs):
            if p == path:
                attempts.append(p)
                raise PermissionError(13, "Permission denied")
            return real_open(p, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=eio):
            r = rcptcheck.read(rp)
            rcptcheck.join_rec(r)
            rcptcheck.join_uploaded(r, {})
            rcptcheck.join_angles(r, {})
        check("snapshot I/O: the unreadable path was attempted exactly once", len(attempts), 1)
        check("snapshot I/O: not a measured angle or digest fault", (r.ioerror, r.angles, r.digest_bad), (True, "", {}))
        check("snapshot I/O: CLI still has a nonzero-result diagnostic", r.faults[0].startswith("--view "), True)
        with mock.patch("builtins.open", side_effect=eio):
            check("snapshot I/O: sweep defers the observation", sweep.read_receipt(rp), None)
        check("snapshot I/O: CONTROL restored access really measures angles", sweep.read_receipt(rp)[3], "OK")
    finally:
        rc.GAME = os.path.join(os.path.dirname(fx.TOOLS), "ftesurf")


def test_selected_rec_tail_io():
    surfd, sweep, _runs = fx.fresh()
    sweep.TOOLS = fx.TOOLS
    rid = "20261006-000206-0"
    rec, view = fx.angle_pair(rid, rot=0.5)
    rp, _pub = fx.make_receipt(surfd.EVIDENCE_DIR, rid, view=view.encode("utf-8"), age=1)
    rc = fx.with_rec(surfd, sweep, rid, rec)
    path = os.path.join(rc.GAME, "data", "evidence", "bhop_eazy", rid + ".rec")
    real_open = builtins.open
    attempts = []

    class TailError:
        def __init__(self, fh):
            self.fh = fh

        def __enter__(self):
            self.fh.__enter__()
            return self

        def __exit__(self, *args):
            return self.fh.__exit__(*args)

        def __iter__(self):
            return iter(self.fh)

        def read(self):
            attempts.append(path)
            raise OSError(5, "selected recording tail I/O")

    def opening(p, *args, **kwargs):
        fh = real_open(p, *args, **kwargs)
        return TailError(fh) if p == path else fh

    try:
        with mock.patch("builtins.open", side_effect=opening):
            check("selected rec tail I/O: sweep defers rather than storing VALID", sweep.read_receipt(rp), None)
        check("selected rec tail I/O: failure hook ACTED", len(attempts), 1)
        with mock.patch("builtins.open", side_effect=opening), contextlib.redirect_stdout(io.StringIO()) as out:
            check_result = rcptcheck.main([rp])
        check("selected rec tail I/O: CLI exits nonzero", check_result, 1)
        check("selected rec tail I/O: CLI explicitly reports unmeasured content", "deferred after I/O" in out.getvalue(), True)
        got = sweep.read_receipt(rp)
        check("selected rec tail I/O: CONTROL restored read measures angle fault", (got[0], got[3]), ("FAULT", "FAULT"))
        conn = surfd.connect()
        try:
            check("selected rec tail I/O: CONTROL measured fault is stored", sweep.receipt_step(conn), (1, 1))
            conn.execute("UPDATE receipts SET stale = 2")
            conn.commit()
            with mock.patch("builtins.open", side_effect=opening):
                check("selected rec tail I/O: interrupted stale read stays retryable", sweep.receipt_step(conn), (0, 0))
            row = conn.execute("SELECT verdict, angles, stale FROM receipts").fetchone()
            check("selected rec tail I/O: old measured observation survives", tuple(row), ("FAULT", "FAULT", 2))
            sweep.receipt_step(conn)
            row = conn.execute("SELECT verdict, angles, stale FROM receipts").fetchone()
            check("selected rec tail I/O: CONTROL healthy recovery completed", tuple(row), ("FAULT", "FAULT", 0))
        finally:
            conn.close()
        with open(rp[:-5] + ".view", "ab") as fh:
            fh.write(b"changed\n")
        with mock.patch("builtins.open", side_effect=opening):
            got = sweep.read_receipt(rp)
        check("selected rec tail I/O: independent digest fault survives", (got[0], "hashes to" in got[4]), ("FAULT", True))
    finally:
        rc.GAME = os.path.join(os.path.dirname(fx.TOOLS), "ftesurf")


def test_unsigned_sibling_io():
    surfd, sweep, _runs = fx.fresh()
    sweep.TOOLS = fx.TOOLS
    conn = surfd.connect()
    rid = "20261006-000207-0"
    rp, _pub = fx.make_receipt(surfd.EVIDENCE_DIR, rid, age=1)
    check("unsigned sibling I/O: CONTROL seed an existing healthy row", sweep.receipt_step(conn), (1, 0))
    conn.execute("UPDATE receipts SET stale = 2")
    conn.commit()
    path = rp[:-5] + ".hid"
    with open(path, "wb") as fh:
        fh.write(b"unsigned sibling")
    real_open = builtins.open
    attempts = []

    def eio(p, *args, **kwargs):
        if p == path:
            attempts.append(p)
            raise PermissionError(13, "Permission denied")
        return real_open(p, *args, **kwargs)

    try:
        with mock.patch("builtins.open", side_effect=eio):
            got = sweep.read_receipt(rp)
        check("unsigned sibling I/O: CONTROL presence is independently known", os.path.exists(path), True)
        check("unsigned sibling I/O: denied read ACTED exactly once", len(attempts), 1)
        check("unsigned sibling I/O: missing-digest fault survives denied bytes", (got[0], got[6]), ("FAULT", "FAULT"))
        check("unsigned sibling I/O: reason names the independently signed contradiction", "hid digest is absent" in got[4], True)
        with mock.patch("builtins.open", side_effect=eio):
            check("unsigned sibling I/O: a partial fault is persisted", sweep.receipt_step(conn), (1, 1))
        row = conn.execute("SELECT stale FROM receipts").fetchone()
        check("unsigned sibling I/O: partial reread still needs completion", row[0], 2)
        partial = conn.execute("SELECT COUNT(*) FROM sweepmeta WHERE k LIKE 'receipt_partial:%'").fetchone()[0]
        check("unsigned sibling I/O: partial provenance was actually recorded", partial, 1)
        os.remove(path)
        check("unsigned sibling I/O: CONTROL recovery ACTUALLY processed the row", sweep.receipt_step(conn), (1, 1))
        row = conn.execute("SELECT verdict, journal, stale FROM receipts").fetchone()
        check("unsigned sibling I/O: removal before recovery cannot clear stored fault", (row[0], row[1]), ("FAULT", "FAULT"))
        check("unsigned sibling I/O: CONTROL recovery completed", row[2], 0)
        partial = conn.execute("SELECT COUNT(*) FROM sweepmeta WHERE k LIKE 'receipt_partial:%'").fetchone()[0]
        check("unsigned sibling I/O: completion retired partial provenance", partial, 0)
        # Presence itself unmeasured: do not infer a contradiction from denial.
        with mock.patch("builtins.open", side_effect=eio), mock.patch("os.stat", side_effect=PermissionError(13, "unknown presence")):
            r = rcptcheck.read(rp)
            rcptcheck.join_uploaded(r, {})
        check("unknown presence I/O: not a measured missing-digest fault", (r.ioerror, r.digest_bad), (True, {}))
    finally:
        conn.close()


def test_parser_bytes():
    surfd, sweep, _runs = fx.fresh()
    rec, view = fx.angle_pair("20261006-000204-0")
    hid = fx._journal_text()
    for name, parser, text in (("rec", reccheck.check_rec, rec),
                               ("view", reccheck.check_view, view),
                               ("hid", hidcheck.check_hid, hid)):
        with mock.patch("builtins.open", side_effect=AssertionError("empty bytes opened path")):
            empty = parser("missing." + name, data=b"")
        check("%s: empty captured bytes are parsed, not reopened" % name, bool(empty.faults), True)
        for nl in ("\n", "\r\n", "\r"):
            # Include a replacement character and a Unicode line separator in
            # a comment: splitlines() would change text-mode parser semantics.
            data = (text + "# invalid \ufffd separator \u2028\n").replace("\n", nl).encode("utf-8") + b"\xff"
            path = os.path.join(os.environ["SURFD_HOME"], "probe." + name)
            with open(path, "wb") as fh:
                fh.write(data)
            disk = parser(path)
            with mock.patch("builtins.open", side_effect=AssertionError("byte parser opened path")):
                captured = parser(path, data=data)
            check("%s byte parser matches filename mode for %r" % (name, nl),
                  (captured.faults, captured.notes, captured.info),
                  (disk.faults, disk.notes, disk.info))


def test_unavailable_angles_keep_view_faults():
    """Post-signature classification: matching captured digest is not valid content."""
    rec, good = fx.angle_pair("20261006-000206-0")
    rec = "\n".join("flags 1" if l.startswith("flags ") else l
                    for l in rec.splitlines()) + "\n"
    end = int(next(l.split()[1] for l in rec.splitlines() if l.startswith("end ")))
    header = "FTESURF-VIEW 2\nmap bhop_eazy\nhid 1\nbegin\n"
    cases = [("range", header + "10.0 1000 %d 0 90 0\n" % (end + 1), "FAULT"),
             ("nonfinite", header + "10.0 1000 0 nan 90 0\n", "FAULT"),
             ("backwards", header + "10.0 1000 1 0 90 0\n10.1 1000 0 0 90 0\n", "FAULT"),
             ("valid", good, "BLIND")]
    for label, view, expected in cases:
        data = view.encode("utf-8")
        r = rcptcheck.Receipt("epoch.rcpt")
        r.recpath, r.recdata = "epoch.rec", rec.encode("utf-8")
        r.file_bytes["epoch.view"] = data
        r.signed = [("view", hashlib.sha256(data).hexdigest())]
        with mock.patch("builtins.open", side_effect=AssertionError("reopened captured evidence")):
            rcptcheck.join_angles(r, {"view": "epoch.view"})
        check("epoch %s: captured view digest was ACTUALLY checked" % label,
              (("view", "epoch.view") in r.digest_checked, r.digest_bad), (True, {}))
        check("epoch %s: availability does not hide independent content faults" % label,
              (r.angles, bool(r.faults)), (expected, expected == "FAULT"))
        if label == "valid":
            check("epoch valid: no unsupported angular-mismatch accusation", r.faults, [])


def test_initial_clock_origin():
    import test_reccheck as vectors

    trusted, good = vectors.held_clock_pair(holds=((0, 73),))
    invalid = trusted[:]
    ix = next(i for i, line in enumerate(invalid) if line.startswith("hold "))
    fields = invalid[ix].split()
    fields[2] = str(int(fields[2]) + 1)
    invalid[ix] = " ".join(fields)
    base = vectors.build(sweep=128, packets=600)
    restored = vectors.head(base[:], "instart", "%d %d" %
                            (vectors.HORIZON, vectors.HORIZON - 50))
    nonfinite = vectors.view_for(base)
    nonfinite[4] = "10.01 1 nan 0 0 0"
    cases = [("trusted", trusted, good, False, "OK"),
             ("before-origin", invalid, good, True, "BLIND"),
             ("restored", restored, vectors.view_for(base, rot=5), False, "BLIND"),
             ("restored-nonfinite", restored, nonfinite, False, "FAULT")]
    for label, lines, view, bad_rec, expected in cases:
        data = ("\n".join(view) + "\n").encode("utf-8")
        r = rcptcheck.Receipt("origin.rcpt")
        r.recpath = "origin.rec"
        r.recdata = ("\n".join(lines) + "\n").encode("utf-8")
        r.file_bytes["origin.view"] = data
        r.signed = [("view", hashlib.sha256(data).hexdigest())]
        with mock.patch("builtins.open", side_effect=AssertionError("reopened captured evidence")):
            rcptcheck.join_angles(r, {"view": "origin.view"})
        check("origin %s: digest check ACTED on captured bytes" % label,
              (("view", "origin.view") in r.digest_checked, r.digest_bad), (True, {}))
        check("origin %s: recording format result is independent" % label,
              bool(r.rec_report.faults), bad_rec)
        check("origin %s: receipt classification respects clock authority" % label,
              (r.angles, bool(r.faults)), (expected, expected == "FAULT"))
        if label != "trusted":
            check("origin %s: no unsupported angular conviction" % label,
                  any("not this recording's" in x or "does not describe this recording" in x
                      for x in r.faults), False)


def test_retry_clock_faults():
    import test_reccheck as vectors

    cases = [("declared", 2, 2, "BLIND"), ("missing", 0, 2, "FAULT"),
             ("extra", 2, 3, "FAULT"), ("invalid-marker", 2, 2, "FAULT"),
             ("untrusted-view-claim", 0, 2, "FAULT"),
             ("run-clock", 2, 2, "FAULT"), ("nonfinite", 2, 2, "FAULT"),
             ("range", 2, 2, "FAULT"), ("invalid-recording", 2, 2, "FAULT"),
             ("cold-load", 2, 2, "BLIND"), ("cold-retry", 2, 2, "BLIND"),
             ("cold-extra", 2, 3, "FAULT"), ("session-only", 2, 2, "BLIND"),
             ("session-extra", 2, 3, "FAULT"), ("cold-run-clock", 2, 2, "FAULT"),
             ("legacy-resume", 2, 2, "BLIND"), ("legacy-extra", 2, 3, "FAULT"),
             ("slot-zero", 2, 2, "BLIND"), ("slot-upper", 2, 2, "BLIND"),
             ("slot-text", 2, 2, "FAULT"), ("slot-range", 2, 2, "FAULT"),
             ("slot-negative", 2, 2, "FAULT"), ("slot-fraction", 2, 2, "FAULT"),
             ("slot-unicode", 2, 2, "FAULT"), ("slot-overlong", 2, 2, "FAULT")]
    slots = {"slot-zero": "0", "slot-upper": "999", "slot-text": "bad",
             "slot-range": "1000", "slot-negative": "-1", "slot-fraction": "1.0",
             "slot-unicode": "\u0662", "slot-overlong": "1" * 129}
    for label, retries, resets, expected in cases:
        if label.startswith("cold-"):
            lines, view = vectors.cold_clock_pair("retry" if label == "cold-retry" else "load", resets)
        elif label.startswith("session-"):
            lines, view = vectors.cold_clock_pair("drop", resets, restore=False)
        else:
            lines, view = vectors.retry_clock_pair(retries, resets)
        if label.startswith("legacy-") or label in slots:
            slot = slots.get(label, "1")
            lines = ["resume %s %s" % (slot, l.split()[1]) if l.startswith("retry ") else l
                     for l in lines]
        if label == "invalid-marker":
            lines = ["retry --1" if l.startswith("retry ") else l for l in lines]
        elif label == "untrusted-view-claim":
            view.insert(3, "retries 2")
        elif label in ("run-clock", "cold-run-clock"):
            f = view[-1].split(); f[2] = "0"; view[-1] = " ".join(f)
        elif label == "nonfinite":
            f = view[-1].split(); f[3] = "nan"; view[-1] = " ".join(f)
        elif label == "range":
            end = int(next(l.split()[1] for l in lines if l.startswith("end ")))
            f = view[-1].split(); f[2] = str(end + 1); view[-1] = " ".join(f)
        elif label == "invalid-recording":
            lines.append(next(l for l in lines if l.startswith("end ")))
        raw = ("\n".join(lines) + "\n").encode("utf-8")
        data = ("\n".join(view) + "\n").encode("utf-8")
        r = rcptcheck.Receipt("retry.rcpt")
        r.recpath, r.recdata = "retry.rec", raw
        r.file_bytes["retry.view"] = data
        r.signed = [("view", hashlib.sha256(data).hexdigest())]
        with mock.patch("builtins.open", side_effect=AssertionError("reopened captured evidence")):
            rcptcheck.join_angles(r, {"view": "retry.view"})
        check("retry %s: source format control ACTED" % label,
              bool(r.rec_report.faults), label == "invalid-recording")
        check("retry %s: captured digest check ACTED" % label,
              (("view", "retry.view") in r.digest_checked, r.digest_bad), (True, {}))
        invalid_slot = label in slots and label not in ("slot-zero", "slot-upper")
        budget = 0 if invalid_slot or label in (
            "missing", "invalid-marker", "untrusted-view-claim", "invalid-recording") else 2
        check("retry %s: server history counts each boundary once" % label,
              r.rec_report.view_reset_budget, budget)
        check("retry %s: source-authorized resets retain independent faults" % label,
              (r.angles, bool(r.faults)), (expected, expected == "FAULT"))


def main():
    tests = (lambda: test_swap("view"), lambda: test_swap("hid"),
             lambda: test_swap("hid", broken_first=True), test_rec_swap,
             test_absent_arrives_between_phases, test_explicit_view_and_bad_digest,
             test_missing_view_and_io, test_selected_rec_tail_io,
             test_unsigned_sibling_io, test_parser_bytes,
             test_unavailable_angles_keep_view_faults, test_initial_clock_origin,
             test_retry_clock_faults)
    for test in tests:
        try:
            test()
        except Exception as exc:
            check("test ran to completion", "%s: %s" % (type(exc).__name__, exc), "no exception")
    print("\n%d checks, %d failed" % (CHECKS, len(FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
