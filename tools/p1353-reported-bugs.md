# P1353: reported prediction, label, zone-editor and texture fixes

Engine source/tag: `09262667df5afe01a9487809ebc868cd56caca4c` / `patch-1353`.
QC build source: `5b3ac8ace326e5a6a074e8e5422ac6ea7f74cf23`.
Later receipt-only commits do not change these artifacts. Build number unchanged.

## Changes

- **GoldSrc illusionary prediction:** the matching `bhop_goldsrc2` save at
  1:01.070 is beside authored skin=-1 `func_illusionary` model *304. The NanoPi's
  Q1 snapshot converted a negative float directly to unsigned: AArch64 clamps it
  to zero, so P919's existing client EMPTY-content rule never saw the tag.
  Convert negative skins through signed int; keep the nonnegative unsigned range.
  Server movement/collision rules and recording formats are unchanged.
- **Independent board labels:** `hud_lines_board` now controls board strokes and
  teleport joins, not the independently enabled number/name passes. Existing
  name/number settings still hide labels. Replay, trail and ghost switches remain
  separate. Hidden board strokes no longer enter native or QC path drawing.
- **Boarding energy:** preserve the existing pre-contact main label, retain the
  first contact sample's squared velocity, and draw its mechanical-energy change
  on a second row. The row obeys the energy/number settings and reserves its full
  height for label placement/final decluttering. It is a sample-to-sample change,
  not a claim of sub-tick collision-only loss. Stitches, breaks and non-ramp
  contacts do not invent a pair.
- **Clip snapping:** a guarded optional `getworldbrushfacepoint` CSQC builtin cuts
  the actual world collision-brush winding using the same plane cutter as
  `surf_view`. Queries are finite/bounded, world/map/host-frame scoped and capped
  at 64 vertices. An editor-only nonsolid trace probe includes player clip; both
  geometry and grid modes aim at the same face. Old engines retain render-face
  snapping. Existing real-corner/flat-plane filtering also applies to clip faces.
- **Teleport labels:** snap the requested size onto the loaded font's baked
  ladder and center at integer coordinates instead of drawing fractional sizes
  and fractional origins.
- **Dragonfall:** the saved view points along the alpha-tested, point-sampled
  `makkon/gothic_stone/{stn_gr02_sand1` floor. Its VTF has ten mips. Authored point
  filtering no longer disables user-selected mip blending or opt-in anisotropy
  on mipmapped world images. Nearest magnification is retained. UI/nonmip images
  keep their prior filtering; existing anisotropy factor 1 remains an opt-out.

## Acting verification

Public task evidence: `C:/FTESurf-worktrees/bugs6-01a1b058/artifacts/` and the build
logs in its parent. No private player identities, raw rollout inventories or
preservation archives belong in this public report.

- Final clean-commit `build.ps1 -Engine -Full -NoDeploy` completes. Qualified
  compiler SHA256 is
  `c24ede65af01d6c7e20d5d1dbd2190a9295a38fb0e109843f75e52166da22f74`:
  all three VMs compile with **zero warnings**. This corrects the earlier full-hash
  transcription; retained `qualified-compiler.json` and `qualified-ui-summary.json`
  already identify these actual bytes. The full Windows rebuild has 74 inherited
  native compiler warnings, no new warning sites. The sole warning in a modified
  unit is the unchanged `PF_resourcestatus` address warning.
- `tools/p1353_skin.c` has ten independent constant-bit expectations. On actual
  AArch64, all five original negative inputs become zero; corrected values pass
  all ten and leave the five nonnegative controls unchanged, including 2^31.
  Windows also passes the corrected expectations. This is an acting producer
  conversion control, not fabricated owner movement acceptance.
- Windows `pm_selftest` actually runs **1608 checks, zero failures**. A first empty
  stdout/exit-zero invocation did not establish execution and is retained as
  unmeasured; the later interactive command has all individual checks and the
  positive completion marker.
- A real dedicated socket and `reported_bugs.cfg` load the same public voyager
  fixture. Board path on/off retains two name labels; disabling labels removes
  them. The independent numeric label remains visible without the path.
- **32 boarding rows** agree with `(z_post-z_pre)+(v_post^2-v_pre^2)/(2*g)`, with
  gravity explicitly 800 and ordinary integer-display/printed-height rounding.
  Maximum display discrepancy is 0.47219 height units. A screenshot shows
  `boarding dE -24` below the existing main contact information.
- On `surf_sinsane_ez`, **four reached invisible clip corners** snap to exact
  coordinates with no render surface. **Four grid controls** stay on that same
  collision plane when geometry snapping is off. An earlier too-close camera
  correctly failed to reach the screen-space snap radius; four other probes hit
  an intervening face and are not counted. Existing render-surface snap regression
  also passed. Teleport text is inspected in the editor.
- Recreated the matching Dragonfall saved view. The grazing pattern improves on
  the tested NVIDIA OpenGL driver. A **280,000-pixel magnified crop is byte-identical**
  before/after; this proves the tested close-up pixel detail is preserved, not a
  frame-rate improvement or all-GPU acceptance. Older Intel behavior is untested.
- The initial install compiler `7ccb93d1` produced two familiar warnings and is
  explicitly **not** the qualified final compiler. Those early controls/logs are
  retained; final candidate UI/clip verification uses c24 and freshly seeded CSQC.
  Source was advanced to include the published P1350–P1352 changes before final
  qualification; no unrelated canonical dirty work is included.

## Clean-commit qualification and delivery — 6 November 2026 UTC

- **Windows, 19:47:25 UTC:** both installs updated using the existing deployment
  transaction. All **28 targets** match the frozen artifacts. All **18,642 protected
  files** are unchanged; **52 predecessor/prior-prev preimages** are archived.
  No game process was killed. The shared released dependency cache was read-only:
  all **1,399 input hashes** still match after the full build.
- **ARM:** 1,131 Git-blob source members verified before the standard native/server
  and matching HL2-plugin build. Its generated shader header differs only in the
  generator-path comment; exact substitution reproduces the Git header. Both
  Windows and ARM run **1,608 numeric checks, zero failures**. All **90 named
  physics rows across six maps** match bit-for-bit, including acting prop,
  rotating/wrapped-prop and Sedona ride controls.
- The documented archived-VM **Pin7** reference passes **9,194 ticks / 9,192 rows**;
  Voyager passes **4,418 / 4,418**. These are historical reader controls, not
  latest-world admission. The latest-VM Voyager attempt's 52-row physent HOLD is
  retained, not regraded. No modern recording-format/admission change is claimed.
- **Lobbies, 20:30:04 UTC:** paired server/HL2/QW/CS promotion; **12 restarted,
  zero skipped**. Full players-and-spectators status proved all empty. Before any
  role staging/restart, all **8 recorder parts** and **183 resume-domain members**
  were archived on-box and individually verified off-box, including resume state
  metadata and cleanup context. All **48,556 protected files** are unchanged;
  zero missing/changed or new protected files. Configurations are unchanged.
- An independently published backend generation changed during archive transfer.
  The original guard refused **before role staging**. Original actor-bound
  inventories/archives were preserved unchanged; a separate fresh closure proves
  the original actor retired, data identities/bytes/metadata still match, and
  current native/backend actors have no recorder/resume FD open. The exact guard
  has an acting read-only positive and two refusal controls. Only the backend
  boundary binding was refreshed; no native-pinned handoff was bypassed.
- Final readback at **20:35:19 UTC** verifies all four canonical hashes, all
  **12 actual native process hashes**, **12 loaded HL2 plugin inodes**, directory
  and full status replies, and the unchanged current backend generation. The
  canonical sweep lock is released. No menu VM was shipped to a lobby. A later
  read-only smoke finds both actual current-boot QW load/initialization markers on
  all **12 process/stdout bindings**, with **zero VM/fatal errors**. Initial
  journal/timestamp/marker/log-append observer failures remain retained; empty or
  wrongly matched logs were never counted as passes.
- CSQC cache **`226f4924.dat`** is seeded on both installs and the Pi. Its SHA256
  matches the shipped CSQC. The existing contribution-code catalog received one
  additive hash (**75 → 76**); all prior bytes are preserved. No service restart,
  detector-policy change, historical regrading or backend generation activation
  was performed for that catalog append.

### Installed artifact fingerprints

| Artifact | SHA256 |
| --- | --- |
| Windows client / `ftesurf64.exe` | `14a9c9bb029a1506b08e16b538671efd0b9dd65175b57c42c637117eeb97361a` |
| Windows dedicated server | `ceb706a5d6a7471a82886bc29661e2f242041b8fd5f888cf838546fe53066e52` |
| ARM dedicated server | `7ae9b6509be357b1b13c76894df139df51a75f384bbbfbfe413b69cb9afe231a` |
| ARM HL2 plugin | `2aad7f3b94268106e851bf83ede3421b32e1ee3a32be91c8c26f29ac4a2b4cb8` |
| `qwprogs.dat` | `aa92900514f44e407b122838c51f9ee82a7c87df09f0cc7510222451ac565d17` |
| `csprogs.dat` | `09fec3b5fc10f31f737ef830aaf588b61fe573c2b5f1e35e288c933ef1b06deb` |

Original unqualified compiler, invocation, missing-content, compile-only memory-cap
and preparation-boundary failures remain retained. None is an uninterrupted-clean
claim. Full raw rollout inventories, player identities, archives and rollback
preimages remain private.

Owner feel/visual confirmation remains pending in `lextest.md`; automation is not
owner acceptance, measured performance or all-GPU coverage. No Build/release bump,
recorder grammar, collector or mover-policy change is part of this patch.
