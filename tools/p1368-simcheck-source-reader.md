# P1368 — selected reader source bytes, not timestamp bytecode

Implemented, independently reviewed and verified on Windows and ARM. Publication
and actual backend delivery are separate: the live P1361 generation is unchanged
at this source-validation boundary. No stale-reader production incident is claimed;
guarded routes already use an absent private bytecode-cache prefix.

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
