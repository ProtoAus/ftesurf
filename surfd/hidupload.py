"""Signed, bounded journal (POST /api/hid) and run view (POST /api/view, P1704) delivery. No run verdicts or
arbitrary destinations.

Wire: a 1024-byte ASCII header (space padded, final newline), then the raw
journal. The first five header lines are the Ed25519 statement; pub/sig follow.
Only a server-written receipt can authorize a destination. Nothing becomes a
.hid until its length and digest agree with that receipt. Existing files never
get replaced, including a conflicting file which an operator must investigate.
"""
import hashlib
import os
import re
import sys
import tempfile

from flask import Response, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

HEADER_SIZE = 1024
MAX_JOURNAL = 64 * 1024 * 1024
# P1704: view sidecars come to POST /api/view (own nginx budgets) as `FTESURF-VIEW 1` statements that must carry
# exactly the receipt's signed view digest. The cap is the netchan route's (RCPT_ULMAX), so no longer run reaches the
# angle checker than before. A view is one ~40-byte line per rendered frame (cl_replay.qc Rec_ViewSample): 4 KiB per
# 66.67 Hz tick covers ~6800 fps.
MAX_VIEW = 4 * 1024 * 1024
VIEW_BASE_BYTES = 256 * 1024
VIEW_BYTES_PER_TICK = 4096
RATE_MAX = 12                 # journals per source/minute, separate from every other API
VIEW_RATE_MAX = 30            # views per source/minute
NAME = re.compile(r"[A-Za-z0-9_-]{1,96}\Z")
MAP = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,63}\Z")
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX128 = re.compile(r"[0-9a-f]{128}\Z")
# the client's netchan address string as rec_sign signs it, scheme included (dtls://, tls://, ws://...; rcptcheck)
SERVER = re.compile(r"[0-9A-Za-z.:\[\]%_/-]{1,127}\Z")


def _run_budget(setting):
    """No guessed policy: both explicit integer settings, or legacy admission."""
    values = [setting(name) for name in ("SURFD_HID_BASE_BYTES", "SURFD_HID_BYTES_PER_TICK")]
    if values == [None, None]:
        return None
    if any(not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]{0,7}", value)
           for value in values):
        raise ValueError("invalid journal run budget configuration")
    base, rate = map(int, values)
    if base > MAX_JOURNAL or not 0 < rate <= MAX_JOURNAL:
        raise ValueError("invalid journal run budget configuration")
    return base, rate


def _run_byte_limit(budget, ticks):
    if budget is None:
        return MAX_JOURNAL
    # Same positive integral signed finish clock; never infer wall/parked time.
    if not isinstance(ticks, str) or not re.fullmatch(r"[1-9][0-9]{0,10}", ticks):
        return None
    return min(MAX_JOURNAL, budget[0] + int(ticks) * budget[1])


def register(app, env, tools=None):
    run_budget = _run_budget(getattr(env, "setting", os.environ.get))
    # Flask <3.1 has no per-request max_content_length setter. A scoped
    # request subclass also keeps the existing 16 KiB ceiling on other APIs.
    base_request = app.request_class

    class JournalRequest(base_request):
        @property
        def max_content_length(self):
            if self.path == "/api/hid":
                return HEADER_SIZE + MAX_JOURNAL
            if self.path == "/api/view":
                return HEADER_SIZE + MAX_VIEW
            return super().max_content_length

    app.request_class = JournalRequest
    tools = tools or os.environ.get("SURFD_TOOLS", os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "tools"))
    if tools not in sys.path:
        sys.path.insert(0, tools)

    @app.post("/api/hid")
    def upload():
        return receive("hid")

    @app.post("/api/view")
    def upload_view():
        return receive("view")

    def receive(kind):
        cap = MAX_JOURNAL if kind == "hid" else MAX_VIEW
        where = [""]

        def fail(message, code):
            # P1704: every refusal that names a run is in the log with it (the netchan route's lobby log lines are
            # gone for these clients); one that names none is anyone's junk, kept out of the warning log
            (env.log.warning if where[0] else env.log.debug)("%s upload refused%s: %s (%d)", kind, where[0],
                                                             message, code)
            return env.fail(message, code)

        if not env.rate_ok(env.rate_key(), env.clock(), cap=RATE_MAX if kind == "hid" else VIEW_RATE_MAX,
                           bucket=kind):
            return env.fail("upload rate exceeded", 429)
        total = request.content_length
        if total is None or not HEADER_SIZE < total <= HEADER_SIZE + cap:
            return fail("bad journal request length", 413)
        if request.mimetype != "application/octet-stream":
            return fail("journal content type required", 415)

        temp = None
        try:
            header = request.stream.read(HEADER_SIZE)
            if len(header) != HEADER_SIZE or header[-1:] != b"\n":
                return fail("bad journal header", 400)
            lines = header.rstrip(b" \n").decode("ascii").split("\n")
            # a view's statement also names the server the run was signed on (P1704 review 3)
            keys = ("map", "runid", "nonce", "hid", "pub", "sig") if kind == "hid" else \
                ("server", "map", "runid", "nonce", "view", "pub", "sig")
            if len(lines) != 1 + len(keys) or lines[0] != ("FTESURF-HID 1" if kind == "hid" else "FTESURF-VIEW 1"):
                return fail("bad journal header", 400)
            fields = []
            for line, key in zip(lines[1:], keys):
                if not line.startswith(key + " "):
                    return fail("bad journal header fields", 400)
                fields.append(line[len(key) + 1:])
            server = fields.pop(0) if kind == "view" else None
            mapname, runid, nonce, hid, pub, sig = fields
            digest, sep, length = hid.partition(" ")
            if ((server is not None and not SERVER.fullmatch(server))
                    or not MAP.fullmatch(mapname) or ".." in mapname
                    or not NAME.fullmatch(runid) or not HEX32.fullmatch(nonce)
                    or not HEX64.fullmatch(digest) or not HEX64.fullmatch(pub)
                    or not HEX128.fullmatch(sig) or not sep
                    or not re.fullmatch(r"[1-9][0-9]{0,7}", length)):
                return fail("bad journal identity", 400)
            size = int(length)
            if size > cap or size + HEADER_SIZE != total:
                return fail("journal length does not agree", 400)

            import ed25519
            import rcptcheck
            statement = ("\n".join(lines[:len(keys) - 1]) + "\n").encode("ascii")
            if not ed25519.verify(bytes.fromhex(pub), statement, bytes.fromhex(sig)):
                return fail("journal signature refused", 403)

            directory = os.path.join(env.evidence(), mapname)
            receipt_path = os.path.join(directory, runid + ".rcpt")
            # The directories/files are server-owned, never created from a POST.
            # An unpublished/temporarily unreadable receipt is retryable, not an
            # assertion about the player's evidence.
            if not os.path.isdir(directory):
                # an empty or unreadable evidence root is a wrong deployment: retryable (a 410 for every run would cut
                # every lobby off for the session); with maps present, an unknown one is no such run (410: junk)
                try:
                    with os.scandir(env.evidence()) as entries:
                        populated = any(True for _ in entries)
                except OSError:
                    populated = False
                if not populated:
                    return fail("journal receipt unavailable", 503)
                return fail("no receipt for this run", 410)
            try:
                rsize = os.path.getsize(receipt_path)
            except FileNotFoundError:
                # P1704: the lobby writes the receipt before it asks, so nothing later will make one. Final: clients
                # now retry a 503, and junk or a community server's journals would be sent six times.
                # 410, not 403: "no such run" -- P1704 clients count it as junk.
                return fail("no receipt for this run", 410)
            if rsize > 8192:        # no receipt is this large: permanent (clients retry a 503)
                return fail("journal receipt unavailable", 403)
            receipt = rcptcheck.read(receipt_path)
            if receipt.ioerror:
                return fail("journal receipt unavailable", 503)
            committed = rcptcheck.signed_get(receipt, kind)
            if receipt.head.get("pub") == pub and receipt.head.get("runid") == runid:
                where[0] = " for %s/%s" % (mapname, runid)     # only the run's own key names it in the warning log
            if (receipt.ok is not True or receipt.faults
                    or receipt.head.get("runid") != runid
                    or receipt.head.get("pub") != pub
                    or rcptcheck.signed_get(receipt, "nonce") != nonce
                    or (kind == "hid" and committed != "%s %s 1" % (digest, length))
                    or (kind == "view" and not (isinstance(committed, str) and HEX64.fullmatch(committed)))):
                return fail("journal does not match its receipt", 403)
            if kind == "view" and rcptcheck.signed_get(receipt, "server") != server:
                # the run is not one this statement's server asked about: no such run on that server (410: junk to
                # a P1704 client; an honest one names the receipt's server)
                return fail("view statement names another server than its receipt", 410)
            if kind == "view" and committed != digest:
                # refused, as journals are: a stored mismatch reads as a FAULT, and a server's csprogs can arm a file
                # under a visitor's public nonce (review 2). An honest P1704 client cannot send one (rec_sign's pin),
                # so it is kept: <runid>.viewrefused, written once, for the review pages.
                try:
                    fd = os.open(os.path.join(directory, runid + ".viewrefused"),
                                 os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "w") as out:
                        out.write("FTESURF-VIEWREFUSED 1\noffered %s %d\nat %d\n" % (digest, size, int(env.clock())))
                except FileExistsError:
                    pass
                return fail("view does not match its receipt", 403)
            if kind == "hid":
                allowance = _run_byte_limit(run_budget, rcptcheck.signed_get(receipt, "ticks"))
                if allowance is None:   # an unfinished run's clock: permanent (clients retry a 503)
                    return fail("journal run budget unavailable", 403)
                if size > allowance:
                    return fail("journal exceeds configured run budget", 413)
            else:
                # a finished run only (an abandon's receipt asks for nothing), sized by its signed clock
                ticks = rcptcheck.signed_get(receipt, "ticks")
                if not isinstance(ticks, str) or not re.fullmatch(r"[1-9][0-9]{0,10}", ticks):
                    return fail("a view needs a finished run", 403)
                if size > min(MAX_VIEW, VIEW_BASE_BYTES + int(ticks) * VIEW_BYTES_PER_TICK):
                    return fail("view exceeds its run's budget", 413)
            fd, temp = tempfile.mkstemp(prefix="." + kind + "-", suffix=".part", dir=directory)
            remaining = size
            measured = hashlib.sha256()
            with os.fdopen(fd, "wb") as out:
                while remaining:
                    chunk = request.stream.read(min(65536, remaining))
                    if not chunk:
                        return fail("journal body truncated", 400)
                    measured.update(chunk)
                    out.write(chunk)
                    remaining -= len(chunk)
                if request.stream.read(1):
                    return fail("journal body too long", 400)
                out.flush()
                os.fsync(out.fileno())
            if measured.hexdigest() != digest:
                return fail("journal digest does not agree", 400)

            final = os.path.join(directory, runid + "." + kind)
            try:
                # Atomic NO-REPLACE publication. A retry/racing request cannot
                # overwrite already observed evidence, even with a good key.
                os.link(temp, final)
            except FileExistsError:
                existing = hashlib.sha256()
                got = 0
                with open(final, "rb") as old:
                    while True:
                        chunk = old.read(65536)
                        if not chunk:
                            break
                        got += len(chunk)
                        if got > cap:
                            break
                        existing.update(chunk)
                if got != size or existing.hexdigest() != digest:
                    return fail("stored journal differs; preserved", 409)
            env.log.info("stored %s%s (%d bytes)", kind, where[0], size)
            return Response("stored %s %d\n" % (digest, size), mimetype="text/plain",
                            headers={"Cache-Control": "no-store"})
        except (UnicodeError, ValueError, BadRequest, RequestEntityTooLarge):
            return fail("malformed journal request", 400)
        except (OSError, ImportError) as exc:
            env.log.warning("journal upload unavailable (%s)", type(exc).__name__)
            return fail("journal upload temporarily unavailable", 503)
        finally:
            if temp is not None:
                try:
                    os.unlink(temp)
                except OSError as exc:
                    env.log.error("journal temporary cleanup failed (%s)", type(exc).__name__)
