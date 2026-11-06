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

Source functional checks passed; exact clean stamped platform qualification and
native-only delivery are recorded separately when completed. Existing runtime
programs, owner settings, data and unrelated optional executable aliases must
remain unchanged. Do not infer deployment from a source commit or build.
