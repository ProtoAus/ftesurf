# P956 — recording identity retained with future verifier attempts

## Change and limits

Future accepted native/source-bound terminal observations store the existing
consumed-recording SHA256 in `verdicts.recording_sha256`, in the same transaction
as the verdict and replay checked-state update. This is input provenance, not
new capture, authorship, eligibility, present-file equality or player detection.

The existing idempotent per-attempt metadata helper adds a TEXT NOT NULL column
with empty unknown default, as for counts_metrics. Schema user-version20 is
unchanged. Historical rows are not reconstructed/backfilled; errors or refusals
without an actual accepted native input remain unknown. Rechecks append their
own source identity rather than rewriting history or the filing hash. Public/
admin payloads, badge/ranking/review/threshold rules and native source are unchanged.
No engine commit/tag pin, VM delivery, Build or release bump is required.

## Acting validation

- Original source:24 existing attribution/source controls pass;13 new acting
  file/SQLite tests fail, proving the durable field is missing rather than a
  silent runner or pre-existing behavior.
- Changed source: all60 focused Windows tests pass. Checks cover accepted PASS/
  HOLD/REFUSE, missing input, unauthenticated/ambiguous/mismatched/failed-exit
  observations, after-native replacement, stable companions, distinct rechecks,
  historical preservation, repeated/simultaneous additive migration, original I/O
  errors and atomic rollback of the insert plus checked-state update.
- ARM runs the same60,59 pass/1 platform skip. Actual installed native runs the
  approved4418-tick legacy positive through the real authenticated runner and
  stores the correct consumed digest in an isolated SQLite attempt. The prior
  schema20 attempt stays unknown and unchanged; native exits0. Only safety-only
  headless argv additions are used. This is not a normal live-cron, new-world or
  human/device-calibration measurement.
- Existing NoDeploy QC entrypoint: three VMs0warnings. Reader suite864checks,
  0failed; existing sweep/board/evidence/receipt identity checks pass. Identical
  selected runs corpus430: baseline294withfaults, changed294withfaults, increase0,
  selected input bytes unchanged. No corpus/player-data write. An unnecessary
  broader saves attempt was blocked by a protected historical fixture; it is NOT
  credited and no ACL was changed.

The first rollback test used the wrong initial seen value; it now compares the
actual captured before-state, without changing product code or weakening the
rollback claim. Failed wrapper invocations/import context and their bounded
repairs remain private evidence, not credited feature passes.

## Delivery state

Deployed to the development backend on 2026-10-24 at 01:17 UTC after two
independent read-only reviews: storage binding and guarded cutover/preservation.
Exactly the two approved source files changed in the existing80-input runtime;
the other78inputs, native dependencies, readers, configs and schema20 stayed
unchanged. A fresh private mode0600 SQLite backup passed quick_check before the
reviewed handoff; no restore, historical recheck or fabricated live row occurred.

Actual loaded sources for both modules, the new column/default, predecessor drain,
successor acceptance/admission, canonical bindings and importer lease/readiness
passed. All244historical verdicts retain identical pre-existing fields and unknown
recording bindings. All12lobbies and the stopped AI service remain unchanged.

No natural future live verdict arrived during postflight. The real-native future
write is therefore the isolated SQLite positive above, not a claimed live-cron
observation. Existing source/build/corpus evidence remains valid; no owner manual
acceptance, calibration or broader anti-cheat completeness is claimed. Private
data, actors, snapshot paths and recovery details are not published here.
