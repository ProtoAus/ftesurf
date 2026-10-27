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

## Qualification

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
- Three fresh independent reviews of QC4259c582/ledgered7de7d0: SOURCE OK, no
  product issues. A lens1 request-field-clearing description was corrected:
  direct forgiveness invalidates by admission/flag, not explicit field clearing.
- Fresh complete corpus503REC/167pairedVIEW/10unpairedVIEW, identical680-file
  domain and reader to its retained independent control and unchanged throughout:
  312 findings/311 faulted reports, increase0. Not a fault-free-corpus claim.

## Delivered 2026-10-27

Reviewed source4259c582, server-only stock QW
`f75f3b4150f61f53e6e12f3884ee046695e3ff40aa21651da5ddc7f6143b10fd`.
BOTH Windows server DAT/LNO pairs read back exactly, with immediate `.prev`;
existing native/client/menu/owner config were preserved and no owner process was
stopped. All12 Pi lobbies were fresh-empty, including actual status7 spectators,
at the short swap boundary. One ordinary restart each; new PID/fresh application
spawn and post-restart heartbeats positive, selected QC startup errors absent.
All12 actual PID namespace QW hashes match; local/public health200 and directory12.
The short sweep lock was released; no backend/config/native/client/UI deployment,
Build/release bump or forced busy restart. A preapply quoting/syntax failure did
not swap/start/restart anything; the same staged artifact was validated and used.
Human natural finish/reset/clean-run acceptance is still pending in lextest.md.
These are delivery/readiness observations, not a new ranked-recording verdict.

## Still open

This is a current-command boundary, not P455's complete commitment bank. Ordinary
queued I/O and active button callbacks have P1072/P1073 lineage. Persistent
logical/button/world state, inherited physical state and future obligations beyond
the current frame remain open. No historical dwell proof is revived. BACKLOG.md
and the private design retain the broader residual.
