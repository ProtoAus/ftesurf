# P1075: consume automatic finish forgiveness after the native command

## Change

An eligible automatic finish/reset-forgiveness check now requests a later grant;
it cannot grant from PlayerPostThink. The existing native EndFrame callback
consumes requests, checks the same positive VM-local admission identity, and
rechecks the unchanged P968 predicates against the current body and holds.
A stale/invalid request is consumed without granting. A request after EndFrame
waits for the next callback; no cached frame stamp authorizes a grant.

No new gameplay speed, dwell or quiet-horizon threshold. No authored effect is
cancelled. No captured field, REC/VIEW format, native ABI, engine pin/tag, qcbuild,
Build or release changes. P1074's published workshop and native requirements are
preserved. Only ENGINE.txt's product patch moves to1075.

## Qualification before independent review

- Published P1074 baseline fe9ebe1e; isolated source, no peer uncommitted inputs.
- Five native dedicated-socket control and subject cases ACTED: physical late
  effect, clean positive grant, changed admission, invalid admission and a later
  hold. Same observed input phase, consumed native work and no intervening
  EndFrame are required; silence is not a pass. Actual grounded body/rest is
  observed, not forged. Effects remain intact and affected attempts stay practice.
- These are instrumented production-helper calls at the real PostThink seam with
  explicit synthetic timer labels, not naturally elicited finishes or human input.
  No reconnect, hardware, new-recording, ranked-run or broad physics claim.
- Full stock build: all three VMs, zero warnings, compiler c24 unchanged. Fixtures
  are not in production manifests. Native image/compiler/input bindings and raw
  results are retained privately, not exported as a public reproducer.
- Reader suite: raw output and actual exit0 retained, 930 checks/0 failures.
  The first post-processing log-encoding failure is retained and not credited.
- Independent source/evidence review, final corpus check, delivery and human
  clean-run acceptance are separate gates; no delivery is claimed here.

## Still open

This is a current-command boundary, not P455's complete commitment bank. Ordinary
queued I/O and active button callbacks have P1072/P1073 lineage. Persistent
logical/button/world state, inherited physical state and future obligations beyond
the current frame remain open. No historical dwell proof is revived. BACKLOG.md
and the private design retain the broader residual.
