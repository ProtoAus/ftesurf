# P710 — compatible game and package presentation source candidate

## State and ownership

2026-10-14 UTC: prepared, compiled and offline-tested; **not deployed or released**.
P705 art and P710 visual/runtime acceptance remain gates, not implied by source
publication. No GPU/game process, live service, public feed or player installation
was used. The completed rebrand2 root is retained evidence and was not repopulated.

Initial isolated game base `e27f2c88af25cd0d6ba6827b883d35cb8d1b01bb`, engine
ledger base `b4c9f82e418e9da28c1832aeb169e289e28e49a3`. During verification peer
P708 published; these owned worktrees fast-forwarded cleanly to game
`594e6931b25949c39bc1c5ff4ee4d4fd31046d4e` and ledger
`30d39532016015a5e895e72869563ee5bbbc9f62`. Peer changed launcher tests/docs and
patch metadata, not the presentation sources. Refreshed both origins and scanned
patch headings/untracked pNNN tests; final publication refresh found peer
`tools/p709trainer-claim.md`, so relinquished provisional709 and claimed **710**.
Also fast-forwarded to game `2c2cb20ce9bfc2480b4940d5aba521ae1d4c501e` (KSF
shipping tools/docs only, no reviewed presentation changes). Source/review
receipts retain their original P709 provenance; this product entry is P710.
Shared source checkouts and peer work were not reset, stashed, built or deployed.

Workspace/evidence: `C:\FTESurf-worktrees\rebrand3-20261014T162411Z\`.
One parent product/integration writer in `qc/`, one isolated package writer in
`package/`, parent-only engine ledger in `engine/`; worker handoff preceded
integration. Package patch SHA256
`5c9212f849ebe2b899b6fa76c46bab3c505069a5047e24d837fabc89cd5c7da8`.
Independent fresh-context source review is retained in
`artifacts/presentation-review.md`. It caught the CSQC boot diagnostic's active
harness contract: the producer was restored exactly rather than altering around
30 readers, and a new source assertion guards it. Narrow repair review is in
`artifacts/marker-repair-review.md`; final disposition is recorded in `OWNER.md`.
The review is not visual, runtime, archive or live acceptance.

## Deliberate change boundary

- `default.fmf`: formal NAME only. GAME/BASEGAME, downloads, icon path and technical
  identity stay legacy. Native engine resources/icons were not rebuilt.
- Player-facing menu/update/consent/help/error/console copy, HUD map title, short
  WOS board/profile/native-score badges, and local/server fallback hostnames.
- One WORLD OF SURF label for crisp, additive halo and feedback menu passes;
  existing native 48px font rung. PIL font metrics observed 226px new title at48
  versus208px old at80; this is NOT an engine screenshot or clipping proof.
- `Lob_Title`: exact case-insensitive old/new prefix recognition with a non-empty
  suffix. Prefix-only/unrelated names remain whole; empty host uses the address.
  This routine compiled but has NOT been executed by these source audit tests.
- Base lobby config and all12 lobby hostnames; no running lobby/config swap.
- Current README/service headings, generated release/install/legal human copy
  and Linux wrapper errors. Commands, legacy archive/root names and truthful
  external/historical FTESurf references stay intact, including the existing
  Discord channel. FTEQW/GPL/source/third-party provenance remains.

Unchanged: executable/scripts/gamedir/config/data/resource names; evidence
writers/readers and signed statements/tags; `ranked` storage/API tier; command
filter `ftesurf`; release/updater signatures/key/permissions/allowlist/feeds;
account URL/default/realm/callback; canonical/social browser-base switch;
repository links, ENGINE commit/tag, native binaries and QC Build number.
No saved player hostname/config migration is introduced. The exact
`FTESurf CSQC loaded` acting-control diagnostic stays unchanged deliberately;
existing startup/reload/count/negative-reload readers still recognize it.

## Predictions, controls and evidence

Pre-registered in task `OWNER.md`/`artifacts/PLAN.md` and package handoff:
new human strings must act in authored and compiled outputs; actual old-source
controls must fail those assertions; only explicit display changes may differ
from the compatibility source, and updater/physical deny regressions must still
act. Silence or missing generated content is not success.

Run commands from the isolated game worktree unless stated otherwise:

| Command / check | Result and boundary |
| --- | --- |
| `cd src; pwsh -NoProfile -File build.ps1 -Jobs 8 -NoDeploy` | Three VMs, zero warnings; scratch products only. First attempt failed to find ignored compiler in engine release, before any compile; copied one verified compiler from `C:\FTESurf\src\fteqcc64.exe` and reran. Both failure and successful logs retained. |
| `python -B tools/test_product_brand.py -v` | 6 frozen-source audit tests pass; all other QC/modules/manifests/account URL match baseline. |
| `python -O -B tools/test_product_brand.py -v` | Same6 pass; checks do not vanish under optimized Python. |
| `python -B tools/test_product_brand.py --source-ref e27f2c88af25cd0d6ba6827b883d35cb8d1b01bb -v` | Acting legacy control exits1 with29 visible/new-prefix/title subtest failures; unchanged-module and machine-mutant checks pass. Not a simulated old page. |
| `python -B tools/test_package_brand.py -v` and `python -O -B tools/test_package_brand.py -v` | 5 each pass; exact explicit prose reconstruction, unedited helpers equal baseline; LinuxTop/archive/site/engine-name mutants rejected. |
| `python tools/test_package_brand.py --source-ref e27f2c88af25cd0d6ba6827b883d35cb8d1b01bb -v` | Acting old-source control exits1 with4 copy failures; other contract/history tests pass. |
| `python -B tools/test_rebrand.py -v` | Existing7 web/art/storage/wire checks pass. No browser or game rendering. |
| `python ../artifacts/marker_predicates.py` | Extracts and executes actual existing runlines, UI negative-reload and P603 lifecycle predicates against9 small log controls. Preserved producer accepted; absent/incomplete/unexpected reload and wrong-count logs refused. No runtime harness/game invoked. |
| `python -B tools/test_updatefeed.py --work-root ../tmp/integrated-feed -v` | Existing12 actual signer/feed/allowlist controls pass using synthetic test key and tiny files, not public publication/native updater. |
| `pwsh -NoProfile -File tools/test_release_deny.ps1 -WorkRoot C:/FTESurf-worktrees/rebrand3-20261014T162411Z/tmp/integrated-deny` | Production tripwire accepts actual tiny baseline stage/archive; individually refuses7 runtime/backup paths in both physical forms. |
| `python tools/test_shipguard.py --work-root ../tmp/package-shipguard` in package lane | BLOCKED before tests: `ship set names a directory that does not exist: ftesurf/particles`. No pass claimed or allowlist weakened; no install/content library copied to hide it. |
| `sh -n ftesurf.sh src/release/linux-pack.sh`; `bash -n src/release/linux-bootstrap.sh`; PowerShell Parser::ParseFile on release.ps1 | Syntax-only passes; no release script execution. |
| Python LSP diagnostics; `git diff --check` | No collected diagnostics or whitespace findings. Not a compiler/runtime proof. |

Source audit tools intentionally freeze this migration boundary to e27f2c8.
They are not generic guards prohibiting all future QC/release features: rerun
with `--source-ref <inspected-P710-commit>` to audit this historical candidate
once later features alter those modules, or explicitly maintain the expected
contract when evolving the migration. Source token/literal comparisons do not
substitute for invoking engine/game/menu routines.

Compiler SHA256:
`7ccb93d1683746247a11f9aebcb54706e54e7ade1100e9e1ea9d603683ea133e`.
Actual compiled outputs (not deployed):

| VM | Bytes | SHA256 |
| --- | ---: | --- |
| qwprogs.dat | 1049318 | `39c5c945457003fd5b32cfe214baed3df23786249e9b833bf197d694e755f3cf` |
| csprogs.dat | 5501942 | `b5dd849d17041287da7f09f18c8f00556e15fe5404e859be827207b88c0baacc` |
| menu.dat | 417194 | `373193f51f56869e80a0d16024cdfbfb9e49103423af44e54b2906272fd28847` |

Retained `artifacts/compiled_brand.py` reads real version7 string tables, not
source guesses: new full/short titles and both prefixes are present alongside
FTESURF-CONSENT/MAPDL/REC/RCPT, the unchanged CSQC boot marker and the legacy
account URL. Initial compiled/source/control receipts precede the marker fix;
`product-build-marker-repair.log`, `compiled-brand-repaired.log` and
`product-brand-repaired*.log` supersede their candidate hash/control counts. Compile date affects
product hashes; these are exact receipt bytes, not a timeless reproducibility
claim. Build/compiled/source/control/feed/deny/parse logs and subagent reports
remain under `artifacts/`; no raw private output or credentials are included.
Worker test-authoring encoding/escape failures were resolved and disclosed in
its report/failure receipt, not hidden as successful first runs.

## Next gates

1. P705 art choice and P710 actual narrow/scale/flat/panel/HUD/native-score and
   mixed-lobby behavior acceptance (`lextest.md`). Source/compile preparation
   does not complete Stage2 or Stage3.
2. Native title/icon/wrapper preparation, complete generated ship set, actual
   archive inspection, Linux execution, fresh install and legacy upgrade.
3. Separate privileged parallel-route deployment and external HTTPS matrix;
   keep old base authoritative until signed account-start drain or explicitly
   verified dual-callback policy. No blind callback redirect.
4. Signed old-client update bridge and clean-tree release dry-run before any
   public default/feed/canonical switch. No on-disk/repository migration without
   owner approval; preserve saved/custom hostnames and player data.

Publication, build, deployment and acceptance are separate states. This receipt
claims only this source candidate's measured compile/offline controls.
