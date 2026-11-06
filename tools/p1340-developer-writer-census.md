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

Product source `7e271da76fc40e6e41e15cd8f90dedb0c9f9eccf`, annotated tag
`patch-1340`; engine-pin companion `b543bee1`. Exact clean outputs are frozen;
the later delivery-journal commit is documentation, not a different binary.

- **Both Windows installs, 6 November 04:55 UTC:** all ten native/plugin targets
  and their `.prev` hashes verified; 19,334 previous non-target paths unchanged,
  no new paths outside the approved target/staging set, no owner client killed.
  The original pre-mutation process refusal is retained; the same payload resumed
  only after its original identities and preimages were still exact.
- **All twelve Pi lobbies, 05:43:48 UTC:** every port warned with the default
  ten-second countdown, then twelve new verified native process epochs and mapped
  plugin inodes, none skipped. Before any canonical stage, eight recorder parts
  and 183 complete current resume preimages were individually rehashed on- and
  off-box, and the strict thirteen-declared-actor FD/birth/namespace check repeated
  under the short canonical sweep lock. All 47,758 previously inventoried protected
  data paths stayed unchanged; eleven new files were retained. Configs, unshipped
  programs and the actual backend launch/files stayed unchanged; lock released.
  `.prev` and all four native predecessor/prior-prev rollback files retained and
  independently verified off-box. No data restoration or backend generation swap.
- **05:59 UTC read-only postflight:** all twelve live native/plugin pairs and
  current/previous destinations still exact; backend active descriptor, configs
  and unshipped programs exact. Both Windows installs' ten current/previous pairs
  also rechecked exact. No repeated restart or swap to manufacture acceptance.

This is the finite census and recorded deployment boundary, not general process/
file-writer closure, complete evidence-fleet coverage, parser safety or human
acceptance. No VM/config/backend shipment, new capture/policy, Build or release.
Original refusals and immutable source/artifacts/archive/rollback history remain
retained. Do not rebuild or redeploy a healthy cohort from documentation HEAD.
