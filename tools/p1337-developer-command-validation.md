# P1337 — developer command validation

The engine validates developer-tool command provenance before VM/filesystem
activity and checks compiler argument capacity before copying arguments. Trusted
operator defaults, explicit source arguments and supported boundary inputs remain
available. Excessive arguments are refused rather than silently truncated.

## Verification

- Actual production handlers compiled in a write-free strict-warning fixture.
- Both untrusted provenance classes refuse with VM present or absent. Trusted
  defaults, explicit arguments, source-search fallbacks, VM setup/teardown,
  optional compiler capability and continuation paths act as expected.
- Exact supported-capacity inputs act; excessive inputs refuse before side effects.
- Untreated source and a test-only missing-provenance-guard control fail the
  expected refusal checks. A too-small-capacity control fails the valid-boundary
  acceptance check. No unsafe untreated overrun is needed or claimed.
- Exact clean tagged-source Windows m-rel/sv-rel and plugin builds pass with no
  new diagnostic sites. Its 74 inherited native warnings remain. Both client and
  dedicated executables pass all 1,578 native self-tests.
- ARM verifies all 1,131 canonical Git blobs, builds baseline and candidate server,
  and runs the same handler controls. Candidate passes 1,578 native self-tests;
  baseline/candidate server each retain 16 warnings, plugin retains one. No new
  server warning sites. Final source remains canonical and probe-free.

No movement, journal/recording format, evidence interpretation, enforcement,
identity/capture, retention, ranking, public release or QC Build change. Fixture
checks do not prove a network exploit or complete native/compiler/parser audit.

## Delivery state

Exact clean stamped qualification passed on Windows and ARM. At 6 November
2026 03:38:33 UTC, the existing native-only Deploy helper updated both Windows
installs' ten supported destinations. All ten destination hashes and their
immediate `.prev` predecessors match; prior destination/`.prev` preimages remain
retained. The shared rig lock is released; no owner process was killed.

A client started after the copy, and the final protected-inventory idle gate
refused. Full non-target postflight and installed-runtime acceptance therefore
remain pending; do not redeploy or invent a preservation pass. No QC/data/config
or optional alias change was requested by this native-only operation.

The ARM server/plugin pair is qualified and frozen, not lobby-deployed. A fresh
13-actor recorder/resume inspection found an open preserved-namespace descriptor
and changing preservation state. The normal warning/countdown restart policy does
not waive those safety dependencies. No live maintenance gate is held. Do not
infer fleet deployment from a source commit, build or Windows delivery.
