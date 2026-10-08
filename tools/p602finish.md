# Patch 602 — ranked finish-duration binding

## Outcome

A new ranked replay PASS must describe the indexed finish duration, not only a
reproducible trajectory. `surfd/sweep.py` selects indexed ticks and accepts the
engine's bounded `ticks N rows N` PASS payload. Confirmed duration disagreement
becomes HOLD, retaining actual ticks and counts. Unavailable, ambiguous or
out-of-range finish output becomes retryable ERROR, with unknown ticks and no
counts snapshot. Public rows do not expose the authenticated reason.

Evidence-only abandon promotion, identity/rate/stage/source fences, existing ERROR
budget and refiling/recheck behavior retain their contracts. Explicit owner
approval still overrides a HOLD. Existing badges/history are not automatically
reread or revoked. No schema, detector threshold, engine/QC/recording format,
config, engine pin/tag, progs, qcbuild/Build or release change.

## Preregistered falsifiers and results

- Matching indexed/verifier duration: runner acts, PASS/public badge1.
- Different duration in either direction: old code PASS; fixed code HOLD/badge0,
  preserving actual confirmed ticks/counts and a private explanation.
- Real POST/file/SQLite/public-board paths with present and later-arriving files.
- Missing, malformed, ambiguous and out-of-range PASS payloads: ERROR/pending,
  unknown ticks/no counts, rather than a false player finding or fresh badge.
- Acting independent same-map companion, identity mismatch, original HOLD/REFUSE
  reasons, explicit approval and abandoned-evidence promotion controls.

`surfd/test_verifier_finish.py`: nine tests, five baseline failures, final zero.
These use an explicit verifier stub; they do not claim engine physics calibration.
Existing sweep/source/counts controls pass. The existing counts test's PASS fixture
now matches its indexed662 ticks instead of an unrelated100; metric assertions
are unchanged. An existing counts test crossed a one-second rendering timestamp
boundary once; its unchanged affected suite passed on the single repeat and both
full boundaries. No unrelated timing-test repair.

Fresh read-only independent review found no issues. It inspected submission,
public badge precedence, source/abandon contracts, tests and the actual native
PASS emitter, rather than accepting supplied test success as independent execution.

## Full verification boundary

```text
python surfd/test_verifier_finish.py
python surfd/test_sweep.py
python surfd/test_verifier_counts.py
python surfd/test_verifier_sources.py
python -W error -m py_compile surfd/sweep.py surfd/test_verifier_finish.py surfd/test_verifier_counts.py
```

Full fixture-free `surfd/test_*.py` except corpus-dependent `test_momindex.py`, plus
10 tool programs: hidcheck, rcptcheck, reccheck; recsim limits/opportunities/parsing/
sources/unreadable; journal diagnostics/snapshots. The eleventh evidence program,
`surfd/test_recsim_observations.py`, is already included in the surfd selection.
An initial script also attempted a nonexistent tools copy of that program; that
setup error is retained, not presented as an executed test or product defect.

- Linux: all70 actual programs pass in an isolated current-source stage.
- Windows:70 actual programs run; only two known baseline admin assertions fail
  (UDP amplification explanation/packet budget), identical to the previous batch.
- `tools/test_reccheck.py`:306 checks, zero failures. Strict owned-file compilation
  adds zero warnings; no unchanged QC/engine binary build was required.
- Immutable copied run/sidecar corpus:269 recording/prefix files and91 paired view
  files. Baseline/subject both170 faulted files and173 faults; no increase. Source
  and copied hashes are checked; raw filenames/findings stay private.
- Additional native Pi control: one readable historical replay positively PASSes
  pm_verify, with parseable finish ticks matching the indexed time. Owned port27792,
  no fixture modification/live ledger import or peer process termination. This
  establishes output compatibility, not general physics or detector calibration.

## Publication and deployment

Publication/deployment provenance is recorded after the exact commit is inspected.
Selected runtime ship set: `surfd/sweep.py`, `surfd/test_verifier_finish.py`, and
its updated `surfd/test_verifier_counts.py` control. A standalone sweep source
swap needs no gunicorn reload. Destination hashes and actual installed-module
controls, protected source/history/process identity and health are deployment
gates. Windows game installs, lobbies, engine/progs/config and player data are
outside this surfd-only ship set.

## Remaining limits

This binds new observations; it is not a historical badge sweep, owner-review
policy change, universal source-race defence, or new cheating detector. Native
output wording changes abstain until explicitly supported. Name/player identity
retiming policy and unrelated baseline admin UDP checks remain separate.
