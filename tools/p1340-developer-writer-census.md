# P1340 — developer writer-command census

The bounded developer file-writer command census is complete in source and
qualified on Windows and ARM. This is not a claim that all native code or parsers
are free of vulnerabilities. The census records explicit command authority,
output paths, existing supported workflows and remaining source-only risks.

## Changes

Thirteen developer callbacks consistently refuse untrusted command contexts
before filesystem/model/VM work. Trusted local exports/dumps remain supported.
Missing-world and failed-output cases refuse cleanly. The compiler output callback
propagates actual write failures and rejects invalid lengths or names rather than
silently aliasing a truncated destination.

Deliberate game-controlled recordings, receipt/journal contracts, capture consent,
movement, evidence grammar and enforcement policy are unchanged. No QC Build bump.

## Verification

- Ten full actual callback functions and three bounded large-function prologues.
  All 26 untrusted-context cases refuse; trusted paths and missing VM/model/world/
  output cases act as expected. Existing shader-file preservation still acts.
- Original source fails the expected refusal checks (one terrain context already
  refused). A test-only removed-guard control fails all corresponding checks.
- Compiler callback: three safe original failures versus zero after the fix;
  normal output, actual write refusal, exact supported filename boundary,
  over-capacity name and invalid length all tested without real filesystem writes.
- Exact clean tagged Windows client/dedicated/plugins: 74 inherited warnings,
  zero new sites; client and dedicated each pass 1,578 native self-tests.
- ARM verifies all 1,131 canonical Git blobs and compares all twelve changed
  source files against the exact parent baseline. Same callback controls pass;
  final server passes 1,578 native self-tests, with baseline/final each retaining
  16 warnings and the unchanged plugin retaining one. No new server warning sites.

The three prologue tests do not simulate complete renderer or terrain geometry.
No unsafe untreated overflow, real null dereference, working network trigger,
whole-engine/parser proof, calibration result or manual game acceptance is claimed.

## Delivery

Exact clean outputs are frozen. Source publication and native-only Windows/Pi
activation provenance are recorded separately; do not infer deployment from this
qualification. Existing configs/data/runtime programs and unrelated optional
executable aliases must remain unchanged.
