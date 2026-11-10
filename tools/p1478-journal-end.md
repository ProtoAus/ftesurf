# P1478 — complete input journals can grow for their terminal record

## Product outcome

The existing P1116 backlog item is fixed: closing a journal no longer lowers its
configured byte limit to its current allocation. A complete journal at an ordinary
64/128 KiB growth boundary can append `end`, rather than being falsely marked
`truncated`. Actual body-cap truncation remains recorded. No collected fields,
record grammar, consent, capture, ranking or enforcement policy changed.

Engine base `0b223e6148922c36687e6abc5aa4b5122df7634e`; fixed source and
`patch-1478` are `0e22be20c52cb6618a0c59a064ff4391d2958ce3`.
The separate threaded-physics journal synchronization backlog item is NOT fixed.
Nor does this promise terminal capacity for every configured-cap/headroom case.

## Verification

- Engine `tools/test_input_journal_end.py` extracts actual Raw/Line and the WHOLE
  production close handler. Host input flush/device enumeration, clock,
  digest and filesystem calls are explicit stubs. Strict C99
  `-Wall -Wextra -Werror`: prechange628 checks/50 terminal and false-truncation
  failures; fixed628/0. All ordinary allocation-boundary cases preserve the
  input prefix and exactly one terminal record. Controls also exercise actual
  cap truncation with reserved allocation, discard/refused-name/write-failure
  and stale-digest invalidation. Submitted digest/write bytes agree.
- Independent source review found no issues. Digest stubs do not test SHA-256,
  disk durability, actual input capture, reader admission or concurrency.
- Standard isolated `src/build.ps1 -Engine -NoDeploy -FteRoot <owned-engine>
  -Jobs 8` built client, dedicated server, all five default plugins and all three
  QC programs. QC0 warnings; native74 warning occurrences, exact same diagnostic
  payload multiset as the retained earlier full-build control, zero new. No new
  warning in the changed input module. Qualified existing fteqcc was used.
- `python tools/test_reccheck.py`:949 checks/0 failures. The required actual run
  corpus sweep checked568 files with356 pre-existing faults; this is NOT a clean
  corpus claim. Reader bytes are unchanged and all selected corpus SHA-256s
  remained unchanged, so this producer-only change introduced no corpus delta.
  The full digest, raw diagnostics and historical fixture exceptions remain
  private. No real recording or protected fixture was edited.
- The shader-generated header differed only in its generator-path comment;
  that build-generated comment was preserved privately and restored to the
  inspected source. All5882 shared dependency files remained byte-identical.
- Final client stamp: `git-8647-patch-1478-0-g0e22be20c`.
  Client SHA256:`71cb4eccd142cfa4bca8ba0e2eda9c643385a04391378879599815d33ff77c88`.

## Delivery state

Implemented, independently reviewed, built and engine source/tag pushed.
The guarded dual-client update REFUSED before any target or `.prev` write because
an installed game client was running. No game was stopped. Both installed client
images remain the inspected patch-1476 predecessor. Deployment needs a brief
owner-game-free interval; the already qualified images must be reused, not rebuilt.

Only `C:/FTESurf/ftesurf64.exe` and `C:/FTEQuake/fteqw64.exe` are intended targets.
Use the existing `build.ps1` Deploy helper, destination/predecessor guards and
saved original/previous images. Preserve actual server/plugin/VM/config bytes;
there is no backend, lobby, ARM, schema or progs change to activate for this
client-only delta. After deployment require both destination and `.prev` hashes,
then an isolated installed-image version smoke without touching owner settings.
Private evidence retains the original refusal and exact source/build binding.
