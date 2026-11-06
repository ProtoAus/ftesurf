# P1352 — bounded retirement of orphan similarity cursors

## Problem

Similarity collection retained per-replay peer scheduling positions after the
corresponding replay rows had been removed. Ordinary enabled collection and
process reopen did not reclaim that state. Long-lived installations could
therefore accumulate scheduling metadata unrelated to any remaining replay.
This is not deletion of recorded evidence or a new interpretation of a run.

## Change

Each enabled collection step examines at most 64 peer-cursor entries using the
existing indexed, disjoint ID ranges. An independent position in the existing
cursor table advances across live windows and survives process reopen. Only peer
positions whose replay row is still absent at the actual DELETE are retired.
Deletion and the maintenance position commit together, including on legacy
SQLite autocommit connections. Source rotation, in-flight source recovery and
all live replay positions retain their existing semantics.

No replay, stored similarity observation, captured input, schema, reader format,
threshold, tier, ranking, public badge or enforcement policy changes. Existing
collector ownership, disabled behavior and cooperative SQL/time admission remain.
The bounded maintenance write is not a hard wall-clock, RSS, whole-pass CPU or
fleet-coverage guarantee, and it does not cover nonparticipating collectors.

## Verification

- Untouched current source fails three production-entrypoint controls after real
  80-opportunity comparisons. Orphans persist through repeated enabled steps and
  reopen, including a stale tail behind 128 live peer positions.
- Fourteen focused controls cover bounded progress, live/old-row preservation,
  negative and zero IDs, source resurrection through a second SQLite connection,
  SQL interruption, disabled/expired/borrowed/read-only behavior, callback
  ownership and deletion-before-checkpoint failure on autocommit.
- A missing-late-guard mutant fails the resurrection control: the actual replay
  row returns after selection, and the mutant wrongly removes its peer position.
- Windows: 72 focused and existing source-recovery/SQL/atomicity cases pass.
- ARM Linux: 260 unit cases pass; the existing standalone similarity program
  passes all 68 checks. These are segmented results. The first discovery command
  incorrectly imported the standalone program, whose successful `SystemExit(0)`
  became one loader error; the refusal/log is retained, and the program was then
  run through its actual supported entrypoint. No product workaround or waived
  comparison/data-preservation check was used.

## Delivery

Verified source implementation; publication and the existing guarded backend
generation cutover are pending. This document must record their actual outcome,
not equate a passing test or staged candidate with live delivery. No VM/native
binary, engine pin/tag, QC Build or release change is part of this patch.
