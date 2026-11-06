# P1346 — interrupted similarity-source recovery

## Scope

A durable recovery marker in existing similarity cursor storage recovers an
admitted source after interruption. Rotation and admission commit atomically;
comparisons remain outside owned write transactions; handled completion clears
only its own marker. This does not change the schema, recording/receipt formats,
comparison thresholds, historical observations, ranking or enforcement. Native,
VM, engine commit/tag pins, Build and release version are unchanged.

## Verification

Two independent fresh-context source reviews found no issues in the exact held
product diff. Windows and Linux each passed all 28 simcheck test programs,
including 11 new reservation cases. Baseline and admission-removed controls each
had seven intended failures, with actual comparison/interruption/reopen and
transaction ownership acting rather than silence being interpreted as a pass.
Reader checks passed 949 tests; primary RUNS corpus faults did not increase.

An additional Windows cap/keyset/wrap/budget combination recovered the source,
interrupted the actual wrap query without mutation, and stored two genuine
80-opportunity comparisons. Baseline SQL selected rows but failed recovery order.
A manually seeded reservation bypasses admission and therefore does not detect
an admission-only mutant; that extra coverage is NOT claimed.

Existing saves unreadability and unrelated baseline warning/import limitations
are retained in private evidence. This is not a fairness, exactly-once, elapsed
runtime or RSS guarantee. Historical observations and captures are not rewritten.

## Delivery

Activated **6 November 2026, 11:10:06 UTC**. Serving generation/source commit:
`40bd0587a63cff0f784f24864752f1c4e84a9198`.

The real systemd candidate, listener, process identity and filesystem namespace
were checked before OPEN: five control pins and both runtime cohorts read-only,
mutable roots writable with create/fsync/rename/unlink acting. Exactly
`simcheck.py` differs among 84 runtime files; the other 83 files, reader,
heldmeta, guard, dispatcher, gunicorn configuration and three external origins
remain unchanged. Schema26, all44 pre-existing tables' schema/non-churn counts,
and eight identity-table digests were preserved. Four cron routes rebound;
`momrequests` is active and health is OK. At11:11:59UTC, all12 dedicated lobbies
and12 fresh directory entries were observed. No lobby/native/VM restart or
Build/release change was performed.

The initial cutover stopped the backend and refused an outstanding admission
lease BEFORE promotion. With explicit operator approval, its exact downloader
received SIGTERM and exited gracefully. Actual admission/candidate drain was
then proven and the recorded failed transaction continued under fresh state,
canonical preimage, actor, cron, source and snapshot checks. Original failure
and continuation evidence are retained; this was NOT an uninterrupted rollout.
The stopped downloader was not automatically relaunched.

Same-data rollback: prior generation
`9150481fa48de38cdfde9cc6c605a130fcb5492a` is retained as the CLOSED compatibility
cohort at `/srv/nvme/agent-work/ac-resume-20261106-0254/rollback-runtime`, guarded
by that root's `control/`. Primary `state/` is OPEN; predecessor and fallback
are CLOSED. Keep this production/rollback root and its namespace dependencies.
Never restore the retained historical database snapshot as a source-only
rollback. No historical database, observation or capture was restored/rewritten.
