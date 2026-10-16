# P739 — live mode2 wire-annotation barrier

## Problem and change

The owner's actual OpenGL snapshot near the bad Kitsune angle reports383 raw,
375 gathered commands,7 admitted planes,status-3,18 edges and190 work. Most
commands are procedural stock CSQC wire annotations, not the12-command static
world fixture. They interleave by centre depth and the conservative unsupported-
slot guard abandons the world-plane refinement. The static pose/ray passes did
not establish live all-angle correctness.

P739 recognizes only stock `fill_trans` scenetris wire annotations in the root
perspective standard pass and retains their legacy post-world layer. Their
normal opaque depth test and widths are unchanged: no xray, missing lines or
extra callback builds. Relative annotation ordering remains stable. As with
mode1, annotations are drawn after translucent world surfaces, not attenuated
by them. Custom/remapped/multipass/deforming shaders, other callbacks/models,
fog/VBO/extra flags and recursive/orthographic cases remain conservative.
Modes0/1/default1 and the graph algorithm are unchanged.

The secure local `r_blendtrace` command arms one root pass, reports anonymous
view/command/graph data and disarms. It prints no names, GUIDs or pointers and
does not change rendering. No giant dump is required for acceptance.

## Controls and limits

- One stock wire command deliberately interleaved between the affected ramp
  faces ACTED: actual-C `annotation_layers_ok` fails before the fix and passes
  after it. The annotation is retained at the end and its original callback
  runs exactly once; source slice/range handles remain intact.
- Normal,HEXEN2 and both fast-math variants pass, as do21 deliberate regression
  controls. Removing only the new annotation-layer assignment fails the new
  oracle. Eleven unsupported annotation contexts are rejected.
- The first test setup had a wrong type/function-call arity, then a retention
  assertion used an invented ID instead of the existing callback's `b->id`.
  Those failures are retained/excluded, not product regressions. The direct
  compiling RED and final GREEN use the actual four-argument rotation contract
  and exact existing callback identity contract.
- The entire default1/dispatch source suffix is byte-identical to public P738.
  Existing LSP alignment/tidy diagnostics are untouched; native build has74
  baseline compiler warnings and0 new. All7 native products built successfully.
- The portable regression models the specific barrier mechanism, NOT every
  command in the375-command native frame. Owner live angular acceptance remains
  **PENDING**. Do not substitute these controls for that verdict.

## Native provenance and delivery

- Clean engine feature: `87df379ec1989302b037acfe4f49b659eae1be84`.
- Tag: `patch-739`; stamp: `git-7328-patch-739-0-g87df379ec`.
- Built in the owned isolated tree on published P738 plus the local diagnostic
  and feature commits; no peer's uncommitted source was included.
- Both normal clients deployed/hash-verified at2026-10-16T15:37:39Z:
  `C:\FTESurf\ftesurf64.exe`, `C:\FTEQuake\fteqw64.exe`.
- Both SHA256:
  `5aa2d4e459f9452754077f9f24cb86412612af1e90e0387e264f6d372ef35b53`.
- Both `.prev` files are hash-verified P737, client SHA256
  `6694363b9fa69eb02c0e5ea4643b2dd71ac476d73935166d227ae18f1d765130`.
  Older rollback copies remain in the owned delivery evidence.

This is a renderer-only CLIENT delivery. Plugin sources/headers are byte-
unchanged since P737 and all5890 shared dependency files match the original
pre-P737 snapshot. Installed known P737 modules therefore retain the exact
same ABI. Other8 native deployment destinations (including DLLs/server) remain
byte-unchanged; no progs/config/saves, QC Build, Pi or release update occurred.
No game process was stopped. The existing successful deployment transaction's
all-target locks/backup/swap/verify/rollback kernel was reused byte-identically;
only metadata parameters and a guarded client-only selection were added.

Local detailed evidence/receipts remain under
`C:\FTESurf-worktrees\mapvisual-01a13061\ramp-centre\`:
`annotation-red-direct.log`, `annotation-green.log`, `build-p739.log`,
`build-p739-review.json`, `prebuild-p739.json`, `delivery-p739/deployment.json`.
No raw private console/session/player output is included in this public note.

## Human check still needed

Exit the OLD `ftesurf-blendtrace64.exe` and launch normally. The alternate exe
contains the earlier logger only, not P739. With mode2 and zones ENABLED, turn
between the saved views and farther right. Works/still-flips is sufficient.
If it still flips, only the `ALPHATRACE result` line is needed. Keep the backlog
issue until live acceptance. All4 original save camera records remain on disk;
no player profile restoration/copy was attempted.
