# P1491 — collector peer prefetch follows its remaining pair allowance

## Useful change

The store-only similarity collector could select 200 peers even when its shared
pair-attempt allowance had only one slot left. Under a supported small SQL-read
allowance, that unused prefetch could prevent its first useful comparison.

Only the owned collector callsite now passes the lesser of the existing 200-peer
window and remaining pair allowance. The same selector, eligibility, actual
reader, metric, source capture, admission and atomic flush remain. Generic direct
comparison calls keep their existing default/explicit windows and late-overlap
lookahead. The contention test adapter preserves its one-peer cap while accepting
the collector's now-explicit window keyword.

No new setting or default, index/table/schema, raw capture, recording grammar,
score, threshold, badge, ranking, enforcement, engine commit/tag or QC Build change.

## Acting evidence

- Real `sweep.similarity_step`, real comparison reader, 201 valid synthetic
  recordings, one source/one pair allowance. At the same **20,000 selected-read
  instructions**, the predecessor requests `LIMIT 200`, returns SQL-unavailable
  and stores no observation. The subject requests `LIMIT 1` and stores one real
  80-move comparison. Pair IDs, verdict, compared opportunities, match and
  captured source observations equal the predecessor's normal positive.
- Both 15,000-instruction arms abstained. That initial allowance is **not** a
  successful old/new discriminator and has not been relabelled as one.
- Windows: 281 existing/new unittest cases, zero failures, six known skips
  (four missing Python SQLite result-code attributes and two POSIX-only controls).
  ARM Python 3.11: the same 281 cases, zero failures and zero skips. Existing
  standalone real-reader, store-only/badge noninterference and independent-writer
  controls pass on both hosts.
- New actual-wrapper regression proves useful low-budget work, later healthy
  passes, source count, idle connection and numeric busy-timeout restoration;
  direct exhausted-budget admission and explicit two-peer comparison still act.
- An initially broader private-comparison cap failed the existing late-overlap
  direct-call regression. The final change is instead at the collector callsite;
  the old test and its positive are preserved. ARM also exposed the contention
  fixture's duplicated keyword: the adapter correction preserves its original
  one-peer constraint and actual busy/committed-first-row/recovery assertions.
- Initial test SQL quoting and scratch default-home errors were retained and
  corrected at their actual seams, not credited as product passes.
- Supported isolated production three-VM QC build: zero warnings, no deployment.
- All six reader/parser/crypto source inputs are byte-identical to their previous
  qualification, and a read-only census verifies the same 568 corpus-member
  hashes and membership. The prior 949/0 reader result and 356 pre-existing
  faulted records remain applicable: reused unchanged-input evidence, not a new
  sweep, repaired historical data, or a clean-corpus claim.

## Limits and delivery

A smaller collector window can offer less **same-pass** lookahead if a selected
candidate becomes stored before its late recheck. No fake admission, skip,
observation or peer-cursor advance fills that gap. Existing bounded rotation does
not promise full allowance utilization, exhaustive coverage or fleet fairness.

Selected SQLite VM callbacks are not a hard whole-pass time, memory, bytes, I/O,
UDF, write or preemption bound. The broader resource/fair-completion follow-up
remains open. Synthetic positives are not genuine input provenance, field
calibration or new detection capability. No historical sample is reconstructed.

**Source qualification only; not live.** No service, current DATA, native image,
game program, lobby, consent or capture action was performed. A guarded backend
promotion still needs its exact approved source contexts and fresh boundary
qualification. Do not interpret source publication as deployment authorization.
