# P717 — bounded retained KSF repair and precise unbound PB authority

## Problem

P714 cold-intent swaps cannot admit retained repair257 when all256 intents
are protected. A global overflow row cursor repeats misses across SCAN32
windows; obsolete nonterminal strikes can permanently saturate metadata.

Published P716 also introduced a distinct interaction: actual null-ID profile
PB B `.0599` replaces identified A `.0601` at the same date/rounded60ms. Losing
B's raw precision and treating its empty runid as legacy lets stale cache
filing or retained recovery reinstate A. Provenance is not current-PB authority.

## Change

- Keep queue256 and protected intents. Discover <=2 transient local-only
  overflow candidates, never a durable second payload queue/archive scan.
  Queued and overflow share original read/conversion cap2; overflow never
  requests or sleeps. One board+exact-key resume position advances through
  <=32 board files; an exhausted empty window releases normal scan rotation.
- Preserve one-day retry/strikes and third-strike seven-day retirement in the
  existing <=2048 ledger. Reconcile obsolete/satisfied nonterminal history
  against exact scoped PBs and actual readable links. Decline unknown overflow
  at genuine capacity; terminal queued work may hold its own slot until expiry
  rather than discard history or attempt a fourth time.
- Old writers can save2050..2304 active tombstones after initial truncation.
  Park locally before DB/work/state save when expiry still leaves excess;
  preserve original state bytes and resume after expiry. Historical files are
  NOT physically normalized to2048; the bound applies to accepted new writes.
- Add schema19 `ksf_unbound`, keyed map/track/leg/style/player, storing nullable
  raw seconds, rounded millis and submitted. Keep record IDs EMPTY, not invented.
  PB and marker writes/deletion share one SQLite chunk transaction. Precise
  null-ID PBs reject stale/cache identity and slower same-ms clocks. Matching
  fresh identified B clears the marker and positively restores authority.
  `current`, transactional install and legacy backfill refuse scoped markers.
- Original schema18 cannot distinguish old legacy from already-written null-ID
  profile rows, and lost raw seconds cannot be recovered. Conservatively mark
  empty-runid KSF rows with unknown precision; native/identified rows unchanged.
  Fresh identified authority may restore them under rounded/time/date gates.
  Unknown18 clocks cannot reject a subtly slower fresh same-ms record before
  identity is regained. Provably pre18 legacy rows remain bootstrap-compatible.
  Malformed/incoherent matching markers remain fail-closed, not silently repaired.
- Exact provenance/path/digest/PB/conversion/link guards and tier isolation stay.
  No native evidence/record grammar, engine binary pin/tag, QC Build or progs change.

## Acted controls and independent review

## Additional offline acceptance (2026-10-15)

`tools/test_ksf_interrupt.py --out <owned-root>/artifacts/cuts` exercises real
profile/importer transactions in deliberately spawned synthetic subprocesses.
It requires an OWNER.md ancestor and creates fresh homes, never an existing DB.
Five acted cuts bracket the PB update, precision-marker insert, PB commit,
profile cursor update and acknowledgement commit. Each killed process is
observed from a new SQLite connection; owed pages recover in a new interpreter
with HTTP forbidden. Unrelated identified/community rows and integrity checks
are controls. A normal uninterrupted step and an intentionally split TEST-ONLY
transaction prove success and inconsistency detection, respectively. A fourth
group audits inherited config/game-code sentinels: the worker scrubs SURFD_*
and redirects actual read/write keys BEFORE import; deliberate denied opens
prove the audit hook acts, and import must load only its synthetic settings.
Windows and native Linux pass all four groups; optimized Python refuses before
creating output. This is process-death recovery, NOT storage/power-loss injection
or live acceptance. The prior harness-isolation failure was reproduced and fixed;
no P717 runtime-product defect was inferred from it.

The continuation also ran ten additional native backend scripts with portable
Node24.14.0 and Pillow12.1.1: JavaScript parser and image branches actually acted.
Seven committed JS/template inputs parse, authored invalid JS refuses, and real
JPEG/PNG decoding acts. No owner corpus was read. MOMGRAB's missing real .mtv
sample remains a reported skip; the local default's existence is not public
provenance. No product runtime files, engine pin, QC Build or deployment changed.

The live-transition review additionally confirms the ordinary deployer requires
a running gunicorn master, while worker recycling can import during per-file
installation. `-NoReload` does not provide a stopped-app transition mode. A
persistent pre-import launch fence, verified drain, coherent source/DB/cache
bundle and fresh candidate-start acceptance remain explicit live prerequisites.
A document or advisory flock is not that fence; do not run the ordinary deployer
as an alleged schema18->19 protocol. Remain fenced and roll forward on failure;
never restore an older DB over later native/player writes.

Owned original evidence: `C:\FTESurf-worktrees\ksfnext-20261014T193114Z\artifacts\`.
Additional evidence: `C:\FTESurf-worktrees\ksfcont-20261015T000538Z\artifacts\`.

- Original protected256 starvation and healthy recovery control; review red
  for stale metadata,2050/2304 processing and64-board links0 versus2. Corrected
 64-board gate includes eight fresh Python-process restarts, no request/sleep,
  original2/scan32 and all256 protected intents. Natural exits are not crashes.
- `profile-authority/product-red.log`: actual profile enqueue/step files null-ID
  B after indexed A, then three intended failures: stale filing, direct zero-
  budget retained relink, and freshly fetched slower A. Existing recovery control
  acts. Fixture/setup/transport errors are separately retained, not product reds.
- Final frozen Windows collector45/profile16/importer106 assertions/top-up8/
  codec9 pass. Scope/bonus/style/player/native isolation, malformed metadata,
  actual update-before-marker abort/rollback,18 ambiguity and pre18 compatibility
  all have controls. Account/board schema19 controls include every13 CREATE
  boundary with real competing DDL, not a dynamic schema-version self-echo.
- Independent source/evidence review first blocked3 P1s, then the integration
  null-ID P1. All4 close after corrections. Reviewers inspected source and
  saved execution; they did not independently execute tests.
- Synthetic local WSL/ext4 migration of10000 unbound SQL rows takes ~0.010s,
  preserves all runs/native/identified controls, remains idempotent and uses
  the scoped primary index. This is NOT owner-sized/NanoPi/live timing proof.

The first immutable pre-integration candidate4463398 passed native16/flattened38.
Publication guard caught peer P716 before any push; that unpublished claim was
superseded by P717. Published profile/schema18 and later live-provenance/test
fixes remain preserved. Selective KSF generation now has six644 blobs; current
nginx config is stage-only test input, never a ship target.

Before publication, run final exact candidate:
`python3 tools/test_surfd_deploy.py --ref <fullSHA> --out <owned>/artifacts/native-p717/delivery -v`.
Required: current deployment18 groups, flattened committed45, profile16 and
full21-script backend gates. Retain exact six blob/mode/source hashes and
receipts in owned CHECKPOINT. Older31/38/schema18 results are not substitutes.
Native chmod/stat/install/direct755 versus644 EACCES, raw filtered-byte refusal,
exclusive backup collision and genuine flock ACK/EOF controls are actual; reload/
transport remain synthetic. Windows Node parses both committed web JS blobs;
this is syntax-only, not browser execution. Native Node/corpus/Pillow/MTV limits
remain explicit until separately supplied.

## Live transition and rollback — separate approval, not executed

Old18 writers do NOT honor schema19 markers, and old collectors cannot safely
consume new `{retry,strikes}` dictionaries (normal old ticks discard them;
direct old discovery can type-error). Source-only downgrade is not safe.

`surfd` migrates on import BEFORE the importer's inner cache lock. Existing
deploy/sweep flocks do not establish old-writer exclusion. DO NOT run the
ordinary deployer alone against live18. An approved procedure must exclude/
drain all old cron/manual importers BEFORE installing or importing new code,
using coherent outer-cron/cache exclusion maintained across six-file install,
migration, fresh accepting-generation verification and final receipt. Failure
or disconnect must remain fail-closed; do not automatically resume mixed files/
old writers. Resume only the intended verified generation afterward.

Preserve matching source, database and cache/demos.json first. DB restore is a
separate operation: never overwrite later native/player data, delete retry/
marker history or reset version blindly to make old code run. No transition,
rollback, live request/crawl, DEMOS cron, service/reload/SSH or game/GPU acceptance
is granted by this offline patch. Original CSS/66t v2/v3 Watch/seek/style/body,
physical UI acceptance, recorder corpus and unsupported staged-course grammar
remain separate gates; do not infer them from synthetic SQL/Flask/decoder tests.
