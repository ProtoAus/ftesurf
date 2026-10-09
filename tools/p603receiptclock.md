# Patch 603 — bind finished receipt ticks to the captured recording

## Outcome and limits

A new positive finished-run receipt observation compares the cryptographically
signed tick count with the selected recording's readable, exact integral finish.
The former signed-ticks / unsigned-svticks comparison is retained. A different
recording duration is a **content FAULT**, while the independent signature-valid
bit and actual angle result remain intact. This is not a cheating verdict.

The writer's `-1` unkept and `0` abandon latches are NOT recording durations.
Off-host absence and unreadable, malformed, nonintegral or unsupported counters
remain unavailable under the existing receipt policy, not manufactured clocks.
A valid signature alone still does not certify those unavailable associations.
No new history reread, rank/owner-review policy, detector threshold/calibration,
schema, receipt/recording wire format, engine/QC/progs/config or Build change.

`join_rec` owns this check, so new full, rec-only and view-only observations use
it; journal-only retry does not rejudge historical recording content. Duration
and angles share the same captured bytes and one `reccheck` grammar parse. A
new recording capture invalidates that observation's parser cache.

Exact finish ticks are a separate initialized report attribute, not a header
key. Decimal parsing of the raw trailer prevents binary64 rounding from turning
near-integral fractions into facts. This optional assertion accepts finite exact
integers from0 through2147483647, including the writer's exponent notation, with
a128-character token cap. Existing float projections and grammar verdicts remain.
These local bounds are not total reader I/O/RSS/time or whole-file size bounds.

## Controls and verification

Preregistered genuine-signature controls compare matching and differing positive
receipt/recording clocks while all identity/nonce/view fields match. Eight of the
initial12 controls fail on the untouched baseline. Final18 tests include:

- Matching positive finished clock retains VALID, signature1, anglesOK, with an
  acting crypto/reader control and one shared parse.
- Both mismatch directions and real SQLite sweep store contentFAULT/signature1/
  anglesOK; original unsigned-server clock mismatch survives.
- -1, zero abandon and off-host absence keep their existing meaning.
- Readable legacy trailers participate; missing/fractional trailers abstain.
- Close-time substitution, fresh later observation and same-report recapture
  exercise the snapshot/cache boundary, not just helper arithmetic.
- Full/rec-only/view-only bind; journal-only does not rejudge an old recording.
- CLI exposes content mismatch without calling the valid signature invalid.
- Unknown header collision, near-integer decimal fraction, finite/range/token
  boundaries and exponent notation have explicit controls.

Initial independent source review found header-name collision and float-rounding
issues; both were corrected and the added controls act. Same-reviewer follow-up
closes both findings with no remaining issues. Review is read-only, not an
independent execution/deployment attestation.

Focused commands from the isolated source checkout:

```text
python tools/test_receipt_ticks.py
python tools/test_rcptcheck.py
python tools/test_reccheck.py
python surfd/test_sweep.py
python surfd/test_receipt_angle_reasons.py
python -W error -m py_compile tools/rcptcheck.py tools/reccheck.py tools/test_receipt_ticks.py
```

Focused18, receipt74 and recorder306 pass; sweep and angle-reason controls pass.
Full boundary is every fixture-free surfd/test_*.py except input-dependent
momindex, plus11 evidence-tool programs including the new receipt clock suite.
Final Linux71 programs pass; Windows71 retain only the two established admin UDP
assertions. The first full boundary preceded review corrections and is retained;
the final changed-code boundary reran both platforms and the fresh immutable corpus.
Both269 rec/prefix and91 paired-view reports retain170 faulted files/173 faults,
baseline and subject equal; source/copy hashes match. No unchanged engine/QC binary
build is claimed or needed for this reader-only fix.

## Publication/deployment

Exact inspected commits, UTC, selected destination hashes, acting installed-reader
controls, completed backup/rollback and preserved live history/process/health are
recorded here after verification. Ship only the two owned readers and their test;
do not ship a peer's uncommitted source.

The primary Windows `tools/rcptcheck.py` is peer-modified and must not be overwritten.
That install is blocked until the peer integrates the change. Secondary Windows
and Pi eligibility and actual installed controls are separate gates. No game,
progs/config/engine swap, owner-process restart or release is in this batch.
