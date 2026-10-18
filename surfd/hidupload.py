"""Signed, bounded journal delivery. No run verdicts or arbitrary destinations.

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
RATE_MAX = 12                 # per source/minute, separate from every other API
NAME = re.compile(r"[A-Za-z0-9_-]{1,96}\Z")
MAP = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,63}\Z")
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX128 = re.compile(r"[0-9a-f]{128}\Z")


def register(app, env, tools=None):
    # Flask <3.1 has no per-request max_content_length setter. A scoped
    # request subclass also keeps the existing 16 KiB ceiling on other APIs.
    base_request = app.request_class

    class JournalRequest(base_request):
        @property
        def max_content_length(self):
            if self.path == "/api/hid":
                return HEADER_SIZE + MAX_JOURNAL
            return super().max_content_length

    app.request_class = JournalRequest
    tools = tools or os.environ.get("SURFD_TOOLS", os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "tools"))
    if tools not in sys.path:
        sys.path.insert(0, tools)

    @app.post("/api/hid")
    def upload():
        if not env.rate_ok(env.rate_key(), env.clock(), cap=RATE_MAX, bucket="hid"):
            return env.fail("journal upload rate exceeded", 429)
        total = request.content_length
        if total is None or not HEADER_SIZE < total <= HEADER_SIZE + MAX_JOURNAL:
            return env.fail("bad journal request length", 413)
        if request.mimetype != "application/octet-stream":
            return env.fail("journal content type required", 415)

        temp = None
        try:
            header = request.stream.read(HEADER_SIZE)
            if len(header) != HEADER_SIZE or header[-1:] != b"\n":
                return env.fail("bad journal header", 400)
            lines = header.rstrip(b" \n").decode("ascii").split("\n")
            if len(lines) != 7 or lines[0] != "FTESURF-HID 1":
                return env.fail("bad journal header", 400)
            fields = []
            for line, key in zip(lines[1:], ("map", "runid", "nonce", "hid", "pub", "sig")):
                if not line.startswith(key + " "):
                    return env.fail("bad journal header fields", 400)
                fields.append(line[len(key) + 1:])
            mapname, runid, nonce, hid, pub, sig = fields
            digest, sep, length = hid.partition(" ")
            if (not MAP.fullmatch(mapname) or ".." in mapname
                    or not NAME.fullmatch(runid) or not HEX32.fullmatch(nonce)
                    or not HEX64.fullmatch(digest) or not HEX64.fullmatch(pub)
                    or not HEX128.fullmatch(sig) or not sep
                    or not re.fullmatch(r"[1-9][0-9]{0,7}", length)):
                return env.fail("bad journal identity", 400)
            size = int(length)
            if size > MAX_JOURNAL or size + HEADER_SIZE != total:
                return env.fail("journal length does not agree", 400)

            import ed25519
            import rcptcheck
            statement = ("\n".join(lines[:5]) + "\n").encode("ascii")
            if not ed25519.verify(bytes.fromhex(pub), statement, bytes.fromhex(sig)):
                return env.fail("journal signature refused", 403)

            directory = os.path.join(env.evidence(), mapname)
            receipt_path = os.path.join(directory, runid + ".rcpt")
            # The directories/files are server-owned, never created from a POST.
            # An unpublished/temporarily unreadable receipt is retryable, not an
            # assertion about the player's evidence.
            if os.path.getsize(receipt_path) > 8192:
                return env.fail("journal receipt unavailable", 503)
            receipt = rcptcheck.read(receipt_path)
            if receipt.ioerror:
                return env.fail("journal receipt unavailable", 503)
            if (receipt.ok is not True or receipt.faults
                    or receipt.head.get("runid") != runid
                    or receipt.head.get("pub") != pub
                    or rcptcheck.signed_get(receipt, "nonce") != nonce
                    or rcptcheck.signed_get(receipt, "hid") != "%s %s 1" % (digest, length)):
                return env.fail("journal does not match its receipt", 403)
            fd, temp = tempfile.mkstemp(prefix=".hid-", suffix=".part", dir=directory)
            remaining = size
            measured = hashlib.sha256()
            with os.fdopen(fd, "wb") as out:
                while remaining:
                    chunk = request.stream.read(min(65536, remaining))
                    if not chunk:
                        return env.fail("journal body truncated", 400)
                    measured.update(chunk)
                    out.write(chunk)
                    remaining -= len(chunk)
                if request.stream.read(1):
                    return env.fail("journal body too long", 400)
                out.flush()
                os.fsync(out.fileno())
            if measured.hexdigest() != digest:
                return env.fail("journal digest does not agree", 400)

            final = os.path.join(directory, runid + ".hid")
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
                        if got > MAX_JOURNAL:
                            break
                        existing.update(chunk)
                if got != size or existing.hexdigest() != digest:
                    return env.fail("stored journal differs; preserved", 409)
            return Response("stored %s %d\n" % (digest, size), mimetype="text/plain",
                            headers={"Cache-Control": "no-store"})
        except (UnicodeError, ValueError, BadRequest, RequestEntityTooLarge):
            return env.fail("malformed journal request", 400)
        except (OSError, ImportError) as exc:
            env.log.warning("journal upload unavailable (%s)", type(exc).__name__)
            return env.fail("journal upload temporarily unavailable", 503)
        finally:
            if temp is not None:
                try:
                    os.unlink(temp)
                except OSError as exc:
                    env.log.error("journal temporary cleanup failed (%s)", type(exc).__name__)
