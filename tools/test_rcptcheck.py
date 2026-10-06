"""Receipt snapshot falsifiers. Only generated evidence in throwaway homes.

A close-time swap proves the path actually changed AFTER the captured read.
The verdict must describe those captured bytes, not a later open of that path.
"""
import builtins
import contextlib
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
        "\nend\n", "\nnonce 1 " + "0" * 32 + "\nend\n").encode("utf-8")
    rp, _pub = fx.make_receipt(surfd.EVIDENCE_DIR, rid, view=view.encode("utf-8"))
    rc = fx.with_rec(surfd, sweep, rid, rec)
    path = os.path.join(rc.GAME, "data", "evidence", "bhop_eazy", rid + ".rec")
    try:
        with swap_after_close(path, replacement) as state:
            got = sweep.read_receipt(rp)
        check("rec swap: replacement ACTED", state["swaps"], 1)
        check("rec swap: identity, nonce and angles share one read", state["reads"], 1)
        check("rec swap: original nonce and angles still describe captured rec",
              got[:4], ("VALID", got[1], got[2], "OK"))
        check("rec swap: CONTROL next observation catches changed nonce",
              sweep.read_receipt(rp)[0], "FAULT")
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


def main():
    tests = (lambda: test_swap("view"), lambda: test_swap("hid"),
             lambda: test_swap("hid", broken_first=True), test_rec_swap,
             test_absent_arrives_between_phases, test_explicit_view_and_bad_digest,
             test_missing_view_and_io, test_parser_bytes)
    for test in tests:
        try:
            test()
        except Exception as exc:
            check("test ran to completion", "%s: %s" % (type(exc).__name__, exc), "no exception")
    print("\n%d checks, %d failed" % (CHECKS, len(FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
