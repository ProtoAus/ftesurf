#!/usr/bin/env python3
"""
rcptcheck.py -- check a run receipt: the signature, and what it is over.

A receipt (Patch 417) is written by the server next to nothing -- it lives in
`data/evidence/<map>/<runid>.rcpt` on the machine that hosted the run, beside
the recordings and under the same retention -- and it says:
this client, holding this public key, signed a statement about the run's nonce,
its tick count and the SHA-256 of its own two evidence files.

WHAT THIS TOOL SAYS AND WHAT IT DOES NOT.  It answers one question exactly --
does the signature verify over the lines the file says were signed -- and then
makes every JOIN it can against the rest of the evidence: the .rec header this
receipt names (by runid), the two tick counts, the server it was signed on, and
THE UPLOADED FILES SITTING BESIDE IT, which it hashes and holds against the
digests that were signed.  That last one is the point of the exercise: it is
how "what arrived is what was committed to" stops being a claim.

AND THEN A THIRD QUESTION, WHICH THE FIRST TWO DO NOT REACH.  A valid signature
says a key made the statement.  A matching digest says the file beside it is the
file the statement was about.  Neither says the file has anything to do with the
run: a sidecar from a different run hashes perfectly well.  So the angles in the
.view are held against the angles in the .rec (reccheck.angle_join), which is
the failure Patch 418's review found live -- one run's journal filed beside
another run's angles -- and which is present twice in this tree's own corpus on
recordings nobody ever signed.  It does not
decide anything about a player.  A valid signature means the holder of that key
made that statement; it does not mean the statement is true, and no threat class
above a casual one is touched by it.  That sentence is in the engine source too.

THE SIGNED BYTES ARE REBUILT FROM THE FILE AND FROM NOTHING ELSE.  Every line
beginning `signed ` is stripped of that prefix and joined with newlines under
the version line, in file order, with a trailing newline -- which is exactly
what engine/client/cl_receipt.c hashes.  A receipt whose signed lines were
reordered or reformatted by anything in between will not verify, and that is the
intended behaviour rather than a fragility: the signature is over bytes.

Usage:
    python tools/rcptcheck.py <file.rcpt | directory> [...]
    python tools/rcptcheck.py --hid <f.hid> --view <f.view> <file.rcpt>
    python tools/rcptcheck.py --tamper <file.rcpt>   # the negative control
    python tools/rcptcheck.py --selftest
"""

import glob
import hashlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ed25519

SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(SURFDIR, "ftesurf")


class Receipt(object):
    def __init__(self, path):
        self.path = path
        self.faults = []
        self.notes = []
        self.head = {}
        self.signed = []            # (key, value) in file order
        self.first = ""             # the version line, verbatim
        self.msg = b""
        self.ok = None
        self.recpath = None         # the .rec join_rec found, for join_angles
        self.recdata = None
        # One observation per path for this report, including absence/read errors.
        self.file_bytes = {}
        self.file_present = set()
        self.digest_checked = set()
        self.ioerror = False        # a file could not be read: nothing was measured
        self.digest_bad = {}        # kind -> the fault, for a sibling that is not what was signed
        # join_angles' result as a word: "" (not checked), OK, BLIND or FAULT,
        # with the measurement beside it.  A CALLER MUST NOT HAVE TO MATCH ON
        # THE WORDING OF A NOTE -- sweep.py stores this, and a note is prose
        # that gets reworded.
        self.angles = ""
        self.angles_detail = ""
        # The journal's CONTENT verdict, and the same rule about wording: a
        # caller must not have to match on prose.  "" = not checked, ABSENT =
        # no journal beside this receipt, OK, FAULT, or BLIND = no fault, but
        # frames the identity could not attribute (teleports among them) or no
        # frame it could judge at all.  This is NOT the digest
        # check -- join_uploaded already hashes <runid>.hid against what the
        # signature committed to.  It is what hidcheck says about the file's own
        # contents: whether the angles in it could have come from the device
        # counts it recorded.
        self.journal = ""
        self.journal_detail = ""
        # ABSENT, and the receipt signs a kept journal's digest: it may still be
        # uploading.  sweep.py reads this to hold the row PENDING.
        self.journal_owed = False

    def fault(self, m):
        self.faults.append(m)

    def note(self, m):
        self.notes.append(m)


def read(path):
    r = Receipt(path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError as e:
        r.fault("cannot read: %s" % e)
        r.ioerror = True
        return r

    # THE VERSION LINE IS TAKEN VERBATIM, not parsed and re-rendered.  The first
    # cut rebuilt it as "FTESURF-RCPT %d" from an int(), so `FTESURF-RCPT 01`
    # and `FTESURF-RCPT 1 anything` both verified against bytes the file did not
    # contain -- which contradicts this tool's own headline rule.
    if not lines or lines[0] != "FTESURF-RCPT 1":
        r.fault("first line is %r, not the one version this tool reads"
                % (lines[0] if lines else ""))
        return r
    r.head["version"] = 1
    r.first = lines[0]

    for ln in lines[1:]:
        if not ln.strip():
            continue
        if ln.startswith("signed "):
            body = ln[7:]
            k, _sp, v = body.partition(" ")
            r.signed.append((k, v))
        else:
            k, _sp, v = ln.partition(" ")
            r.head[k] = v

    for k in ("pub", "sig", "runid"):
        if k not in r.head:
            r.fault("missing %r" % k)

    # EXACTLY THESE FIVE, ONCE EACH, IN THIS ORDER.  The first cut verified
    # whatever `signed ` lines it found, so a receipt with NONE AT ALL -- a
    # signature over the version line and nothing else -- reported VALID, and
    # --tamper had nothing to tamper with and passed too.  A statement about no
    # run read exactly like a statement about a run.
    want = ["server", "nonce", "ticks", "hid", "view"]
    got = [k for k, _v in r.signed]
    if got != want:
        r.fault("the signed block is %s; a receipt signs exactly %s, in that order"
                % (got or "empty", " ".join(want)))
    if r.faults:
        return r

    # THE MESSAGE, rebuilt.  Version line, then each signed line with its prefix
    # removed, each newline-terminated.
    text = r.first + "\n"
    for k, v in r.signed:
        text += "%s %s\n" % (k, v)
    r.msg = text.encode("utf-8")

    try:
        pub = bytes.fromhex(r.head["pub"])
        sig = bytes.fromhex(r.head["sig"])
    except ValueError:
        r.fault("pub or sig is not hex")
        return r
    if len(pub) != 32:
        r.fault("pub is %d bytes, not 32" % len(pub))
    if len(sig) != 64:
        r.fault("sig is %d bytes, not 64" % len(sig))
    if r.faults:
        return r

    # A SMALL-ORDER KEY VERIFIES EVERYTHING.  ed25519.verify refuses it, but the
    # refusal would read as "bad signature" -- and this one is not a bad
    # signature, it is a key that is not an identity.  Said separately because a
    # reader acts differently on the two.
    if ed25519.small_order(pub):
        r.fault("the public key has small order -- a key anybody can sign under, "
                "so it names nobody")
        return r

    r.ok = ed25519.verify(pub, r.msg, sig)
    if not r.ok:
        r.fault("SIGNATURE DOES NOT VERIFY over the lines this file says were signed")
    return r


def signed_get(r, key):
    for k, v in r.signed:
        if k == key:
            return v
    return None


def file_bytes(r, path):
    """Capture once; a later join must not observe replacement or new arrival."""
    if path not in r.file_bytes:
        try:
            with open(path, "rb") as fh:
                r.file_present.add(path)
                r.file_bytes[path] = fh.read()
        except FileNotFoundError as exc:
            r.file_bytes[path] = exc if path in r.file_present else None
        except OSError as exc:
            # Even if opening bytes is denied, stat may independently establish
            # a stored sibling that contradicts a missing signed digest.
            try:
                os.stat(path)
            except OSError:
                pass
            else:
                r.file_present.add(path)
            r.file_bytes[path] = exc
    data = r.file_bytes[path]
    if isinstance(data, OSError):
        raise data
    return data


def join_rec(r):
    """Join the receipt to the .rec it names, when that file is on this disk."""
    runid = r.head.get("runid", "")
    mapname = r.head.get("map", "")
    if not runid or not mapname:
        return
    # BOTH TREES.  `data/runs/<map>/<leg>/` is where a kept run is archived;
    # `data/evidence/<map>/<runid>.rec` is where an abandoned or stage-posting
    # run's recording goes -- and the receipt sits in that same directory, so on
    # a host it is the FIRST place to look rather than one the tool did not know.
    hits = glob.glob(os.path.join(GAME, "data", "evidence", mapname, "*.rec"))
    for leg in ("main", "stage_*", "bonus_*"):
        hits += glob.glob(os.path.join(GAME, "data", "runs", mapname, leg, "*.rec"))
    for path in hits:
        selected = False
        try:
            # Unrelated recordings cost only a header scan, as before. Capture
            # the selected one's remaining text BEFORE closing this same handle.
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                head, prefix = {}, []
                for ln in fh:
                    prefix.append(ln)
                    if ln.strip() == "begin":
                        break
                    k, _sp, v = ln.strip().partition(" ")
                    head[k] = v
                if head.get("runid") != runid:
                    continue
                selected = True
                text = "".join(prefix) + fh.read()
        except OSError as exc:
            if selected:
                # The matched recording exists, but its session nonce/angles
                # are unmeasured. Do not silently store a permanent VALID row.
                r.ioerror = True
                r.note("the selected .rec read is deferred (%r)" % exc)
                return
            continue
        # No digest covers the .rec; its decoded observation is shared by the
        # nonce and angle readers. Re-encoding preserves replacement/newlines.
        with io.StringIO(text, newline=None) as fh:
            lines = list(fh)
        r.note("joined %s" % os.path.relpath(path, GAME))
        r.recpath = path
        r.recdata = text.encode("utf-8")
        want = signed_get(r, "nonce")

        # A FILE CAN STATE MORE THAN ONE NONCE AND THE RECEIPT SIGNS THE LAST.
        # The header's belongs to session one; a Multi-Session resume writes a
        # `nonce <mt> <hex>` RECORD for each later session, and the client that
        # finished the run holds -- and signs -- whichever was last issued.
        # Comparing against the header alone faulted every resumed run, which is
        # how this was found: the tool was wrong, the receipt was right.
        stated = []
        if "nonce" in head:
            stated.append((0, head["nonce"], "header"))
        body = False
        for ln in lines:
            if not body:
                body = ln.strip() == "begin"
                continue
            f = ln.split()
            if len(f) == 3 and f[0] == "nonce":
                stated.append((len(stated), f[2], "session %d" % (len(stated) + 1)))

        if not stated:
            r.note("the .rec states no nonce (a recording older than Patch 416)")
        elif want == stated[-1][1]:
            r.note("nonce agrees with the .rec (%s, the one in force at the "
                   "finish)" % stated[-1][2])
        elif any(want == s[1] for s in stated):
            which = [s[2] for s in stated if s[1] == want][0]
            r.fault("the receipt signs the nonce of %s, and the file states a "
                    "later one -- the run was resumed after this was signed"
                    % which)
        else:
            r.fault("the .rec states %s and the receipt signs %r"
                    % (", ".join("%s %s" % (s[2], s[1]) for s in stated), want))
        return
    r.note("no .rec with this runid on this disk (normal off the host)")


def join_ticks(r):
    """The client's tick count against the server's own.

    THE BEST IDEA IN THE PATCH AND IT WAS NOT BEING USED: the server records
    both, precisely so a reader can see them disagree, and nothing compared
    them.  -1 on both sides is the ordinary answer for a run the server did not
    keep, and is not a finding.
    """
    a = signed_get(r, "ticks")
    b = r.head.get("svticks")
    if a is None or b is None:
        return
    if a == b:
        r.note("ticks agree with the server (%s)" % a)
    else:
        r.fault("the client signed ticks %s and this server counted %s" % (a, b))


def join_server(r, expect):
    """The address the client signed, against what it should have been.

    This is the line that makes a signature non-portable, and it can only be
    checked by somebody who knows which server wrote the receipt -- so the
    expectation is given on the command line (the sweeper knows its own
    lobbies).  Without one, the value is REPORTED and the absence of a check is
    said out loud rather than passed over in silence.
    """
    got = signed_get(r, "server")
    if got is None:
        return
    if not expect:
        r.note("signed on %r -- no --server given, so nothing checked it" % got)
    elif got == expect:
        r.note("signed on %r, which is this server" % got)
    else:
        r.fault("signed on %r, but this receipt was written by %r -- a signature "
                "made on one server is not a receipt on another" % (got, expect))


def join_hid(r):
    """Check the committed journal digest against the file, when there is one."""
    v = signed_get(r, "hid")
    if not v or v.startswith("-"):
        r.note("no journal digest in this receipt")
        return
    f = v.split()
    if len(f) != 3:
        r.fault("`signed hid` takes <sha256|-> <bytes> <kept>, has %d field(s)" % len(f))
        return
    digest, nbytes, kept = f[0], f[1], f[2]
    if kept != "1":
        r.note("the journal was not kept (%s bytes committed to, discarded at the "
               "end of the run)" % nbytes)
        return
    # The path is not in the receipt -- the server never knew it -- so this only
    # runs when the caller points us at a file with --hid.
    r.note("journal kept, %s bytes, sha256 %s..." % (nbytes, digest[:16]))


def join_uploaded(r, want):
    """Hash the evidence that was uploaded BESIDE this receipt.

    THIS IS THE CHECK THE WHOLE THING IS FOR, and until the review it only ran
    when an operator typed a path by hand -- so the property every comment
    claimed ("what arrives can be checked against what was committed to") was
    asserted everywhere and tested nowhere.  A receipt at
    data/evidence/<map>/<runid>.rcpt sits beside <runid>.view and <runid>.hid
    when Patch 418's upload landed; those are the files to hash, and no operator
    should have to know that.

    An ABSENT sibling is not a fault: the upload is off by default for journals,
    a client can decline, a run can produce no sidecar, and a receipt copied
    away from its host has neither.  A sibling that does not match IS one.
    """
    base = os.path.splitext(r.path)[0]
    for key in ("view", "hid"):
        if key in want:
            continue            # the caller named one explicitly; that wins
        path = base + "." + key
        try:
            data = file_bytes(r, path)
        except OSError as exc:
            # The CLI must still exit nonzero. sweep distinguishes ioerror
            # from independently measured faults, not by diagnostic wording.
            r.ioerror = True
            if path in r.file_present:
                check_file(r, key, path, sibling=True)
            else:
                r.fault("--%s %s: %s" % (key, path, exc))
            continue
        if data is None:
            # ABSENT IS NOT A FAULT, BUT IT IS NOT NOTHING EITHER.  A receipt
            # that signs a real digest and has no file beside it is the only
            # on-disk trace of "the client committed to evidence and did not
            # hand it over" -- and until this said so, a client that declined
            # every upload looked exactly like a host with uploads switched
            # off.  `signed <kind> -` means there was nothing to send; a digest
            # with no file means it did not arrive.
            want_d = (signed_get(r, key) or "").split(" ")[0]
            if want_d and want_d != "-":
                if os.path.exists(path + ".part"):
                    r.note("%s.part is here but was never renamed into place -- "
                           "an upload that did not finish, not a mismatch"
                           % os.path.basename(path))
                else:
                    r.note("commits to a %s digest, and no %s is on this host"
                           % (key, key))
            continue
        check_file(r, key, path, sibling=True)


def join_angles(r, want):
    """Does the .view the digest names describe the .rec the runid names?

    IMPORTED LAZILY AND WRAPPED, because this is the one check here that depends
    on another tool: reccheck owns both grammars and re-parsing them in this
    file would give the tree a second reader to keep in step.  A receipt whose
    angles could not be checked still reports everything else it knows -- the
    alternative is a verifier that returns nothing about a file because one of
    its five questions could not be asked.
    """
    if not r.recpath:
        return
    view = want.get("view") or (os.path.splitext(r.path)[0] + ".view")
    try:
        data = file_bytes(r, view)
        if data is None:
            return
        if ("view", view) not in r.digest_checked:
            check_file(r, "view", view, sibling=("view" not in want))
        if "view" in r.digest_bad:
            r.angles = "FAULT"
            r.angles_detail = "not the sidecar the receipt signed: %s" % r.digest_bad["view"]
            return
        import reccheck
        rec = reccheck.check_rec(r.recpath, data=r.recdata)
        v = reccheck.check_view(view, rec, data=data)
    except OSError as exc:
        r.ioerror = True
        r.note("the angle cross-check is deferred (%r)" % exc)
        return
    except Exception as exc:
        r.note("the angle cross-check did not run (%r)" % exc)
        return

    off = v.info.get("angle_off")
    if off is None:
        # NOT COMPARABLE IS NOT A PASS.  If the sidecar is unreadable enough
        # that no join happened at all -- no frames, a tick past the end of the
        # recording, a clock that runs backwards -- then the file this receipt
        # COMMITS TO is broken, and reporting "no angle stream" leaves the
        # receipt VALID with an empty verdict.  The subject is the sidecar.
        if v.faults:
            r.angles = "FAULT"
            r.angles_detail = v.faults[0]
            r.fault("the signature is over this .view and the .view hashes to "
                    "the digest that was signed, but the .view cannot be read "
                    "against the recording at all: %s" % v.faults[0])
            return
        r.note("the recording carries no angle stream to check the sidecar against")
        return
    solo = v.info.get("angle_solo", "")
    detail = [off] + ([solo] if solo else [])
    detail.extend(n for n in v.notes if n.startswith("the tight angle rule did not judge this pair:"))
    r.angles_detail = "; ".join(detail)
    bad = [m for m in v.faults if "does not describe this recording" in m
           or "does not match its sidecar" in m
           or "the sidecar is not this recording's" in m]
    # BLIND IS ABOUT THE SWEEP RULE ONLY.  Nearly every run the fleet records
    # has a still camera, so reporting BLIND whenever the sweep rule abstained
    # would put that word on the whole board while the one-frame rule was
    # quietly doing the work.  Ask whether ANY rule had something to say.
    # A v9 PAIR THE TIGHT RULE DID NOT REACH IS NOT `OK`.  `solo` is present
    # exactly when the recording is v9, and the sweep rule's own blindness is a
    # separate question from the tight rule's coverage: a SWEPT run whose
    # sidecar pads every tick used to come back a plain OK here, with nothing
    # examined at 0.05 deg and the loose rule's documented hole wide open.
    # ASKED AS A KEY.  This used to sniff `angle_off` for a "BLIND" prefix,
    # and when reccheck reworded that line the branch went dead: every pair the
    # tight rule never judged -- which is most of them -- came back a confident
    # OK.  reccheck now says which rule decided, in one word.
    blind = v.info.get("angle_rule", "sweep-only") != "tight"
    r.angles = "FAULT" if bad else ("BLIND" if blind else "OK")
    if bad:
        # SAID IN FULL, because the three facts TOGETHER are the finding and any
        # one of them alone reads as something milder.
        r.fault("the signature is over this .view, the .view hashes to the "
                "digest that was signed, AND the .view does not describe this "
                "recording: %s" % bad[0].split(": ", 1)[-1])
    elif r.angles == "BLIND":
        r.note("angles: %s" % r.angles_detail)
    elif off.startswith("BLIND"):
        r.note("the sidecar's angles are the recording's angles on every tick "
               "that held one frame -- %s" % solo)
    else:
        r.note("the sidecar's angles are the recording's angles -- %s" % off)


def join_journal(r):
    """Run hidcheck over the sibling .hid and hold its verdict.

    WHY THIS IS SEPARATE FROM join_uploaded, WHICH ALREADY LOOKS AT THIS FILE.
    join_uploaded hashes <runid>.hid against the digest the signature commits
    to, which answers "is this the journal the client signed".  It cannot answer
    "could this journal have been produced by a real device", and that is a
    different question with a different failure: a journal that was written by a
    tool rather than by a mouse hashes perfectly.

    hidcheck is the only tool in the tree that asks it -- the angle identity
    (Patch 293/305, both axes since the pitch check), the raw-injection counters
    (Patch 306/311), the counts join (Patch 312) and the device-provenance table
    (Patch 303) -- and until this existed it had NO CALLER OUTSIDE tools/ and
    cfg/test/.  The journal was hash-bound by the receipt and content-checked by
    nobody.

    A FAULT HERE DOES NOT MOVE THE RECEIPT'S VERDICT, deliberately.  The
    signature is over the digests and it did verify; what is broken is the file's
    contents, which is a finding about the RUN and belongs in its own column
    where a reviewer can weigh it.  Folding it into `verdict` would make a
    journal-content fault indistinguishable from a signature that did not verify,
    and would move a badge on the strength of a check whose false-positive rate
    on journals nobody has collected yet (run_evidence_ul is 1 on the fleet, so
    the fleet holds ZERO .hid files) has not been measured in the field.
    """
    base = os.path.splitext(r.path)[0]
    path = base + ".hid"
    try:
        data = file_bytes(r, path)
    except OSError as exc:
        r.ioerror = True
        r.note("the journal content check is deferred (%r)" % exc)
        return
    if data is None:
        # Not a fault and not nothing: `run_evidence_ul 1` takes the .view only,
        # so an absent journal is the normal case on a lobby today.  ABSENT is
        # the word that says the content question was never asked -- and it gets
        # a reason too, because "" in the reason column is what an unmigrated row
        # carries, and a reader must be able to tell "this sweep asked and there
        # is no journal here" from "no sweep ever asked".
        r.journal = "ABSENT"
        r.journal_detail = "no journal beside this receipt"
        f = (signed_get(r, "hid") or "").split()
        r.journal_owed = len(f) == 3 and f[0] != "-" and f[2] == "1"
        return
    if ("hid", path) not in r.digest_checked:
        check_file(r, "hid", path, sibling=True)
    if "hid" in r.digest_bad:
        r.journal = "FAULT"
        r.journal_detail = "not the journal the receipt signed: %s" % r.digest_bad["hid"]
        return
    try:
        # Lazy and wrapped exactly as join_angles does it: hidcheck lives beside
        # this file, and the sweep puts this directory on sys.path before it
        # imports rcptcheck at all.  A host that has rcptcheck but not hidcheck
        # still reports everything else the receipt knows.
        import hidcheck
        h = hidcheck.check_hid(path, data=data)
    except Exception as exc:
        # A journal too broken to parse is a finding about the file, but this
        # function must not take the receipt step down with it -- the sweep's own
        # rule, and the reason its imports are inside functions at all.
        r.journal = ""
        r.note("the journal content check did not run (%r)" % exc)
        return
    r.journal_detail = (h.info.get("identity") or "")
    pitch = h.info.get("identity_pitch")
    if pitch:
        r.journal_detail = "%s; pitch %s" % (r.journal_detail, pitch)
    if "identity_mouse_frames" in h.info:
        coverage = "mouse counts on %d/%d judged frames (%.2f%%); longest no-mouse span %d frames" % (
            h.info["identity_mouse_frames"], h.info.get("identity_judged", 0),
            h.info["identity_mouse_pct"], h.info["identity_no_mouse_longest"])
        r.journal_detail = "%s; %s" % (coverage, r.journal_detail) \
            if r.journal_detail else coverage
    unresolved = h.info.get("identity_unresolved") or 0
    if unresolved and "identity_unresolved_runs" in h.info:
        continuity = "unresolved spans %d, longest %d frames" % (
            h.info["identity_unresolved_runs"], h.info["identity_unresolved_longest"])
        r.journal_detail = "%s; %s" % (continuity, r.journal_detail)
        # Keep measurements before prose: the sweep retains the first 300 chars.
    if h.faults:
        r.journal = "FAULT"
        # The sweep stores 300 chars. Leave room for the numeric diagnostics;
        # keep the original fault note below and the FAULT verdict unchanged.
        fault_summary = h.faults[0]
        if len(fault_summary) > 96:
            fault_summary = fault_summary[:93] + "..."
        r.journal_detail = "%s | %s" % (fault_summary, r.journal_detail)
        r.note("the journal beside this receipt does not hold up: %s"
               % h.faults[0][:300])
    elif unresolved or not h.info.get("identity_judged") or h.info.get("identity_blind"):
        # THE THIRD VERDICT.  A teleport and a whole-angle rewrite are the same
        # bytes here, and a journal the identity judged nothing in has measured
        # nothing: neither is guilty, and neither is OK.
        r.journal = "BLIND"
        why = ("%d frame(s) unresolved (%d moved both axes)"
               % (unresolved, h.info.get("identity_whole") or 0)
               if unresolved else h.info.get("identity_blind")
               or "no frame the identity could judge")
        r.journal_detail = "%s | %s" % (why, r.journal_detail) \
            if r.journal_detail else why
        r.note("the journal beside this receipt has no fault, and %s" % why)
    else:
        r.journal = "OK"
        r.note("the journal beside this receipt holds up -- %s"
               % r.journal_detail)


def check_file(r, key, path, sibling=False):
    """Hash a file the caller points at and hold it against what was signed.

    THE PATHS ARE NOT IN THE RECEIPT and cannot be: the server never knew where
    this client put its files, and a receipt that named a path on somebody
    else's disk would be stating something it cannot know.  So the join is the
    caller's to make, which is also the only honest way round -- whoever holds
    the file says which file they mean."""
    r.digest_checked.add((key, path))
    v = signed_get(r, key)
    if not v or not v.split():
        r.fault(("a %s is stored under this run's name and the receipt signs no "
                 "%s digest" % (key, key)) if sibling else
                ("--%s given but this receipt signs no %s digest" % (key, key)))
        r.digest_bad[key] = r.faults[-1]
        return
    digest = v.split()[0]
    if digest == "-":
        r.fault(("a %s is stored under this run's name and the receipt's %s "
                 "digest is absent" % (key, key)) if sibling else
                ("--%s given but this receipt's %s digest is absent" % (key, key)))
        r.digest_bad[key] = r.faults[-1]
        return
    try:
        data = file_bytes(r, path)
        if data is None:
            raise FileNotFoundError(path)
    except OSError as e:
        r.fault("--%s %s: %s" % (key, path, e))
        r.ioerror = True
        return
    got = hashlib.sha256(data).hexdigest()
    if got != digest:
        r.fault("%s hashes to %s, the receipt commits to %s"
                % (os.path.basename(path), got[:16], digest[:16]))
        r.digest_bad[key] = r.faults[-1]
    else:
        r.note("%s matches the committed digest (%d bytes)"
               % (os.path.basename(path), len(data)))


def report(r, verbose=False):
    name = os.path.basename(r.path)
    if r.ok is True and not r.faults:
        print("ok   %-40s signature VALID  (%s)" % (name, r.head.get("pub", "")[:16]))
    else:
        print("FAIL %-40s" % name)
    for m in r.faults:
        print("     ! %s" % m)
    if verbose:
        for m in r.notes:
            print("     - %s" % m)


def tamper(path):
    """THE NEGATIVE CONTROL.  A checker that always said VALID would pass every
    arm above; this is the one that says otherwise.  Each signed line is altered
    in turn, on a copy in memory, and every one of them must break the
    signature."""
    r = read(path)
    if r.ok is not True:
        print("%s does not verify to begin with; nothing to control" % path)
        return 1
    if not r.signed:
        print("%s signs nothing, so there is nothing to tamper with -- which is "
              "itself the finding" % path)
        return 1
    bad = 0
    for i, (k, v) in enumerate(r.signed):
        text = "FTESURF-RCPT %d\n" % r.head["version"]
        for j, (k2, v2) in enumerate(r.signed):
            val = (v2 + "0") if i == j else v2
            text += "%s %s\n" % (k2, val)
        ok = ed25519.verify(bytes.fromhex(r.head["pub"]), text.encode("utf-8"),
                            bytes.fromhex(r.head["sig"]))
        print("  tampered %-8s -> %s" % (k, "STILL VALID -- BAD" if ok else "invalid, as it must be"))
        if ok:
            bad += 1
    print("%d of %d tampered variants still verified" % (bad, len(r.signed)))
    return 1 if bad else 0


def main(argv):
    verbose = "-v" in argv or "--verbose" in argv
    argv = [a for a in argv if a not in ("-v", "--verbose")]

    if "--selftest" in argv:
        return ed25519.selftest()
    if "--tamper" in argv:
        argv.remove("--tamper")
        if not argv:
            print("--tamper needs a receipt")
            return 1
        return tamper(argv[0])

    want = {}
    for key in ("hid", "view", "server"):
        if "--" + key in argv:
            i = argv.index("--" + key)
            if i + 1 >= len(argv):
                print("--%s needs a value" % key)
                return 1
            want[key] = argv[i+1]
            del argv[i:i+2]

    files = []
    # Receipts live beside the evidence they attest, so the sweeper's retention
    # covers them; with no argument, look through every map's directory.
    default = sorted(glob.glob(os.path.join(GAME, "data", "evidence", "*")))
    for a in argv or (default or [os.path.join(GAME, "data", "evidence")]):
        if os.path.isdir(a):
            # RECURSIVE, because the natural thing to type is the top of the
            # tree and receipts live one level down in data/evidence/<map>/.
            # Pointed at the parent, the non-recursive glob printed "no
            # receipts" and returned 1 -- a verifier that reports nothing wrong
            # because it looked in the wrong place.
            files += sorted(glob.glob(os.path.join(a, "**", "*.rcpt"),
                                      recursive=True))
        else:
            files.append(a)
    if not files:
        print("no receipts")
        return 1

    bad = 0
    missing = 0
    deferred = 0
    for f in files:
        r = read(f)
        join_rec(r)
        join_ticks(r)
        join_server(r, want.get("server"))
        join_hid(r)
        for key, path in want.items():
            if key != "server":
                check_file(r, key, path)
        join_uploaded(r, want)
        # AFTER join_uploaded, not before: "this file matches the digest and
        # still is not this run" is a different sentence from "some file here
        # is not this run", and the order is what makes the first one sayable.
        join_angles(r, want)
        report(r, verbose)
        if r.faults:
            bad += 1
        if r.ioerror:
            deferred += 1
        if any("and no " in m for m in r.notes):
            missing += 1
    print("%d receipt(s) checked, %d with faults" % (len(files), bad))
    if missing:
        # COUNTED IN THE SUMMARY AND NOT ONLY UNDER -v, because it is the line
        # that distinguishes a host with uploads off from a client that signs
        # digests and hands nothing over.  It is not a fault: an upload can
        # legitimately not arrive, and a receipt without its files is still a
        # complete receipt.
        print("%d of them commit to evidence that is not on this host" % missing)
    if deferred:
        print("%d receipt read(s) deferred after I/O; some content is unmeasured" % deferred)
    return 1 if bad or deferred else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
