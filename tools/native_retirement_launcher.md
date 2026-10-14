# Retained-generation launcher gate

`test_update_native_retirement_launcher.py` is a **separate** native acceptance
gate. Historical graders, engine source, signed feed/pins, bootstrap and updater
policy are not modified. `test_update_native_retirement_launcher_unit.py` contains
12 portable negative-oracle/positive controls.

## Named measurement

Use the external corrected candidate and its exact PE-text companion, the clean
production bootstrap, and the **existing** signed production closure. This tool
never reads a signing key or authors a signed fixture.

At persisted `attempts=3` it seeds both:

* signed-complete current content with a same-sized corrupt named protected-zone
  stage: native readable valid stage retirement must ACT, retaining the complete
  original transaction and corrupt stage without spending content budget;
* incomplete exhausted content: native startup must refuse unchanged, with the
  whole original transaction still authoritative.

For each, real Rust launcher `--offline --no-launch` and unavailable-service
negative controls must refuse without authority/content/stage changes or object
GETs. The acting signed `--yes --verify --no-launch` control then verifies the
whole signed closure, repairs exactly the incomplete unprotected files (zero or
two object GETs), preserves all protected/unmanaged bytes and partial ledger
policy, completes Rust recovery and parks the exact original native journal.
Old native stage objects and failed `journal.tmp` are retained, not swept or
adopted. A fresh launch of the **same corrected candidate** must now naturally
reach its startup actor; all signed bytes/metadata/stages are checked again.
Enabled consent is explicitly seeded `1\n` so repair consent is not conflated
with the recorder's separate consent or first-run UI.

Every native/Rust process starts suspended and is registered in an owned Windows
kill-on-close job before resume. Successful phases require natural pre/post job0
and complete metadata/log/inventory export. The signed-mirror server joins
accepted workers before the late final census. Source/client/bootstrap bindings
are rechecked. Successful synthetic runtime retirement requires these receipts;
failed fixtures and unknown guards remain. No game is spawned by the launcher.

## Invocation

```
python -B tools/test_update_native_retirement_launcher.py \
  --engine <corrected-candidate.exe> --symbols <exact-companion.exe.db> \
  --launcher <production-bootstrap.exe> --launcher-binding <binding.json> \
  --feed <retained-signed-update.json> --objects <retained-objects-root> \
  --runtime-root <fresh-owned-runtime> --evidence <fresh-disjoint-evidence>
```

`launcher-binding` records the published bootstrap `sha256`/`commit` and inspected
clean `inspected_repo`/`inspected_sources_sha256` from its release provenance. Do
not use an earlier stale build receipt merely because the binary filename matches.
The native engine source/build provenance is recorded by the caller alongside
its input receipts; this driver's PE comparison is not a replacement for that
source/build binding. When several suites use the signed envelope's fixed
loopback mirror port, serialize their native execution with an owned cross-process
resource lock. Never change/resign the envelope or stop another lane's server.

## Limits

This is explicit loopback transport using the pinned verifier, **not** default
public-feed availability, a newly signed/new-version release, launcher-spawned
real gameplay, or a power-loss durability test. It closes same-version signed
launcher repair/supersession of a retained generation, not partial-read handling,
publication interruption or retained-generation in-game apply admission. Those
remain separate gates. The portable oracle tests alone are not native acceptance.

## Initial evidence

Owned task root `C:/FTESurf-worktrees/wjfinish-20261014T075250Z`:

* `artifacts/launcher01`: FAIL, preserved runtime. Offline/unavailable controls
  refused and online recovery ACTED; the driver incorrectly expected World of
  Surf branding instead of the bound bootstrap's `FTESurf ... is ready.` banner.
  It is not counted as acceptance. Exact source at clean commit `5c60f697`
  establishes the correct banner.
* `artifacts/launcher02`: both named cases PASS after the banner correction.
* `artifacts/launcher03`: both named cases PASS on the final stronger oracle:
  full original rows/budget and exact native retirement map before Rust repair,
  bootstrap-source/binding rechecks, and complete closure regrading after fresh
  candidate startup. Ten native/launcher phases; each natural job0, full export.
  Successful runtime retired; `launcher01` remains for failure evidence.

Exact commands, hashes, phase receipts and HTTP/object census are in those
artifacts, not inferred from a product build or deployment.
