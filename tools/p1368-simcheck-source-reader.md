# P1368 — selected reader source bytes, not timestamp bytecode

Implemented, independently reviewed and verified on Windows and ARM. Source
acceptance below and actual backend delivery are separate; the latter is recorded
under its own UTC boundary. No stale-reader production incident is claimed; guarded
routes already use an absent private bytecode-cache prefix.

## Problem and change

The collector resolves one reader for each enabled pass, reusing that reader within
the pass. Its ordinary path loader could nevertheless execute old timestamp-valid
bytecode after the selected source changed at the same file size and integer mtime.
`-B` prevents writing caches; it does not prevent reading them. Thus an ordinary
direct caller's next pass could still execute the previous reader revision.

Keep the existing caller-only path, spec/module metadata, per-pass lifetime,
capability checks and exception-to-unavailable handling. Execute the selected
binary source bytes with `compile(..., dont_inherit=True)` in the same module
globals instead of asking the loader for cached code. Encoding cookies/BOM and
source future statements retain normal Python semantics. No cache deletion,
process-global module cache, new search path or alternate reader is introduced.

This changes neither reader signals/grammar nor recording capture, clock support,
source selection policy, historical observations, schema, thresholds, ranking,
defaults, native pin/tag or QC Build.

## Acting control and subject

The new existing-fixture case explicitly builds timestamp alpha bytecode. Its first
pass performs three real80-opportunity comparisons; the first comparison callback
installs equal-length bravo source while that pass correctly retains alpha. Restore
the original timestamp, prove source size/mtime and cached bytes still match, then
admit a genuinely new fourth source. The next three real comparisons must execute
bravo. Previously stored rows remain field-for-field unchanged.

- Pristine P1361 control: the final marker fails with six alpha calls instead of
  three alpha and three bravo, AFTER all six actual80, source/cache/time/new-pair/
  old-row assertions acted. It is not a loader/setup failure or fake metric.
- Fixed Windows Python3.10: all four pass-reader tests pass.
- Actual ARM Python3.11.2/aarch64: four subject tests pass; the exact legacy control
  fails only the same final marker. Paired small source fixtures contain no player
  input or live database and all test processes/temp caches are cleaned up.
- Independent source review: CLEAR. A private actual-loader smoke also passed
  Latin-1, UTF-8 BOM, evaluated annotations, spec metadata, no-cache-write and the
  existing missing/source-error/capability-unavailable behaviors.

## Regressions and data preservation

All30 existing similarity test programs are covered on Windows:273 unittest cases,
267 passes and six existing skips, plus68 legacy executable assertions. Four skips
require SQLite result-code attributes; two require POSIX ownership/named-pipe
contracts. These are not claimed as Windows passes or complete ARM bank coverage.

The required reader executable passed949 checks with zero failures, using the
frozen P1359 checker `3eab465a...`. That reader/corpus evidence is not a claim about
later peer checker changes included while merging publication metadata. The actual
selected reader/heldmeta and the reviewed collector/test blobs stayed exact.
The existing runs corpus has554 REC and178 VIEW files, all byte-identical to the previous input
inventory. Its351 existing faults remain344 REC and seven VIEW; all732 per-file
report blocks match the previous multiset. Raw stdout order differs because the
current explicit input list is globally sorted. No fault, stored observation or
input was repaired, rewritten, regraded or silently omitted.

## Actual primary backend delivery — 7 November 2026

The owner executed the separately reviewed, four-source-hash-checked namespace
installation and primary activation. A subsequent READ-ONLY completion audit at
2026-11-07T14:29:19Z confirms the accepted OPEN primary generation16fb0b54 and actual
collector `ffed2432` source. All84 runtime and158 declared inputs match their pinned
material. Canonical launcher, four cron routes and the importer select this source;
health, auth/protected-route and inventory method boundaries pass. The actual serving
master PID/birth/invocation, saved namespace proof, live mount/inode flags and profile
are bound together, not inferred from host-visible files or a synthetic candidate.

The same current database remains schema26/44tables; the eight identity digests were
preserved at cutover and still match this read-only audit. No restore/regrade/backfill
occurred. Leases are released and no recovery/failure/observer-cleanup artifact exists.
Primary and fallback materials, original receipts and prior code remain retained;
fallbackfb7ed790 uses CURRENT data, never an old database restore. Do not repeat the
healthy activation or edit its immutable serving package to ship another feature.

Readers remain the prior P1359 BF99/3eab/A3f7 cohort; this core-only delivery is NOT
P1370/P1374 reader delivery. P1377's later selected-SQL-deadline collector is likewise
NOT included. Each subsequent change needs a fresh source-bound generation/reader
plan and its own actual acceptance, not re-dated P1368 evidence or tier credit.

## Limits

The guarantee is selected reader source-byte execution for this existing API.
Imported helper bytecode/global state, arbitrary concurrent source publication,
code authenticity, whole-corpus freshness, hard time/RSS/SQL bounds and complete
fleet scheduling are not proved. Existing hardware/human/calibration/policy leaves
and acceptance tiers do not gain credit. Source tests do not establish a live
namespace, application cutover, fallback or whole-fleet pass.

The known guarded live routes already avoid the demonstrated default-cache path.
Any later generation still needs its own immutable material/current-data/actual
namespace checks; source publication alone is not deployment.
