# P1158 — finite-stamina takeoff in the existing status consumer

## Source and scope

Native candidate `793ee161a9baa8ba976f1f426e19bfd10c5d877a`, local annotated
`patch-1158`, carries version `git-8072-patch-1158-0-g793ee161a`. Publication and
runtime identity are separate from this source declaration.

The existing default-jump model now admits known finite pre-cost stamina,
models the same vertical scale before the native debit, and retains the result
only if the native jump succeeds. Existing default-context, posture, finite,
clear-path and actual-use restrictions still apply. Stock crouch and ground-duck
transition remain unsupported. The actual movement implementation, captured
fields, APIs, formats, flags, tiers and QC gameplay source are unchanged.

Published P1152/P1156 and P1154's 10/15ms TAS-clock integration are retained.
The normal Windows builder also serializes plugin metadata packaging: two
parallel builds reproduced ZIP temporary-file failures in different plugins.
Engine compilation retains the requested parallel job count. This does not
attribute the underlying ZIP temporary-name/file-access mechanism.

## Executed pre-commit evidence

These tests used the current published TAS server header, not just the earlier
parent. Their native stamp was `git-8071-patch-1154-0-ge6e5e3b73`; they are NOT
final-tag, installed-image or ARM evidence.

- Untreated production plus the same new tests: 1428 pass and exactly 20
  predicted new failures. Contacts, accepted jumps, pool debits and neutral/body
  controls execute; absence of output is not acceptance.
- Implemented candidate: all 1448 checks pass, including 249 new checks. Nine
  earlier finite-admission expectations are explicitly updated for the widened
  supported context; they are not unchanged historical expectations.
- New controls compare the pure model with the actual native jump, distinguish
  pre/post-cost scales, exercise zero/half/three-quarter scales, and verify body/config
  preservation. Seven posture/mode contexts include observed/unobserved/neutral
  arms, earlier accepted use and speculative/no-use restrictions.
- Both required host images were fully rebuilt after the published TAS-header
  change. The initial full wrapper failed plugin ZIP packaging. Failed logs and
  available partial outputs remain retained; they are not reclassified passes.
  Rebuilding the failed packaging cells through the corrected official builder
  completed all seven images with aligned metadata in all five plugins.
- An earlier subject run passed all 249 new checks but failed one obsolete
  P1139 expectation. That run remains failed; a changed-source execution after
  the explicit expectation correction passes all 1448.
- The 14 current installed Windows native files and 12 actual program/symbol
  targets stayed byte-identical during these isolated checks. This is not a
  whole-data-domain preservation, deployment or current-program runtime claim.

## Remaining delivery gates

Fresh independent whole-feature reviews, clean final-tag Windows/ARM builds,
qualified regression/reader evidence and frozen native-only promotion are still
pending. Runtime programs must be preserved from their actual current identity;
a stable test-program fixture is not permission to deploy it. Pi work requires
fresh recorder-part namespace/union, actor/FD and on/off-box member preservation
checks at the actual execution boundary. Historical failed preservation checks
are not waived or recovered by this source change.

No backend operation, program promotion, Build/release, human feel, ranked-finish
or full consumer-bank completion is claimed here.
