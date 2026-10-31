# P1158 — finite-stamina takeoff in the existing status consumer

## Source and scope

Frozen native `793ee161a9baa8ba976f1f426e19bfd10c5d877a`, annotated
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

## Final frozen-source qualification

Producer QC `d620045b451ff775b3505e6b935d111918635dcd` and the frozen native
source/tag above have now completed:

- Two independent whole-feature source-review lenses. Two factual documentation
  findings were fixed and confirmed; all code/builder/player-note blobs held.
  All 4016 raw tracked files, own HEAD/index and tag were verified after review.
- Clean final-tag Windows Full build: all seven images, all five plugins freshly
  packaged serially. Host literal stamps and DECOMPRESSED plugin metadata stamps
  match; plugin archive offsets and CRCs pass. The failed raw-string expectation
  for compressed metadata was a retained caller error, not a build rerun/pass.
- ARM64 build from all 1124 canonical Git blobs. Server, HL2 plugin, symbols and
  every selected evidence member were independently read back off-box. Original
  plain Git-archive CRLF failure remains retained; the documented producer uses
  per-command `-c core.autocrlf=false`, not a global config change or guard waiver.
- Actual native self-tests: **1448/1448 on BOTH architectures**, including 249 new
  checks each. All 60 full five-map rows match across architectures, use the same
  three program binaries, and match retained P1152 rows exactly.
- Five existing source/literal-native regressions pass. Reader self-tests pass
  **949/949**. The current runs-only sweep checks 541 recordings, has 348 existing
  faults (no increase), and holds all 866 current record/sidecar member hashes
  before/after. This dataset differs from the older 540/707 snapshot; no identical
  old-input claim is made. The earlier default save-prefix refusal is unwaived.

The native seven-file Windows and three-file ARM cohort is frozen at source
`793ee161a` and version 8072. Verification-only documentation commits do NOT move
that tag/pin or rebuild the artifacts for prose. These checks use the stable
source-8ed test fixture (actual QW program hash begins `fcb5b5a7`), NOT the actual
current installed program cohort, human play or ranked acceptance.

## Native-only delivery — 31 Oct 2026 UTC

The exact frozen seven Windows images are installed in BOTH installs, with all
14 approved P1156 predecessors retained in `.prev` and every member of the
28-file rollback archive read back. Immediate program/LNO/config/data guards
remain unchanged. NanoPi server/HL2 are installed in all12 positively empty
lobbies, each restarted once without force. Every current native-namespace UNION
suffix-part archive member was individually verified ON and OFF box before
canonical staging or restart. Strict13 original actors, no open recorder FDs,
part identities and on/off-box archive authority are checked JIT under the short
sweep lock. All old data, programs/configs and backend files/unit/master birth
remain unchanged at the transaction boundary. No programs or backend are shipped.

Fresh copies of BOTH installed native clients naturally exit after downloading
the then-served CSQC, drawing the9-column/type14 board and reporting no QC errors.
Screenshots were read: empty kitsune/terms unaccepted, NOT human feel or ranking.
The first cold harness passes; the second original harness FAILS because its
mutable local expected CS advanced during concurrent program deployment. The
original post-cold SAME12actor gate also REFUSES changed lobby process epochs.
A separate read-only diagnosis retains both failures: native/predecessor pairs
remain ours, old Pi data and all part identities/bytes remain exact, current13
actors have no recorder FDs, and backend files/unit/master birth are unchanged.
Both Windows program/LNO sets and the Pi QW/CS programs changed; the writer is not
attributed by this lane. No repeated client, healthy restart, rollback, data
restore or backend operation is used to manufacture a pass.

A separate fresh current-program cohort now passes BOTH installed native/menu
cold checks using an immutable OFFBOX copy of actual Pi-served CSQC as the
expected authority, not mutable local Windows CSQC. Same current12 native/plugin
epochs, programs/configs, strict13 actor/no-FD census, old data and all part
identities/bytes, backend files/unit/master birth and current Windows preimages
are held before/after. Both new screenshots are read: empty kitsune/terms
unaccepted. The first fresh-cohort post-empty census refusal remains retained;
a separate fresh positive-empty live/directory/no-FD control precedes the
unchanged postgate on fresh volatile input, WITHOUT repeating either client or
restarting a healthy lobby. Its original transient cause was not captured; no
directory-lag explanation is invented. Original older-program/epoch failures are
not regraded. Source builds, qualification, installation and bounded current-
program cold checks are complete for P1158; broader bank/human/ranked stay open.
Historical preservation failures are not recovered or waived. No backend or
program promotion, Build or release is performed by this lane.
