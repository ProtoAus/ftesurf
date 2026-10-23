# P953 — native local file-writer trust boundaries

## Scope

Engine `93a891fea47f3c5f64e44fc2da8ef5ab7ad6cd0b`, annotated tag `patch-953`.
Two existing server file-writer handlers now apply `Cmd_IsInsecure` before any
file or logging-state operation. Registration restrictions are not a substitute
for that check. Explicit refusals leave their files and logging state alone;
trusted operator behaviour remains available. This adds no command endpoint.

No movement, input/evidence API, recorder format, verifier semantics, collector,
schema, ranking, legacy-credit, QC Build number or release-version change.
The native source includes the already-published Phantasia/Epiphany fixes; this
feature does not roll those back or deploy shared uncommitted source.

## Verified before exact-tag qualification

- An actual dedicated native control demonstrated the former local file writes
  in an isolated, data-less namespace. This was not just a policy model.
- The changed native explicitly refused both tested untrusted contexts. Its
  synthetic file remained byte-identical and no frag log was created. Caller
  readbacks and an existing trust-boundary control acted in each arm; a missing
  or silent response was never accepted as success.
- A trusted operator positive subsequently replaced its own synthetic file and
  opened/closed one new empty frag log, proving the commands were not disabled.
- The complete paced run exited normally with code0, no forced stop, own child
  reaped, both real install configs and seven supplied native images unchanged.
- Three QuakeC VMs compiled with zero warnings. The initial native Full build
  retained the known74 inherited warnings and added no warning site. Its parallel
  metadata-packaging failure is retained; exact metadata recovery and the same
  source build continuation succeeded. Explicit-database standalone clangd
  completed with zero parser errors.

The first subject run passed its functional checks but exceeded the native
connectionless amplification budget at quit. It is retained as a **whole-test
failure**, not silently relabelled a pass. The harness was paced to respect the
unchanged detector; no rate/security limit was raised or disabled.

This proves the tested native command contexts, not normal-client wire
reachability. Private fixtures, credentials, actor details and raw logs are not
published. No automatic player verdict or genuine-player collection follows.

## Final qualification and development delivery — 2026-10-23 UTC

- Clean tagged Windows `Full/NoDeploy`, using the existing serial packaging route:
  three VMs0warnings, seven AMD64 images, two exact clean EXE stamps, five valid
  plugin ZIP CRCs/metadata stamps,74 inherited native warnings and no new site.
  A detached launcher that never reached the build is retained separately; only
  the successful foreground build is credited.
- Final-image refusal/trusted/native caller controls passed with normal quit0.
  The actual installed dedicated also passed trusted file export/log open-close
  and the version smoke. Ten native destinations across both Windows installs
  match the qualified bytes;21 protected VM/menu/config files remain unchanged.
  Independent private test processes were not stopped or overwritten.
- ARM64 native pair built with16 unchanged warning sites. All60 named physics
  rows over five matched-fixture maps agree with the installed Windows native.
  Both documented legacy positives pass. The fixture deliberately holds its
  retained VM and map rules constant; this is not a QC VM rollout or new-world
  coverage claim.
- All12 Pi lobbies were restarted only after fresh empty-unit checks. Actual
  running EXE hashes and mapped HL2 identities match the qualified pair;
  predecessor bytes/previous history, configs and28,612 existing protected files
  were preserved.
- The paired rollout encountered a backend-availability failure. That transaction
  remains recorded as **failed**. Forward recovery restored the qualified backend
  without a native downgrade or data restore. Final actual worker/importer checks,
  health/board/API responses and the fresh12-lobby directory passed. Application
  contents, schema and collection policy were not changed by this native patch.

Source publication, binary qualification, destination hashes and live postflight
are separate evidence. No release/Build bump, owner manual acceptance,
normal-client wire reachability, human/device calibration or automatic player
verdict is claimed. Private actors, recovery details, credentials and raw logs
remain private.
