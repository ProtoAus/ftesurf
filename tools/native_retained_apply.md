# Live retained-generation apply admission (Windows)

NEW tooling-only gate: `test_update_native_retained_apply.py` and sixteen unit
falsifiers in `test_update_native_retained_apply_unit.py`. Historical graders,
helpers, product engine, pins and signing policy are unchanged. This does not
execute the launcher, test publication interruption or authorize deployment.

## Predictions and actor

The exact corrected candidate's `QKU_Apply_f` checks a retained journal before
`QKU_StartDownloads`; `QKU_Apply` independently guards installation. A retained
signed-complete cleanup transaction with same-size corrupt named stages should
survive boot, then a live AVAILABLE apply should report state `launcher` with
`retained update recovery; run the launcher before another update`. Expect ONE
manifest GET and NO object GETs; old journal/manifest/stages, ledger/certificate,
protected and unmanaged bytes remain exact across planning/apply and natural exit.

Complete content alone produces no AVAILABLE plan. Both arms therefore first
boot with signed-complete content, then author exactly one managed crosshair drift
AFTER READY. This is an explicit fixture actor, not a forced plan/result. The
no-retained-journal arm on the SAME client must check, plan one file, download the
exact signed object, install the crosshair, retain protected content and finish in
`restart`. The corrupt retained arm refuses the identical gesture. This covers
same-release repair admission, not an unprovided newer signed release. No keys,
pin overrides or generated feed are used.

Reuse unchanged `retirement.prepare`/staging input validation, WinJob ownership,
PE text binding, complete snapshot and joined-worker mirror classes. Source and
build receipt must match the exact client/companion hashes. Hash every imported
local Python dependency and serializer; recheck those inputs before PASS. Before
control loses authority at boot despite corrupt stages and subsequently downloads
and applies; this is an acting defect characterization, NOT a safety pass.

## Invocation

Run through the task's fixed-port serialized-native wrapper. Pass exact client,
matching companion, source, build receipt, signed feed and complete object closure:

```text
python -B <task>/artifacts/serialized-native.py tools/test_update_native_retained_apply.py --engine <exe> --symbols <exe.db> --source <qkupdate.c> --build-receipt <build.json> --serializer <task>/artifacts/serialized-native.py --feed <signed-update.json> --objects <closure-root> --objects <additional-root> --runtime-root <task>/runtime/apply/<fresh> --evidence <task>/artifacts/apply/<fresh>
```

Before adds `--expect-before` with the exact clean-before pair/source/receipt.
Never invoke historical wrappers or kill a busy port. Busy-port rejection is an
acting no-client control. Use fresh disjoint owned roots; failure runtimes/guards
are retained. This driver deliberately does not remove even successful runtimes;
parent may retire only independently verified disposable fixtures after review.

```text
FTESURF_TEST_SCRATCH=<owned-task>/tmp/apply python -B -m unittest discover -s tools -p test_update_native_retained_apply_unit.py -v
```

## Exports and measured run

Seed and final exports are complete unchanged shared snapshots. Active exports
are explicitly incomplete/non-retirement: omit ONLY
`.ftesurf-updater/install.lock` and `ftesurf/logs/retained-apply.log`. That exact log
can append while copying; all other files, including unmanaged `.log` files, must
remain byte-exact. Full final export includes log/lock only AFTER natural pre/post
job0. Semantic receipts are separate for startup, pre-check, planned, applied and
final; joined signed-mirror census is separately graded. Failed semantic guards
are retained. Boot complete-only replay reformats `state.json`; startup checks
identical parsed ledger values and every other byte. Subsequent check/apply uses a
fresh exact byte baseline for refusal, with NO ledger or authority exemption.
Positive apply also compares complete expected byte maps, rejecting mutations,
removals AND new paths. Only the one signed destination, exact signed certificate
and envelope, fully checked ledger formatting, and removal of the transaction's
single named stage and publication-consumed `journal.tmp` are authorized. There
is no updater-namespace or arbitrary `.log` exemption. Every unrelated stage,
consent file, protected recording and unmanaged log must survive unchanged.
Joined raw HTTP census is persisted in `finally` even when a live actor fails;
that failure remains FAIL and cannot authorize semantic acceptance or cleanup.

Evidence at `wjfinish-20261014T075250Z/artifacts/apply/`:

- `subject05` / `before02`: final strengthened driver PASS after independent
  review found the earlier positive-state oracle too broad. Both arms on each
  exact client reach natural pre/post job0 and full final inventories. Subject
  retained census has one manifest/no object; ordinary positive and both legacy
  apply arms have one manifest/one exact crosshair object. Complete positive maps
  and stage/metadata survivors are checked at applied and post-exit phases.
- `subject04` / `before01`: earlier native PASS logs support retained refusal and
  clean-before defect characterization, but independent review BLOCKED complete
  gate acceptance because their positive checker exempted the updater namespace
  and arbitrary logs. Those sources/results remain untouched; no relabeling.
- `subject03`: earlier successful driver before added build-receipt validation and
  separate post-exit semantic grade; not the final-source acceptance run.
- `subject01` FAIL: active shared exporter raced appending native log. Parent
  authorized NEW-driver-only exact log/lock active exclusion. Guard/runtime kept.
- `subject02` FAIL: ordinary apply ACTED; retained startup failed byte comparison
  solely on boot ledger formatting. Parsed ledger was equal. Corrected startup
  oracle only; live authority/network checks were not weakened. Guard/runtime kept.

Additional preparation failures: missing own artifact directory, transient driver
syntax error before any launch, and clean-before source LF hash mismatch before
launch. Git blob reconstructed with CRLF matches immutable build receipt
`61428b46...`; historical source/binaries were never changed.

Limits: headless native disconnected client, serialized trusted fixture paths,
loopback signed mirror only (not all-network silence), corrupt named stages only
(no held-stage live arm), no hostile link swap, no power-loss, no launcher repair
or supersession, no newer-release signed envelope. Independent source/evidence
review remains required. Product shipping remains blocked by other named gates.
