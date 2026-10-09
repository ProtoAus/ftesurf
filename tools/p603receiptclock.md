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

Exact product `7e24d9d92fcecc679690ca926ebb3ec5a6d7c504` and changelog-only engine
`2d3394a6874191880966144dcd89823678836bc7` were inspected and pushed by exact SHA.
Frozen clean-tree source review confirms that product identity. The467-file final
staging manifest differs after unpublished upstream rebase only in the unrelated
pi.dev launcher script; all466 remaining source/fixture files, including the three
ship paths, match the final tested bytes. Frozen focused18/strict compilation pass.

Only the two reader modules and their test were installed, parser before consumer:

| Installed file | SHA256 |
| --- | --- |
| reccheck.py | 270a9654548ec6fe89e1ee2d0df547a1fc7633ca4152d9949b061c0b297667c4 |
| rcptcheck.py | e16a58746156fa727c125ce5bb3cf9be3cf027391f914131f32cc3af86139cbe |
| test_receipt_ticks.py | 689485d6f066c28734ca0837d693fdedbc4fee29e53c2db9e891cc408663862b |

- Secondary Windows `C:/FTEQuake/tools`: **2026-10-09T04:09:08Z**, actual installed
  reader/test18 controls pass;6 other support/game files and shared index unchanged.
- Primary Windows `C:/FTESurf/tools`: **2026-10-09T04:10:06Z**, actual installed
  reader/test18 controls pass;195 other support/game files and shared index unchanged.
  Its initial peer-modified-reader blocker cleared when the peer completed work;
  immediately before deployment both readers were clean at inspected e2aead9 and
  matched the same approved predecessor pair. No peer change was overwritten.
- Pi `/srv/nvme/ftesurf-server/game/tools`: **2026-10-09T04:13:28Z**, canonical sweep
  lock, actual installed reader/test18 controls and actual app/sweep module paths
  pass. All137 other support/source/game files, receipt/verdict/review/sim/cursor
  history hashes, scalar run/replay counts, original master/worker and health12
  unchanged. Completed mode600 SQLite/source rollback retained at
  `/srv/nvme/surfd/rollback-p603-20261009-041319`. No reload required.

Installed reader imports are explicitly bound to destination paths. Generated
fixture helpers come from frozen source; temporary homes never import the live
ledger. The first primary/Pi path-context gates failed BEFORE test bodies acted;
exact predecessor readers were restored, logs retained, and only the private
harness's explicit import precedence/context was corrected. No product repair,
relaxed assertion or redundant secondary reship. Windows rollback pairs are
retained in the private owned task's artifacts.

No game/progs/config/engine swap, owner-process restart, historical reread or
release. Primary checkout branch/ref/index were not advanced by deployment.
Practice-hold/calibration, ranking identity policy and historical rechecking remain
separate work; this verifies content consistency, not client or recording authenticity.
