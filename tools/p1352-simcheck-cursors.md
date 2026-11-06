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

**Deployed and verified on 6 November 2026 at 18:36:12 UTC.** Public source and
serving generation: `9b6cb7c0c48a14994fd08f6012643f668514153c`; engine journal:
`9ae0fea60d8dfcb6e2b9e2823f90697d5be74543`.

The existing guarded code-only backend generation route replaced exactly
`simcheck.py` in the actual serving 84-file profile; the other 83 frozen files,
separately bound reader and helpers remained unchanged. Both primary and
same-data rollback cohorts passed the real CLOSED candidate checks, including
acted feature/control metadata behavior and existing authentication/source guards.
The actual cutover preserved all 44 pre-existing table schemas, eight identity
table digests and protected non-churn counts; 156 bound-file checks passed.
All four cron routes and the managed importer were rebound through the guarded
launcher. The service is healthy, primary admission is OPEN and fallback CLOSED.
The shared installer input was restored exactly and its reservation removed.

Fourteen targeted tests subsequently passed against the actual serving module,
using only owned synthetic SQLite/files and genuine 80-opportunity comparisons.
No production collection or historical reread was invoked for that fixture.
The original missing-input/predecessor-template staging refusals remain recorded;
same immutable archive/closed fence bytes were verified before completing the
stage without reinitialization. A postflight health observer first used the wrong
port; that refusal remains recorded, and only the read-only observation was
completed through the actual service endpoint. No healthy activation/test was
repeated to hide a wrapper failure.

Active runtime: `/srv/nvme/agent-work/ac-cursor-20261106T1747Z/runtime`, primary
fence `state/` under that root. The same root retains `rollback-runtime` and
CLOSED `control/` for exact predecessor generation
`53b94a926f2a0089cb20e3b5b21808e61fd70a79`. These paths and the namespace pins are
runtime dependencies, not disposable scratch. Rollback uses **current data**
through the existing guarded route; the historical backup is not a restore input.
No lobby/game process, native/VM binary, engine pin/tag, QC Build, release,
collector/capture policy, identity or verdict history changed in this patch.
