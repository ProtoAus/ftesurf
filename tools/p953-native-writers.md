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

## Delivery state

Source/pin/notes publication is distinct from binary qualification and delivery.
Exact-tag Windows/Linux builds, final-artifact checks and guarded deployment are
pending at this source checkpoint. No deployment or owner manual pass is claimed.
Ordinary development delivery must preserve predecessor bytes and player data,
verify actual destination hashes and obey active-process/empty-lobby gates.
