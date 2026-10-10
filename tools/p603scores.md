# Opt-in native scoreboard staging (historical p603 harness names)

Patch 603 is now published for unrelated reader work. The p603 filenames and
older checkpoints below preserve evidence continuity, NOT a product-number
reservation. Fetch both repositories and reallocate max+1 before publication.

## Patch 607 — one board layout, 2026-10-10

Patch 607 removes the classic look: there is one +showscores layout and no
`ui_style`. For these tools:

- `--style` is gone from `p603scores.py` and `p603perf.py`; every arm runs the
  one layout. The Patch 606 commands below that pass it are history.
- `ui_gallery.py` takes `--sizes WxH ...` (one arm a size) where it took
  `--styles`, `--width` and `--height`; `--against <rig or arm>` writes pairs. It
  shoots the plain HUD first, and reports a rig whose window took the foreground
  as INTERFERED: the owner's desktop reached it, so no shot can be trusted.
- `test_ui_theme.py` compares two builds (`--control-qc`, or `--control-arm` for
  a gallery that already ran) and proves each panel was on screen (P0).
- `p603life.py`'s dock arm narrows the canvas to 560 (`vid_conwidth` is live in
  these rigs); raising hud_scale no longer docks the room list.
- `scores status` prints `cols <5-9>` and `type <px>` for the last drawn frame.

### Commands

    python tools/test_ui_theme.py --engine <exe> --server <sv> --control-arm <Patch 606 gallery>/style1 \
        --subject-qc <progs> --library <install gamedir> --out ROOT/runtime/<tag>/look
    python tools/ui_gallery.py --engine <exe> --server <sv> --qc-artifacts <progs> --library <install gamedir> \
        --sizes 1280x720 1024x768 800x600 640x480 [--against <rig>] --out ROOT/runtime/<tag>/gal
    python tools/p603scores.py ... --arms legacy --out ROOT/runtime/<tag>/board
    python tools/p603scores.py --dense [--renderer d3d11|vk] ... --out ROOT/runtime/<tag>/...
    python tools/p603scores.py --life ... --arms native1 native2 legacy --out ROOT/runtime/<tag>/life
    python tools/p603perf.py run [--rows 20 --repeats 3 --samples 5] ... --out ROOT/runtime/<tag>/perf

### Results (the tree of the Patch 607 commit, engine patch-606 binaries as installed; ROOT/runtime/one3, one4)

- **Build.** Three progs at 0 warnings; qwprogs.dat byte-identical to Patch
  606's (no server QC changed). csprogs.dat is 40 KB smaller.
- **Look gate** (`one4/look`): 30 checks, 0 failed. All 13 panel states are on
  screen (P0) and pixel-identical to the Patch 606 final build at `ui_style 1`
  (`ROOT/runtime/final606v/theme/subject/*/style1`); the mutant (the theme's
  butter moved) differs on `gfx_page1` (1,745) and `scores_local` (2,099) and by
  0 on `hudedit_list`; the parked mouse reads `tip 1 [cs_tier1]`. Its first two
  runs did not grade: one read 16 and 18 "changed" pixels on the map picker, all
  in the panel's rounded corners where the animated backdrop shows (the regions
  now sit six pixels in), and one exited 2 because the mutant's rig window took
  the foreground.
- **Other sizes** (`one3/gal`, against the Patch 606 arms at the same size):
  1280x720, 1024x768 and 800x600 are identical in every in-game shot but for the
  ping digits. `scores status` there: type 14 with 8 or 9 columns, type 12 with
  7 or 8, type 12 with 5 or 6. 640x480 is new: type 8, 6 or 7 columns, the room
  list 200 wide beside the board, where Patch 606 fell back to the classic
  layout. Its small labels are larger than its rows (BACKLOG).
- **Board actions, legacy arm** (`one3/board`): 0 failures, the three
  source-switch clicks included. **Dense** (`one3/dense`): native1, native2,
  legacy, 0 failures.
- **GL six arms** (`one4/gl`): 0 failures; reader controls 69/69 once the
  one-pixel control followed the table's rectangle (it was a fixed (568,279),
  inside the rank crop only in the classic layout: 68/69 before). **Hostile
  names** (`one4/names`), **D3D11** (`one4/d3d11`), **Vulkan** (`one4/vk`): 0
  failures each.
- **Lifecycle** (`one3/life`): the dock arm passes in both native arms at a
  560-wide canvas (`cols 5 type 8`, list 200 wide and docked, `clipped=1 gap=1
  hover=0`). The suite's two other failures are the stale ones BACKLOG names,
  identical on Patch 606's tree (`ROOT/runtime/base606/life`).
- **Other SUI gates.** `test_ui_modern.py` 27/27 (its two classic checks are
  gone, one "the open editor changes pixels" check is new) and its unit tests
  9/9; `p498keys.py` 16/16; `test_water_menu.py` 0 failed; the five
  `compare_chip_smoke.py` seams each match once.
- **Cost** (`one4/perf`, QC UpdateView median us/frame, 20 rows, open): legacy
  1194, no plugin 1197, native 1121; closed 355-459. Inside Patch 606's range
  for the same layout. At the default 6 rows the tool's screenshot crop read 893
  bright pixels against a bound of 1000 in every arm: it was placed on the
  classic rows. Moved to the layout's first six rows, the same rig regrades at 0
  failures (`one3/perf6`).
- **A batch that would not stop.** `one3` ran while a batch I had stopped
  (`one2`, an abandoned build) was still executing its remaining steps: the
  harness's stop did not end the script. Nothing from `one2` is cited. `one3`'s
  rigs are separate directories and ports, its editor rig's provenance shows
  this build's csprogs, and every step in it passed; a second game running can
  fail these checks (focus, timing) but has no way to pass one. The gate script
  now takes a stop file and waits while another game is running.
- **Not run:** soak; `compare_chip_smoke.py` itself.

### Deployment — Patch 607, 2026-10-10

Published: this repository `5474c48`; ftequakers gains only the
`ENGINE_PATCHES.md` entry. Progs built from the commit: csprogs
`162aaf018682ca0b`, menu `d38891771c3ae376`, qwprogs `5e7fd33b3d0beac1`
(unchanged), byte-identical to the build the gates above ran on. Deployed
2026-10-10T07:16:07Z to `C:/FTESurf` and `C:/FTEQuake` by the guarded copy
(ROOT/tmp/deploy607.py, receipt ROOT/artifacts/deploy607-receipt.json):
`csprogs.dat`, `menu.dat` and their `.lno` in both (8 files), each destination
first checked against the hash recorded after the Patch 606 deploy, the live
file kept as `<name>.prev`, the copy verified. The binaries are Patch 606's. No
game was running from either install.

**The Pi, 2026-10-10 07:28-07:29 UTC, on the owner's request.** `build.ps1 -Pi`
from the clean worktree at `5b3f181` (the commits after it touch no game code),
0 players in all 12 directory rows. Before: qwprogs `76f4a7bf24f2d759`, csprogs
`108a66c5b0230432`, the 8 Oct pair. After: qwprogs `5e7fd33b3d0beac1`, csprogs
`162aaf018682ca0b`, the old pair kept as `.prev`. The two qwprogs differ in two
bytes, fteqcc's compile date, so no server QC shipped; what the lobbies now
serve is the client code of Patches 595-607. `cfg/default.cfg` already equalled
the repository's (`8fd357ac59147c8a`). Read back in one ssh call: all 12 units
active since 07:28:57-07:29:07, no `.new` left behind. `tools/pi_lobby_smoke.py`
(as `ROOT/tmp/pismoke.py`, rig `ROOT/runtime/pismoke/20261010T183134`): a fresh
client with no csprogs joined lobby 1 on surf_kitsune, the file it downloaded
hashes to the build, and the board drew (`cols 8   type 14` at 1280x720). The
tool as committed then did the same on lobby 2
(`ROOT/runtime/pismoke/pi-lobby-smoke-20261010T183415`). Its first run measured
nothing: a rig manifest of my own was refused with "Game mismatch", so the rig
carries the real `default.fmf` now. The native aarch64 engine and surfd were
not touched.

## Patch 606 — the board under `ui_style 1`, 2026-10-10

Patch 606 gives +showscores a second layout (`Scores_DrawModern`) behind
`ui_style 1` and themes the provider. `ui_style 0` runs the board code the
sections below measured. What changed for these tools:

- `p603scores.py --style 0|1` and `p603perf.py --style 0|1` set `ui_style`
  before the board opens. Unset leaves the default (0).
- The modern layout keeps the classic sui ids, so every click, focus and
  hand-off check runs unchanged against it.
- The basic suite now clicks the source switch for real (`p603 move sb_t0`,
  `sb_t1`, `sb_t2`, then `p603 tab <label>`): Online, Segmented, Local, in
  either style. It clears `lobby_dir` first so an online tab cannot reach a
  real board from a rig.
- `p603scores.py` compiles its fixture csprogs from the WORKING TREE's `src/`;
  `--qc-artifacts` supplies menu.dat, and qwprogs.dat outside `--dense`/`--http`.
- `p603perf.py` proves the native route from a screenshot by counting the
  themed provider's own background. It counted ImGui's default blue until the
  theme removed it.
- The p603 rigs carry no `gfx/ui/roundmask.png`, so they draw the modern layout
  square-cornered: the missing-mask fallback, not the shipped look. The shipped
  look is `tools/ui_gallery.py`'s.

### Commands

    python tools/test_ui_theme.py --engine <exe> --server <sv> --control-qc <Patch 605 progs> --subject-qc <progs> \
        --library <install gamedir> --out ROOT/runtime/<tag>/theme
    python tools/p603scores.py --style 0|1 ... --arms legacy --out ROOT/runtime/<tag>/board<style>
    python tools/p603scores.py --dense --style 1 ... --arms native1 native2 legacy --out ROOT/runtime/<tag>/dense1
    python tools/p603perf.py run --rows 20 --repeats 3 --samples 5 --style 0|1 ... --out ROOT/runtime/<tag>/perf<style>
    python tools/ui_gallery.py --engine <exe> --server <sv> --qc-artifacts <progs> --library <install gamedir> \
        [--styles 0 1] [--width W --height H] [--renderer gl|d3d11|vk] --out ROOT/runtime/<tag>/...

### Results (QC 7027eed's tree with engine d100d856d's, before the patch entries; ROOT/runtime/fix3b)

- **Build.** Three progs at 0 warnings; qwprogs.dat byte-identical to the
  installed one (no server QC changed).
- **Theme gate** (`theme/`, rigs `ui-gallery-5rvel_3x` control,
  `ui-gallery-encl20ng` subject, `ui-gallery-0eomktex` mutant): 13 panel states
  at `ui_style 0` differ from the Patch 605 progs by 0 pixels; all 13 differ at
  `ui_style 1`; the mutant (one classic colour moved) is caught on the three
  hud_edit shots, 76,248-76,734 pixels, and reads 0 on the save-lock shot; the
  parked mouse reads `tip 1 [cs_tier1]` at style 1 and `tip 0 []` at style 0.
  32 checks, 0 failed.
- **Board actions, legacy arm** (`board0/p603-scores-*`, `board1/p603-scores-*`):
  0 failures in each style, the source-switch clicks included.
- **Dense, `--style 1`** (`dense1/p603-scores-*`): native1, native2, legacy,
  0 failures.
- **Other SUI gates.** `test_ui_modern.py` 28/28, `p498keys.py` 16/16,
  `test_water_menu.py` 0 failed.
- **Cost, reported, not gated** (`ROOT/runtime/fix3p`, `fix3q`, `fix3r`; QC
  UpdateView median us/frame, 20 rows, board open; legacy / no-plugin / native;
  the machine was shared with the owner and another agent's jobs):
  final build, modern, 15:57: 1594 / 1537 / 1465 (closed 458 / 429 / 481);
  final build, classic, 16:01: 1329 / 1157 / 1000 (closed 400 / 364 / 392),
  `[focus] window is foreground` in every arm;
  first review copy (a07ae96), modern, 16:07: 1208 / 1190 / 1114 (closed 364 /
  454 / 365); final build, modern, 16:12: 1169 / 1173 / 1075 (closed 346 / 352 /
  337). Draw calls 127 and about 18,250 indices in every modern legacy sample.
  Two runs of one build differ by 36%; no layout or build is shown cheaper, and
  the 14:37 figures an earlier draft quoted (modern 1074, classic 1203) are one
  more sample of the same noise.
- **Not run:** D3D11 and Vulkan in the modern layout, the old-plugin,
  old-engine and no-plugin arms in the modern layout, hostile names, soak.

### Final build and Windows deployment — Patch 606, 2026-10-10

Published: ftequakers `93828165c` (Patch 606, tag patch-606); this repository
`55c4057`.

Build of exactly those commits, `build.ps1 -Engine -Full -NoDeploy -Jobs 4`, exit
0, with `SVN_VERSION=git-7144-patch-606-0-g93828165c` and the matching
`SVNREVISION` in the environment (a worktree build stamps nothing otherwise).
Client and server both contain that string and not Patch 605's. 426 lines of the
log hold the word `warning`, the same count and kinds as Patch 605's final build:
349 from make, 74 compiler lines (none in `plugins/ui_imgui`, which builds under
-Werror) and the three `Done. 0 warnings` of the progs. The three progs are
byte-identical to the build every QC gate above ran on.

| sha256 (first 16) | file |
|---|---|
| `6fb2ff02a559c314` | fteqw64.exe (installed as ftesurf64.exe / fteqw64.exe) |
| `13ecc334cc2ba536` | fteqwsv64.exe |
| `f93b8f9dacc95a55` | fteplug_ui_imgui_x64.dll |
| `d4d20d075c4a4c80` | fteplug_hl2_x64.dll |
| `966b302625f864f7` | fteplug_box3d_x64.dll |
| `bbdaa2bf4edd482a` | fteplug_cod_x64.dll |
| `700101dde5c28483` | fteplug_ode_x64.dll |
| `3ae1bba0b9224e0c` | csprogs.dat |
| `5e7fd33b3d0beac1` | qwprogs.dat (unchanged since Patch 605) |
| `c14493765bfabfe0` | menu.dat |

Rerun on those binaries, all 0 failed: host suites (629 / 3750 / 2872 per index
width and the model regression counts), GL six arms
`runtime/final606/gl/p603-scores-bt7apfp_` with 69/69 reader controls, hostile
names `runtime/final606/names/p603-names-ppiwjp2p`, D3D11
`runtime/final606/d3d11/p603-scores-jowgcrru`, Vulkan
`runtime/final606/vk/p603-scores-62qu9eu6`. Those run at the default `ui_style
0`: the classic board with the themed provider. Also `p603scores.py` legacy arm
at `--style 0` and `--style 1` and `test_ui_modern.py` 28/28
(`runtime/final606u`).

`test_ui_theme.py` on these binaries FAILED its first run: three classic menu
comparisons differed (8,949, 2,520 and 2,520 pixels: a hovered lobby cell and a
hovered close button missing in the subject). That rig's log holds `[focus]
window is foreground` across exactly those shots, and its parked cursor read
back as 321,1137, the real pointer; the control and the mutant, undisturbed,
agreed with each other on every menu shot. The rerun, with no foreground line in
any rig, passed 32 of 32 (`runtime/final606v/theme`). The gallery should say
"interfered" itself instead of failing; that is Patch 607's.

NOT rerun on the stamped binaries: p498keys, the dense suite at `--style 1`, the
cost runs.

Deployed 2026-10-10T05:51:29Z to `C:/FTESurf` and `C:/FTEQuake` by the guarded copy
(ROOT/tmp/deploy606.py, receipt ROOT/artifacts/deploy606-receipt.json): every
destination was first checked against the hash recorded after the Patch 605
deploy and opened for writing before anything was copied, the live file kept as
`<name>.prev` (replacing Patch 605's predecessors), the copy verified.
25 files match the build (21 replaced; `qwprogs.dat` and its line table were
already identical in both installs): the client, the server (second install),
all five plugins in both, and `ftesurf/{qwprogs,csprogs,menu}.dat` with their
`.lno` in both. No game or server was running from either install, and none was
started from one. The owner's `ftesurf.cfg` was read for four settings
(`ui_style`, `ui_native_scores`, `vid_renderer`, the window size) and not
written. **Not deployed to the Pi**: that restarts the public lobbies and is the
owner's call, so on a public lobby the csprogs panels keep the old look.

## Published — Patch 605 (and 604), 2026-10-10

`ui_native_scores 1` is published as an opt-in; `0` (legacy) stays the default and
the fallback. The stage described in the checkpoints below was rebased onto
origin/main, reviewed, fixed and gated in the owned root
`C:/FTESurf-worktrees/imgui-ship-20261009T2050Z/` (ROOT below; its rigs are
retained until the root is retired). Everything was measured on ONE machine, the
desktop PC (RTX 2080 SUPER; this file said "laptop" until 10 Oct, wrongly), with
synthetic rows; this is not device, DPI, font or appearance acceptance — those are
lextest.md's. Known quirks: BACKLOG.md "Native scoreboard".

Engine source: ftequakers Patch 604 then Patch 605 (ENGINE.txt has the pin).
The gates ran on `build.ps1 -Engine -NoDeploy` builds of exactly that source
before the patch entries were written. The rebuild from the published commits
and the installed hashes are in the deployment record that follows this commit.

### Commands

    cd src; pwsh -NoProfile -Command "./build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot <engine> -QuakeDir <unused>"
    python tools/test_p603dense.py --fte <engine> [--control <p603dense_variant.py output>] --out ROOT/artifacts/...
    python tools/test_p601model.py --fte <engine> --out ROOT/artifacts/...
    python tools/p603scores.py --dense --fte <engine> --qc-artifacts <progs> --engine <exe> --server <sv> --plugin <dll> \
        --old-plugin <P601 dll> --old-engine <P601 exe> --arms native1 native2 oldplugin oldengine legacy absent --out ROOT/runtime/lean/gl
    python tools/test_p603dense_unit.py <that rig>
    python tools/p603scores.py --dense --renderer d3d11|vk ... --arms native1 native2 legacy absent --out ROOT/runtime/lean/<r>
    python tools/p603names.py --engine <exe> --server <sv> --plugin <dll> --qc-artifacts <progs> --control-qc <pre-fix progs> --out ROOT/runtime/lean/names
    python tools/p603perf.py run --rows 20|32 --repeats 3 --samples 5 [--arms absent legacy native] ... --out ROOT/runtime/lean/perf<rows>
    python tools/p603soak.py --fte <engine> --engine <exe> --server <sv> --plugin <dll> --qc-artifacts <progs> [--rows 6] [--set CVAR VALUE] --out ROOT/runtime/soak3
    python tools/vkenum_coldstart.py --control <unfixed exe> --subject <exe> ... --renderer vk --starts 20 --out ROOT/runtime/vkenum

### Results (final source unless a line says otherwise)

- **Build.** Three progs at 0 warnings; engine, server and five plugins link;
  wrapper exit 0. No engine warning sits on a line this work added. Both
  Windows installs byte- and mtime-identical afterwards.
- **Host.** 629 /2 bridge checks (597 plus the open budget), 2872 dense + 3750
  scoreboard per index width, 0 failed. Model/input regression 173/929/463 and
  110/701/184 per width, 0 failed. No `imgui.ini` left in the cwd. One-factor
  control, row cap 24 -> 6 in `scores.inc`: all 3750 originals still act and
  exactly one registered failure per index width.
- **GL, six arms** (`runtime/lean/gl/p603-scores-y2eqls4w`): 0 faults, reader
  69/69. The `dense_cursor` step (move while the table is not painting, then
  click without moving) opens row 0's recording. Control: the same arm on the
  pre-fix product source (`runtime/fix-control/p603-scores-9r7sfoqc`) fails
  exactly that check and opens row 8's.
- **Hostile names** (`runtime/lean/names/p603-names-7zpubzek`, 14 owner
  fields: control bytes, `^U`/`^{}` markup that decodes to them, overlong,
  surrogate, lone and truncated sequences, 200 bytes, 40 CJK): the table stays
  native in all four QC string modes (139 frames each, 0 rejected). Control:
  progs built before the sanitizer open once and close themselves (0 frames).
  Before the string-mode guard, `utf8_enable 1` + `com_parseutf8 0` fell back
  too (`runtime/names/p603-names-5rlwwu62`). Labels were read by eye, and the
  four screenshots are pixel-identical before and after the ASCII fast path.
- **D3D11** (`runtime/lean/d3d11/p603-scores-7xfj4a3_`) and **Vulkan**
  (`runtime/lean/vk/p603-scores-c56i_r30`), four arms each: 0 faults, renderer
  positively initialised, no device-lost line. Before Patch 604 D3D11 failed one
  check (capture upside down) and Vulkan's legacy arm crashed at startup; see
  that patch. D3D9 does not start on this machine.
- **Cost**, GL, uninstrumented progs, QC UpdateView median us/frame over 3
  cycles x 5 hundred-frame buckets, native / legacy / no plugin:

  | run | closed | open | after close |
  |---|---|---|---|
  | 20 rows (`runtime/lean/perf20/p603-perf-l2kyx8i0`) | 314 / 312 / 317 | 828 / 1050 / 1068 | 307 / 314 / 314 |
  | 32 rows (`runtime/lean/perf32/p603-perf-vhv9dw0w`) | 313 / 312 / 399 | 852 / 1095 / 1079 | 313 / 314 / 384 |

  Open is 0.78-0.79x legacy with fewer draw calls (106-107 against 131-134).
  20 rows is the closest equal visible work (legacy shows about 19.5); 32 fills
  native's 24-row page. Predictions written before the runs: open <= 1.5x
  legacy, held; under 2000 us at 32 rows, held; closed and after-close within
  10% of no plugin, held at 20 rows, and at 32 rows native matched legacy while
  the no-plugin arm itself read 85 us high for its whole process with identical
  pixels. **These figures move with the QC temp-string collector**: the same
  held-open table reads 822 us with the collector disabled and 1159 us with it
  cycling (`runtime/regime-gc2`, `regime-gc1`), and 1174 us in two long soak
  holds. Before the rebuild throttle the open figure was 1140-1196 us
  (1.03-1.09x legacy; `runtime/perf20`, `runtime/perf32`), and the first of
  those runs missed the after-close prediction by 17.5%. No GPU timing.
- **Churn and soak.** Per-cycle counters (live while open, released after,
  one open and one upload per cycle, nothing rejected) held on every cycle of
  every run: 150 slow cycles and 800 fast ones, each cycle stepping the font
  16 -> 24 -> 13. Memory took three runs, and the first two missed:
  1. `runtime/soak` (150 cycles, bounds of a few MiB on fitted growth): every
     arm failed, legacy included. Private bytes saw-tooth with the temp-string
     collector, so a fitted slope read the teeth and the leak control did not
     separate. It measured no leak either way, but it showed the native table
     making 5.4 MiB/s of garbage held open against legacy's 1.05, by rebuilding
     ~220 labels a frame. Fix: rebuild only on a change that moves a row,
     authority or input, else at 10 Hz.
  2. `runtime/soak2` (800 fast cycles, grade on the floor: min of the last
     third minus min of the first, bounds fixed in ROOT/PLAN.md beforehand):
     the leak control separated, floor +294 MiB against native's +54; native
     minus legacy was 59 MiB against a 32 MiB bound, a miss. Control
     `runtime/soak-rows6`: the same 800 opens with 6 rows leave the floor flat
     (-5.7 MiB), so the rise follows per-row QC string work, not the open: no
     per-open leak in the plugin or engine. Fix: printable-ASCII labels skip
     the per-character rebuild; a row's token is looked up in its own slot
     first.
  3. `runtime/soak3`, same bounds: native floor +21.0 MiB, legacy +1.9 over
     the cycles (inside 32); over the 180 s hold -3.7 against +18.8, fitted
     growth 0.8 against 35.9 MiB; hold CPU drift under 1%. **The leak-control
     arm of this run was killed by the host's memory reaper** and its samples
     were lost, so this rig is incomplete and the reader controls
     (`test_p603soak_unit.py`) have no passing rig: on run 2's complete rig 17
     of 18 act and the 18th reports that rig's real miss. The instrument's
     discrimination rests on run 2.
- **Review.** Three readers on the committed stage (ABI/memory, input
  authority, hostile data), one fresh reader on the fix delta, one on the
  throttle. No memory-safety defect. Fixed: a wrong-row click from a stale private cursor copy; a refused
  label from a hostile name costing the table (and the string mode the second
  reader found still doing so); the page lost when pinning from a peek; Vulkan
  deferred destroys outliving `VK_R_DeInit`; unbudgeted opens; an overflowing
  clip extent; plugin Makefile header deps. A fifth reader took the rebuild
  throttle and the two string reductions, which came after the others: no
  wrong-action or stuck-UI defect, one cosmetic staleness. Everything else is
  in BACKLOG.md.

### Final build and Windows deployment — 2026-10-10

Published: ftequakers `26e74dc91` (Patch 604, tag patch-604) and `f6b92f413`
(Patch 605, tag patch-605); this repository `6af23fc` (build.ps1 summary),
`f892aa5` (Patch 604 record), `a1c8dd7` (Patch 605).

Build of exactly those commits, `build.ps1 -Engine -Full -NoDeploy -Jobs 6`, 132 s,
exit 0. The engine Makefile's `test -d ../.git` fails in a worktree and leaves
the binary unstamped (the first final build was; caught by reading its bytes), so
the rebuild passed `SVN_VERSION=git-7142-patch-605-0-gf6b92f413` and the matching
`SVNREVISION` in the environment. Client and server both contain that string. 77
compiler warning lines, the same count as the pre-review stage build; 55 distinct
sites, none on a line this work changed. Three progs at 0 warnings, byte-identical
to the build every QC-dependent gate above ran on.

| sha256 (first 16) | file |
|---|---|
| `d06480c2661351f5` | fteqw64.exe (installed as ftesurf64.exe / fteqw64.exe) |
| `90cd91c03e4b92b4` | fteqwsv64.exe |
| `086b8a29dd35a835` | fteplug_ui_imgui_x64.dll |
| `37e4cd604786ee54` | fteplug_hl2_x64.dll |
| `dfeb400c75e3aff2` | fteplug_box3d_x64.dll |
| `053a19f6f6948ace` | fteplug_cod_x64.dll |
| `5d07ff5351e9713e` | fteplug_ode_x64.dll |
| `3bd943ca40390396` | csprogs.dat |
| `5e7fd33b3d0beac1` | qwprogs.dat |
| `bb08951eb595687d` | menu.dat |

Rerun on those binaries, all 0 failed: host suites (629 / 2872 / 3750 and the
model regression counts), GL six arms `runtime/final/gl/p603-scores-4t07pp8h`
with 69/69 reader controls, hostile names `runtime/final/names/p603-names-ezjvjvve`,
D3D11 `runtime/final/d3d11/p603-scores-mg1nspav`, Vulkan
`runtime/final/vk/p603-scores-96fulhx8`. NOT rerun on the stamped binaries: the
cost runs and the soak, which measured the same source built without the stamp.

Deployed 2026-10-10T01:35:58Z to `C:/FTESurf` and `C:/FTEQuake` by a guarded copy
(ROOT/tmp/deploy.py, receipt ROOT/artifacts/deploy-receipt.json): every
destination was first checked against the hash recorded when the task began, the
live file kept as `<name>.prev`, the copy verified. 25 files match the build (23
replaced, two line tables already identical): the client, the server (second
install), all five plugins in both, and `ftesurf/{qwprogs,csprogs,menu}.dat` with
their `.lno` in both. build.ps1 itself refreshes only hl2 and ui_imgui in the
primary; box3d, cod and ode were refreshed there too so no plugin beside the new
exe comes from an older build. No game or server was running from either install,
and none was started from one: live behaviour rests on hash identity with the
gated binaries. The owner's `ftesurf.cfg` was not opened.

The progs come from origin/main, so this also puts Patch 600/601's guarded QC
transport (previously published without a progs deploy) on both installs; it is
inert without `ui_native_scores 1`. No other commit has touched product QC since the
previous installed progs were built (2026-10-08T10:55Z). **Not deployed to the Pi**: that restarts the public
lobbies and is the owner's call.

### Not covered

Real online boards (loopback HTTP only); another GPU, driver or machine; D3D9;
Linux; fullscreen; Windows display scaling; a leak inside the CSQC heap (process
private bytes cannot see one); GPU cost; hours-long sessions.

## Earlier checkpoint — 2026-10-09 continuation (superseded by the section above)

Stage remains **uncommitted, unpushed and undeployed**, with legacy default
(`ui_native_scores 0`). The loopback HTTP gate described at the end now passes;
narrow layout, enable/VM lifecycle, dock exclusion, recurring-cost controls and
Vulkan atlas lifetime have a further staging checkpoint below (2026-10-09).
Bounded physical fonts and additive /2 dense pages now have further checkpoints
below. Shared presentation/DPI/face policy, dense cost/endurance/backend/device
acceptance and clean-tree publication/deployment remain. Latest continuation:
`C:/FTESurf-worktrees/imgui-dense-20261009T150334Z/CHECKPOINT.md`.

Owned continuation outputs/evidence: `C:/FTESurf-worktrees/imgui-scores-20261009T044139Z/`.
Historical ad-hoc source worktrees are adopted for the requested continuation,
not moved or removed. New runtime copies are only inside the owned root.


## Authorization and scope

Operator approved starting the opt-in scoreboard migration on 9 Oct 2026 UTC,
with legacy retained as default and fallback. This first real-panel slice replaces
the ranked table at Scores_Draw's explicit draw site. The existing SUI shell,
tabs, leg selector, filters, footer and room list remain in their single bracket;
they are not claimed as all-native. No recorder, evidence, server, preference UI
or default-style change. `ui_native_scores 0` remains default; 1 opts in.

Inspected game `78297a0141241a7ba8a44ed27123840419234ad1`; engine
`368a622ce99d17a44a17f1dee3b85859daf14836`. Isolated worktrees clean at start.
Shared primary trees have peer changes; do not build/ship those. Fetched origins
and checked patch headings/untracked test files: max 602; claim 603 only.

## Design / pre-registered predictions and falsifiers

Reuse NativeUIModel/1 unchanged: one new CSQC owner 205, at most 64 widgets,
positive non-reused identities, bounded plain UTF-8 labels. Six rows per snapshot,
nine typed cells per row, metadata and previous/next controls; no text commands
or paths accepted from native actions. Data and action dispatch remain in QC.
Only changed snapshots advance revision/reset native input; steady frames must
not abandon a held click. Model row tokens are keyed to map/leg/source and actual
row identity, never recycled within an owner generation. Reorder/replacement,
tab/leg/filter/page/data changes invalidate stale action authority.

- Default control: actual legacy table and shell act, no native context/submits.
- Native control: real local/online rows render and real watch/line/page clicks
  act once through the existing hand-offs. The same rows/units/run labels and
  missing-replay/queued/error/empty/loading states remain truthful.
- Stale subjects: acting control first, then held/queued old click while row,
  tab, leg, page or model changes; no wrong row may watch/toggle a line.
- Hold/pin: passive TAB owns no native input or cursor. Mouse2 pins using the
  existing whole input chain; TAB release/Escape close and release once, including
  paired button releases. Room/SUI clicks must not also activate native cells.
- Interruptions: independent mouse/keyboard focus loss, chat, higher overlays,
  console/menu, plugin unload and renderer restart discard native held input.
  No action after close; steady closed state adds no native work.
- Fallback arms: absent optional plugin/builtins, P601 plugin (owner unsupported),
  failed model/open/draw must cover with the usable legacy table, without retry
  spam within the same gesture. A fresh gesture may retry.
- Layout: actual table uses inherited physical clip and converts virtual mouse
  coordinates on both axes. Two virtual scales at the same physical size must
  hit the same actual cells. Inspect screenshots; no font-quality/device/cost
  acceptance is inferred from numeric route probes.

## Verification / delivery gates

Build isolated QC and native outputs with pwsh 7, -NoDeploy, isolated -FteRoot;
read actual compiler output and retain logs. Existing P601 host/input controls
must stay green; new real ImGui controls must act in both index widths. Run the actual production QC bodies (test-only entrypoint/print wrappers are
identified separately from uninstrumented artifacts) in a marked, isolated
dedicated socket rig with explicitly seeded hash, controlled fixtures, screenshots
and reader-mutator tests. Do not
run owner-data harnesses or kill owner processes. No deployment until commit-
pinned artifacts and predecessor guards are inspected; no Pi/server swap is
implied. Patch/engine pin/tag publication only after verification. Human-only
appearance, mouse feel, font/DPI, device and performance acceptance remain open.

## Checkpoint — 9 Oct 2026 UTC, in progress / NOT published or deployed

Starting refs remain game `78297a0141241a7ba8a44ed27123840419234ad1` and engine
`368a622ce99d17a44a17f1dee3b85859daf14836`. Fetched again: game origin/main is
`0ae3ba37bf974a6143fd9a72341f54e485703488` (peer off-ramp tooling/tests/docs;
not merged, no product QC in that delta); engine origin/main unchanged.
Both indexes are empty. Source changes below are uncommitted and wholly this
workstream; this task did not change primary integration trees/installs or terminate
owner processes.
No ENGINE.txt/ENGINE_PATCHES entry, tag, patch pin or Build bump yet. 603 is a
pre-registered number, not a claim that this product patch is complete.

### Owned paths

Game: `src/cl_progs.src`, `src/client/cl_main.qc`, `src/client/cl_players.qc`,
`src/client/cl_scores.qc`, new `src/client/cl_scores_native.qc`,
`src/shared/sh_nativeui.qc`, this checkpoint and `AGENT_NOTES.md` findings;
`tools/p603scores.py`, `tools/test_p603scores.py`, `tools/test_p603scores_unit.py`,
`tools/p603follow.py`, `tools/test_p603follow_unit.py`,
`tools/fixtures/p603follow_runtime.qc`, `tools/fixtures/p603scores_prefix.qc`,
`tools/fixtures/p603scores_runtime.qc`,
`tools/fixtures/p603scores_host.cpp`. The C++ fixture is ignored by this tree's
patterns: it exists but will need an exact-path `git add -f` at publication.

Engine: `engine/client/pr_csqc.c`, `plugins/ui_imgui/backend.h`, `input.inc`,
`model.inc`, `ui_imgui.cpp`, new `scores.inc`. No mover, journal, recorder,
verifier, server QC or engine mesh-adapter semantics changed.

### Implementation present

- Explicit owner 205 table schema on unchanged NativeUIModel/1: five metadata/
  paging widgets plus nine cells for up to six rows (59 maximum). Actual ImGui
  table/clipper; plain labels bypass ##/### identity parsing; literal typed IDs.
- Opt-in `ui_native_scores 0` default, legacy shell/room retained. Same-frame
  legacy table cover for unavailable/open/commit/draw failure; gesture-latched
  failure prevents retries. Suspend/close on focus, engine key destination,
  higher cursor owners, hidden view, preference disable or VM teardown.
- Optional CSQC `ui_native_gamefocus` uses Key_Dest_Has/Has_Higher. Old engines
  without it select legacy. Native input belongs only to pinned, frontmost
  scores; replay is a higher input owner too. Passive table child widgets are
  explicitly disabled, not just the parent window's NoInputs flag.
- QC current-row-key resolution drives existing watch/line hand-offs. Local
  same-path rebuild generation and layout changes reset action authority.
  Unchanged snapshots do not republish/reset held input. Page/row token IDs are
  not reused within the native owner generation; exhaustion fails to fallback.
- Both coordinate axes convert virtual mouse positions to physical; actual room
  rect excludes input and crops a docked native viewport. Transient online
  readiness is checked before opening/uploading a context, avoiding per-frame
  open/close churn. Finite parsed online finish/standing cases now pass below;
  real HTTP, segmented/imported and full online actions are not accepted yet.

### Actual commands / results

All paths relative to `C:\FTESurf-imgui-input` unless stated otherwise.

- `python tools/test_p603scores.py --out rig/p603-checkpoint-host`: 474 real
  scoreboard assertions per 16/32-bit index arm, plus 109 baseline assertions per
  arm, zero failures; native compilation -Werror. Watch/line acting controls
  precede held/unpolled replacement and reset subjects. Bad cell-role subject
  passes generic grammar first, then fails the scoreboard-specific schema.
- `python tools/test_p601model.py --out rig/p603-final-regression`: 463 model-host,
  929 input-host, 172 passive host per invocation; 184 model/700 input/109 passive
  per relevant 16/32-bit executable. All zero failures.
- `pwsh -NoProfile -Command 'Set-Location C:\FTESurf-imgui-input\src;
  ./build.ps1 -Engine -Jobs 8 -NoDeploy -FteRoot
  C:\msys64\home\Lex\fteqw-imgui-input'`: retained
  `rig/p603-build/full-build.log`; actual native build completed. Only the known
  pr_csqc address-comparison / make peer-dependency warnings appeared, present in
  P601's build log. No source-warning repair or build-script edit was made.
- Latest QC-only same command without `-Engine`: retained
  `rig/p603-build/qc-checkpoint2.log`, outputs
  `rig/build-nodeploy-f4eb5f77711d494fb47e491653b33941`. Server/client/menu each
  **Done. 0 warnings**. Script exit 1 is the existing final-summary Get-Item at
  build.ps1:562 looking for intentionally absent integration qwprogs.dat, AFTER
  all three successful isolated outputs. Do not misreport this as exit-zero build.
- Runtime command:
  `python tools/p603scores.py --qc-artifacts
  rig/build-nodeploy-46ec315b5261467b8bbe68145d03ae28 --plugin
  rig/p603-scores-759oi6l4/native-build/fteplug_ui_imgui_x64.dll --old-plugin
  rig/p601-model-sicdm_9i/scale1/fteplug_ui_imgui_x64.dll --arms legacy native1
  native2 absent oldplugin`.
  Final `rig/p603-scores-owz8d6rs`: five arms, 17 screenshots, **zero local-route
  failures**. Real dedicated socket on an available designated 27520..27620 port,
  CWD C:\FTESurf, owned server/client Popen handles only. Synthetic eight-record
  dataset; instrumented actual production bodies compile zero warnings and seed
  the exact csprogs hash. No injected native action vectors or fake Watch_Open.
- Native 1920x1080 physical at 1920x1080 and 960x540 virtual: passive no cursor/
  watch; pin acts; line builds 20 points then turns off; page 0->6->0; actual Row0
  replay opens 20 samples, closes native table; same-path rescan advances revision
  and cancels held old click; independent keyboard-focus loss and console release
  native, regain restores it; TAB release clears owner/button state. Both final
  closed plugin status snapshots are identical with live=0. Final native pinned,
  scale-2 next-page and P601-plugin fallback screenshots inspected; all 17 files
  retained.
- Legacy/default, absent and P601-plugin arms render legacy and actual Row0 mouse
  watch succeeds. Legacy's responsive column budget hides its line checkbox in
  this layout, so `scores line 0` is the explicit legacy line-hand-off control;
  it builds/removes the same 20-point line. Do not claim a hidden legacy checkbox
  was clicked. Native line control really clicks its rendered checkbox.
- `python tools/test_p603scores_unit.py rig/p603-scores-owz8d6rs`: 25 reader controls
  passed on the final designated-port matrix. Reject quiet/missing/duplicate/inert controls,
  wrong row identity, unchanged rescan, stale activation, stuck release, extra
  closed work, incomplete planned arms and missing screenshots.
- Python compilation and diff whitespace checks pass. LSP diagnostics inspected:
  engine has existing unused-global/tidy findings; plugin has existing unused-
  include hints. QC has no language server; the compiler/runtime are the proof.
  C++ fixture clangd lacks its host include flags; real -Werror builds pass.

### Retained failed controls / constraints

`p603-scores-759oi6l4` proved first real rendering and watch, but its stale arms
are NOT evidence: invalid `replay close` left replay owning input. Correct command
is `replay off`. `p603-scores-l_6d50fz` rejected nonexistent legacy line hitboxes;
`p603-scores-kbpv2fjy` rejected a quiet legacy watch control after line changes.
The corrected fixture refreshes its known physical position immediately before
both button edges; `p603-scores-0felo808` and later matrices act. Early scratch
rigs used ephemeral dedicated ports; final driver restricts designated ports.
No failed arm was waived or turned into a pass by deleting a requirement.

Fteqcc old-style absolute input paths fail; use owned same-src-directory manifests,
unchanged relative inputs and a rig output line, then remove only owned manifests.
A typo `_action_elements[i].size_y` crashes git-6681 qcc with 0xc0000005 and no
output. Correct struct-vector syntax is `.size.y`: a single-factor bad-member
probe crashes while a float-index/dotted-member control compiles. The compiler's
silent crash is not evidence against untouched QC. Probe logs in
`p603-scores-nepx9do4`; do not ship diagnostic mutations.

### Resume gate — finish following / own standing (pre-registered)

Next bounded gate: share the existing finished-leg/style predicates with legacy,
seek the native six-row page once, and carry explicit selected-row/standing
metadata on NativeUIModel/1 (five metadata widgets + 54 cells = 59 maximum).
No new action, ABI, recorder or server contract. The fifth checkbox is display
metadata only: its row token marks a highlighted row; its plain label is a
non-clickable standing footer. Never manufacture a replay/line target for a
standing outside the fetched rows.

Acting local Row0 watch/line/page controls remain mandatory. Then local Row7
finish must reveal page 6 once and highlight it; wrong-leg and closed views must
retain seek, and a held old click followed by finish/page change must not watch.
Online bodies go through the actual Online_Parse; a clearly identified test-only
own-row seam sets ob_mine AFTER parsing (not a claim about Online_FindMine or
HTTP/download acceptance). Own Row7 must reveal page 6 only after both answer
and current-generation reply; pending/stale replies retain seek. Outside fetched
rows, rank 99 / standing 0:03.150 / fixture name must display without an action.
Wrong leg/style and an empty board must not invent that standing. Two physical/
virtual scales and legacy comparison, strict reader mutations and screenshots
are required. Full online HTTP/download and lifecycle gates remain separate.

### Resume results — 9 Oct 2026 UTC 03:24, still uncommitted / undeployed

Starting inspected refs unchanged; both indexes remain empty. Added the finite
finish gate files listed above, shared `Scores_FinishedLeg`, finished-style,
outside-standing and online-seek predicates with legacy. Native follows the
matching local finish or online own row once; wrong leg/style and pending/stale
reply retain seek. Seek is consumed only AFTER successful native drawing, so a
failed native publish/draw leaves the legacy fallback its reveal. Explicit
metadata highlights a real visible row token and displays an outside standing
without manufacturing any clickable row. The owner-specific validator rejects
an orphan highlight; unchanged NativeUIModel/1 and six-row bound remain.

The new acting online arm exposed an existing WIP readiness bug:
`ui_mc_state != 2` gated native boards on the MAP-VOTE CLOCK. This is not a
leaderboard readiness variable (`cl_hud.qc` MapClock_Read/HUD_MapClockText). Removed that
guard; valid leg + `Online_Shows` still precede allocation. Wrong-body leg/style
cover with legacy without native rows/resources; empty current board renders
five metadata widgets and no synthetic standing.

- `python tools/test_p603scores.py --out rig/p603-follow-host`: **554 scoreboard
  assertions per 16/32-bit index arm**, plus 109 passive baseline assertions each,
  zero failures, actual native host compilation with warnings fatal.
- Final runtime:
  `python tools/p603scores.py --qc-artifacts
  rig/build-nodeploy-f3661d217a254ddab559c9fa89e57a85 --plugin
  rig/p603-scores-_5tsw0l7/native-build/fteplug_ui_imgui_x64.dll --old-plugin
  rig/p601-model-sicdm_9i/scale1/fteplug_ui_imgui_x64.dll --arms legacy native1
  native2 absent oldplugin --follow`.
  `rig/p603-scores-7sbn9_kl`: **five exit-zero arms, zero local/follow faults**.
  Actual-source instrumented csprogs SHA256
  `5146fc6fbe69fb74e6939b7ebbaf67dbd60c68331df7f7cb1ee51ebaa76db657`;
  plugin `8c81a4d23b230ad5bf1ec43af1c387420d15d2b16c1cedc09e17df86ff63d6dd`;
  engine `07395139b68789a291f8ce7b36a51b7969641611fe2e8a4fb7303615a1e5e28f`.
  Both physical/virtual scale arms act on watch/line/page before finish subjects.
  Local Row7 reveals page 6/highlight; Previous stays at page 0 afterward;
  finish while holding Row0 cancels the old click; closed seek survives and
  reveals on reopening. Parsed online own Row7 reveals after answer/current
  generation only. Outside rank 99, 0:03.150, P603Fixture is read-only text;
  wrong leg/style/body/empty do not show it. Final closed statuses are identical.
  Legacy comparison and native highlight/standing/guard screenshots inspected.
- `python tools/test_p603follow_unit.py rig/p603-scores-7sbn9_kl`: **43 tests pass**
  (25 inherited local reader controls + 18 finish-gate controls/mutations).
  `test_p603scores_unit.py` rerun independently: 25 pass. Inert reveal/highlight,
  repeated follow, premature closed/pending/stale seek, synthetic standing row,
  wrong standing units, wrong-body native route, incomplete/duplicate evidence
  and missing screenshots cannot pass.
- `python tools/test_p601model.py --out rig/p603-follow-regression`: passive 172,
  input bridge 929, model bridge 463, real 16/32-bit input 700 and model 184
  (+109 passive each), all zero failures.
- Final uninstrumented QC build: same -Jobs 8 -NoDeploy -FteRoot command, log
  `rig/p603-build/follow-qc-final2.log`, outputs
  `rig/build-nodeploy-490dda00e1854b5785023dda6e8b58ed`. All three compilers
  **Done. 0 warnings**. Existing build.ps1:562 final-summary missing deployed
  qwprogs.dat still makes the WRAPPER exit 1; not repaired or hidden.
- `python tools/test_reccheck.py`: 306 checks, zero failures. Read-only corpus
  comparison against the HEAD checker: 269 recordings, 91 paired sidecars,
  **170 faulted reports in both baseline and current**, no increase. No player
  data touched or raw identity/file-path findings emitted into this checkpoint.
- Failed controls retained: `p603-scores-1rlel6nk` fixture compile rejected a
  ninth sprintf parameter and nonexistent TF_STITCH; split the probe and use
  TF_SEGMENT. `_5tsw0l7` exposed the map-clock gate (17 online faults), not a pass.
  `ynf5w0qf` missed the first scale-2 line click (second then turned it ON), so its
  two local faults remain a failure. Target moved from the checkbox's left-edge
  margin (+697) to its interior (+705), not a relaxed grader; `qbpycu_7` then the
  two full matrices `k2xa9c5u` and final `7sbn9_kl` all pass. This does not prove
  the external OS/device-input cause of that first miss.

No commit, push, tag, patch pin, Build bump or deployment. Finite online bodies
are parsed by production `Online_Parse`, but `ob_mine` is deliberately set after
parsing by the disposable wrapper. Do NOT infer Online_FindMine, real HTTP,
download, public leaderboard or live finish certification acceptance from it.

### Remaining gates / next action

1. Local and finite finish/standing gates above are done. Keep the final five-arm
   matrix and reader mutations as acting controls when extending the next gates.
2. Add actual online/segmented/imported HTTP/parser/identity and download/line
   controls plus loading/error/missing-replay/rate/flags/why/verified cases. Audit
   readiness/root/terms gates against Scores_DrawOnlineRows; no native allocations
   while loading. Test byte-identical online refresh generation and row reorder/
   replacement authority explicitly before claiming online migration complete.
3. Extend whole-chain lifecycle matrix: mouse-only focus, Escape release, chat,
   replay and other higher overlays, menu, room click isolation, source/leg/filter/
   page held changes, plugin unload/reload, renderer restart and deliberate draw/
   model failure. Acting controls first, no gameplay binding/device claims from
   synthetic CSQC_InputEvent calls. Check uninstrumented artifact behavior too.
4. Clean up legacy fallback-block indentation; final build/regression/review,
   fetch and allocate max+1 (603 is now occupied). Integrate only inspected peer published
   changes needed for publication; no peer source deployment. Then one verified
   engine patch entry + ENGINE.txt pin/bump, clean commit-pinned artifacts, tags/
   exact-SHA pushes. No premature qcbuild/Build decision.
5. Any deployment requires the full Pi-operations/dual-install ship-set and
   predecessor/owner-process guards first. Nothing has been deployed in this task.

Native table currently uses default ImGui font size and bounded six-row pages;
font/DPI/appearance/device feel, all-platform/non-GL behavior and cost acceptance
are still open. This checkpoint proves the local-table route, not roadmap C done.

## Actual HTTP continuation — 2026-10-09

Source bases remain QC `78297a0141241a7ba8a44ed27123840419234ad1`, engine
`368a622ce99d17a44a17f1dee3b85859daf14836`, plus adopted scoreboard staging.
No canonical checkout changes, owner settings/data or deployment. Actual product
change here: `Scores_NativeDraw` now commits a fresh action revision on an online
`ob_epoch` change, even when visible bytes/row keys match. The page stays intact.

New `tools/p603http.py`/fixtures drive loopback HTTP through the actual engine
URI callback, parser, FindMine, replay cache/write, watch and line builders.
A server spawn wrapper supplies a synthetic *phash via the production FS_GuidId
input boundary; it does NOT assign ob_mine or substitute parser/callback logic.
Demo POST answers are synthetic queued/failed states, not real downloader work.

Commands (from `C:/FTESurf-imgui-input`; use the owned root for all new outputs):

```text
python tools/p598build.py --fte C:/msys64/home/Lex/fteqw-imgui-input --cc C:/msys64/ucrt64/bin/g++.exe --out C:/FTESurf-worktrees/imgui-scores-20261009T044139Z/artifacts/native-build
python tools/p603scores.py --qc-artifacts rig/build-nodeploy-490dda00e1854b5785023dda6e8b58ed --plugin C:/FTESurf-worktrees/imgui-scores-20261009T044139Z/artifacts/native-build/fteplug_ui_imgui_x64.dll --arms native1 native2 legacy absent --http --out C:/FTESurf-worktrees/imgui-scores-20261009T044139Z/runtime
python tools/test_p603http_unit.py <HTTP-rig> C:/FTESurf-worktrees/imgui-scores-20261009T044139Z/artifacts
python tools/test_p603scores.py --fte C:/msys64/home/Lex/fteqw-imgui-input --cxx C:/msys64/ucrt64/bin/g++.exe --out C:/FTESurf-worktrees/imgui-scores-20261009T044139Z/artifacts/host-tests
```

- `p603-scores-hpjocqc5`: the pre-fix native acting control downloaded/watch-opened
  the correct 20-sample file and drew its comparison line. An identical actual
  HTTP refresh advanced ob_epoch but retained native authority; releasing a held
  click opened that replay. Corrected initial grader: exactly two failures for
  this refresh (retained revision + stale watch). Do not call this rig a pass.
- `p603-scores-xcgbocm8`: failed combined finite/HTTP fixture run (28 faults).
  The preceding finite empty/scroll state prevented the initial HTTP ask. Suites
  now run separately (`--follow` and `--http` are mutually exclusive); the HTTP
  start explicitly asks with production board_fetch. No relaxed assertions.
- Final `p603-scores-b1zw1xao`: **four exit-zero arms, zero local/HTTP faults**,
  fresh plugin -Wall/-Wextra/-Werror build. Actual-source client and synthetic
  identity server compilers exit zero, **Done. 0 warnings**. Controls: genuine
  FindMine row 7; both native scales page to 6 and retain it over refresh; cold
  replay transfer followed by line/watch/cache reuse; missing replay explanation;
  held identical/reordered replies reject old watch; loading/wrong-body/429 do
  not allocate native contexts; empty tables; imported momentum/ksf words and
  POST queued/failed line states; segmented flag; mixed tickrates/ms delta and
  verified labels. Closed counters/owner release remain covered by local gate.
- `p603-scores-wrir5iqe`: **four exit-zero arms, zero local/finite-follow faults**
  after the epoch fix. Historical oldplugin acceptance remains the prior five-arm
  checkpoint; oldplugin was not rerun for this HTTP continuation.
- Reader mutations: HTTP **21 tests pass**, local **25**, finite-follow **43**
  (includes inherited local tests). Host tests: each index width **554 scoreboard
  +109 passive checks, zero failed**. LSP has no recorded diagnostics; QC is
  established by compiler/runtime, not LSP. Representative native/legacy/error/
  refresh screenshots inspected. Source/diff/compiled artifact hashes and raw
  synthetic rigs are retained in the owned root's artifacts.
- Failed setup controls retained: prefix before generated server definitions
  triggered Q208/sysdefs rejection; prefix now precedes sv_player only. An
  attempted mingw64 compiler path did not exist; actual tool is ucrt64 g++.

The prior next-action HTTP step is now covered **for this loopback scope**, not
public service/full downloader/live certification acceptance. Next: replay-column
clipping in BACKLOG; root/terms and remaining whole-chain lifecycle cases,
renderer test modes 1..3, cost/uninstrumented acceptance, then publication number
reallocation, clean commit-pinned build and guarded dual deployment. The ignored
`tools/fixtures/p603scores_host.cpp` is load-bearing existing staging source
(`*.cpp` ignore rule): retain and explicitly stage it when publishing, not an
untracked-file-only inventory. No commit/push/tag/pin/Build bump/deployment yet.

## Continuation checkpoint — 2026-10-09, clipping/lifecycle/fallback gates

**Still opt-in, unpublished and undeployed.** The completed gates below replace
those specific earlier next actions, not the remaining acceptance/publish hold.
No product patch number claimed, no ENGINE/Build pin changed. Source branches
remain game `imgui-input-600` at `78297a0141241a7ba8a44ed27123840419234ad1`
and engine `imgui-input-600` at `368a622ce99d17a44a17f1dee3b85859daf14836`.

New owned root: `C:\FTESurf-worktrees\imgui-scores-20261009T083108Z`.
The earlier task root is read-only evidence, not a cleanup target. New test source:
`p603life.py`, `test_p603life_unit.py`, and its prefix/postfix/runtime QC fixtures.
Existing scoreboard/HTTP fixtures and readers were extended, not replaced with
fake native actions. `p603scores.py --life` may now follow `--http`; finite
`--follow` and `--http` remain mutually exclusive.

### Changes and acting controls

- Engine `ScoresGallery` gives replay a 140-physical-pixel minimum, growing to
  `CalcTextSize` of every copied replay label. Long verification suffixes no
  longer disappear. Actual table-column WorkMinX/WorkMaxX checks cover verified
  watch/Get-demo/queued/retry and a longer bounded claim. Restored-layout line
  and existing watch/page controls still ACT. A minimal predecessor overlay
  restoring ONLY the 68-pixel replay budget fails all five text-fit subjects;
  corrected 16/32-bit hosts each pass **783 scoreboard +109 baseline checks**.
  Inspected native1 Get-demo and native2 retry screenshots show full words.
- Legacy fallback block indentation in `cl_scores.qc` is corrected, with no
  legacy semantic change. `ui_native_scores` still defaults to 0.
- Native lifecycle subjects cover mouse-only focus loss/regain, Escape, chat,
  higher HUD-editor ownership, builtin menu, held filter/source changes, room
  exclusion, a real SUI filter click, plugin unload/reload and vid_restart.
  Final owner/button pairs are clear. Renderer restart correctly selects legacy
  until a fresh gesture; plugin reload and fresh gestures restore native rows.
  HUD editor refuses a pinned board and steps aside if scores repins: the valid
  higher-overlay subject closes the pin, opens the editor, holds readonly scores,
  releases the old button, then closes editor and repins. No false direct-overlay
  claim. Legacy/no-plugin are usable route controls, not subjects for a new
  revision-bound SUI input contract.
- Test-only draw/commit response seams run the production native failure paths:
  exactly one failure response per gesture, immediate usable legacy cover, no
  retry while the gesture remains held, an actual Row0 fallback watch, and fresh
  native recovery. No production failure switch was added.
- HTTP v2 adds denied terms, empty lobby_dir, terms/root recovery, cached-board
  404/500 failures, and verified Get-demo/queued/retry labels. Stub evidence
  proves denied terms sends NO /noterms request, genuine 404/500 delivery and
  exactly one real verified-demo POST in each queued/error route. Cached rows
  remain usable on same-board failed refresh; unconfigured/denied states retain
  legacy explanations without native allocation. Synthetic identity only.
- New `oldengine` arm uses an explicitly supplied older executable with the
  CURRENT plugin hash recorded per arm. Its actual builtin probe says
  gamefocus=0, model=0: this proves old-engine fallback, not an isolated
  missing-focus-only model-capable engine. P601 old-plugin fallback also reran.

### Exact successful gates

Paths in commands are relative to `C:\FTESurf-imgui-input` unless absolute.
Artifact/evidence names below are beneath the new owned root.

- `python tools/p598build.py --fte C:/msys64/home/Lex/fteqw-imgui-input --out
  C:/FTESurf-worktrees/imgui-scores-20261009T083108Z/artifacts/native-build`:
  fresh plugin compiled/linked with -Wall/-Wextra/-Werror, no warnings.
- `python tools/test_p603scores.py --out
  C:/FTESurf-worktrees/imgui-scores-20261009T083108Z/artifacts/clip-host`:
  both index widths, 783+109 checks per width, zero failures. The predecessor
  overlay/log is retained under `artifacts/clip-predecessor` (five expected
  failures, exit 1; NOT a pass).
- `python tools/p603scores.py --qc-artifacts
  rig/build-nodeploy-490dda00e1854b5785023dda6e8b58ed --plugin
  C:/FTESurf-worktrees/imgui-scores-20261009T083108Z/artifacts/native-build/fteplug_ui_imgui_x64.dll
  --arms native1 native2 legacy absent --http --life --out
  C:/FTESurf-worktrees/imgui-scores-20261009T083108Z/runtime`:
  **`p603-scores-lue7obk7`, four exit-zero arms, zero local/HTTP/lifecycle faults**.
  Both virtual scales, actual production parser, actions, frontend/input/draw
  bodies; exact instrumented csprogs seeded to real dedicated sockets. Synthetic
  driver owns absolute motion (see limitations below).
- Same base command, without --http/--life, adding `--old-plugin
  rig/p601-model-sicdm_9i/scale1/fteplug_ui_imgui_x64.dll --old-engine
  C:/FTESurf/ftesurf64.exe --arms oldplugin oldengine`:
  **`p603-scores-saxmditv`, two exit-zero arms, zero local-route faults**.
- Fresh `pwsh -NoProfile -Command 'Set-Location C:/FTESurf-imgui-input/src;
  ./build.ps1 -Jobs 8 -NoDeploy -FteRoot C:/msys64/home/Lex/fteqw-imgui-input'`:
  all three actual compilers **Done. 0 warnings**; outputs
  `rig/build-nodeploy-ab9e2e5d70764d83a4c8c5c62126042f`, retained. Script still
  exits 1 in its existing final summary when integration qwprogs.dat is absent;
  this is NOT an exit-zero script claim. `artifacts/qc-build.log` retains output.
- Base runtime command with that fresh QC output and `--arms native1 native2
  legacy --follow`: **`p603-scores-53dfaur5`, three exit-zero arms, zero
  local/finite-follow faults**, on the final instrumentation/production source.
- Final readers: **25 local, 29 HTTP, 26 lifecycle, 43 finite-follow tests pass**.
  The lifecycle reader includes unchanged acting evidence and mutations for
  duplicate/missing fields, inert controls, stale watch, retained ownership,
  button pairs, retry spam, failed legacy cover and missing screenshots.
- `python tools/test_p601model.py --out .../artifacts/bridge-regression`:
  172 passive /929 input /463 model bridge checks and both pinned native input/
  model index widths pass. `python tools/test_reccheck.py`: **306 checks, 0 failed**.
  Python compilation, diff whitespace and LSP diagnostics checked. Host fixture
  clangd still lacks the test-only include flags; the real -Werror compiler is
  the C++ test proof. QC has no language server.
- Read-only canonical corpus: **370 .rec/.view files**, staging HEAD-reader
  control and unchanged subject both report **173 faults /610 notes**, all
  findings equal; byte hashes and file inventory unchanged. No increase, but
  emphatically NOT a clean-corpus claim. This older staging reader and current
  canonical corpus were not repaired/migrated. Aggregate-only summaries retained
  in artifacts; raw player findings were not printed or exported.

### Failed controls and boundaries

All new raw rigs, including failures, are inventoried/archived before retiring
ONLY their disposable synthetic runtime trees. Directly browsable logs/screens/
reports survive in `artifacts/evidence/<rig>`; source/builds and retirement proof
remain in artifacts. Never rerun an archived evidence folder as a runtime cwd.
Retirement verified 2026-10-09T09:55:42Z: **3,658 files /1,062,198,479 bytes**,
all archive members SHA256-checked, zero owned game-process references, runtime
root absent. Archive SHA256:
`88be17e28d14a9af414bb2b54bbf73bcda38bd8f2c2a8386aadce5c38fc8e369`.

- `nkvxmk70` and `sgvj3hde`: editor subjects did not act because production's
  pinned-board refusal/repin arbitration was ignored by the fixture. The latter
  also applied native cancellation expectations to legacy SUI; that is not the
  product contract. Corrected supported overlay/native-only held subjects passed
  in `hp8j5p27`, then in the final combined matrix.
- `v2lrlbsi`: one HTTP native1 probe caught OBS_READY before the real draw; the
  probe was moved after production CSQC_UpdateView with a frame barrier.
  `8lx91cq5`: pending empty-string handles were tested by truthiness, producing
  fixture errors; strcmp fixed this test-only defect. Neither rig is a pass.
- `xl60dw75`: missing-replay click explanation did not act once. Combined
  `a40p9ijy` also missed a base watch despite both edges being consumed and
  exposed inherited HTTP state contaminating the later lifecycle source subject.
  Win32 INS_Accumulate continuously feeds real absolute cursor motion while
  mouseinactive, racing injected motion. The TEST-ONLY CSQC input wrapper now
  excludes hardware IE_MOUSEABS and sends synthetic motion to the unchanged
  production input body; other input routes remain real. Lifecycle reset also
  explicitly clears root/consent. Final matrix passed without relaxed activation
  assertions or retrying a missed click inside a control. This is NOT
  real-device/manual focus acceptance.
- Combining suites exposed a reader mutant: later correct fallback Row0 watches
  masked a wrong base identity searched across the whole log. Base watch identity
  is now bound to its own action/probe interval; the mutant rejects correctly.
  Lifecycle unit copies also retain HTTP evidence when testing a combined report.
- Initial oldengine grading had a test-only variable/metadata bug; fixed reader
  and fresh per-arm engine/plugin provenance passed in `saxmditv`. Earlier
  `gzfeljwn` is not the final accepted compatibility report.

### Remaining next action / publication hold

Do not reinterpret these synthetic gates as roadmap C/full-scoreboard acceptance.
Still needed: human actual-device/font/DPI/appearance acceptance, denser bounded
native pages, larger-store/endurance and wider-device cost budgets, any remaining
public-service downloader acceptance, then independent clean-tree source review
and commit-pinned build/publication with a freshly reallocated product patch number.
Historical p603 harness names reserve NO number. Then guarded, hash-verified dual
Windows/fleet deployment under the existing operations rules. The synthetic
controls below do NOT replace those gates. No commit, push, tag, ENGINE pin,
qcbuild/Build bump or deployment was performed.

## Fundamental continuation — 2026-10-09 (imgui-core)

Owned evidence: `C:/FTESurf-worktrees/imgui-core-20261009T100410Z/` (`OWNER.md`).
Source refs remain game `78297a0141241a7ba8a44ed27123840419234ad1` and engine
`368a622ce99d17a44a17f1dee3b85859daf14836`, plus the adopted unpublished staging.
Canonical peer edits were not touched. No product patch number was reserved.

### Changes and discriminating controls

- **Narrow tables:** `plugins/ui_imgui/scores.inc` now wraps heading/standing text,
  reserves the real wrapped footer height, and stacks pagination when two buttons
  cannot fit. A too-short table requests covering legacy instead of accidentally
  passing a non-positive BeginTable height (which means fill available space).
  Actual pinned-ImGui mouse-only scrollbar, line activation and Previous/Next
  controls at 150/190/260/400 physical px pass; wide layout recovers. Predecessor
  `artifacts/narrow-predecessor/host16/host.log` has 12 expected failures, not a pass.
  Subject `artifacts/narrow-final-host/` passes 1633 scoreboard +109 inherited
  checks per 16-/32-bit width, no compiler/linker warnings (-Werror).
- **Whole-chain lifecycle:** production preference disable during a held press
  returns usable legacy, has live=0 and identical counters over a timed interval;
  enable recovers. Real disconnect unloads CSQC, then a dedicated reconnect seeds
  a fresh VM and gesture, without replay on the old release. A hud_scale=5 subject
  actually docks the room inside the board: native viewport ends exactly one
  virtual unit before the room, room hover is excluded, and no watch acts.
  These are synthetic motion/button controls through the actual source bodies,
  not physical-device acceptance.
- **Pure-label recurring cost:** `cl_scores_native.qc` caches only the pure
  decolor/control-character/UTF-8 truncation transform by raw cell label and UTF-8
  mode. It still builds/checks live row metadata and action/query identities every
  frame. The extra buffer is released on close/reset/failure. Live row-name probes
  include color/control characters and literal ##/###: changed display text
  advances revision; a color-only equivalent remains revision-identical. Neither
  replay/download state nor actions are cached by this optimization.
- **Vulkan atlas lifetime:** acting native watch freed the atlas after recording
  this frame's draw, before submission; `VK_DestroyTexture` destroyed its image,
  view and sampler immediately. Native predecessor `p603-scores-ucc9etaq` loses
  the device (`ERROR: vkQueueSubmit: VK_ERROR_DEVICE_LOST`); legacy watches the same
  replay successfully. `engine/vk/vk_init.c` now uses the existing copied-handle
  `VK_AtFrameEnd(VK_DestroyVkTexture_Delayed,...)`, already used for upload
  replacement. CPU wrapper/token retirement stays immediate, native handles wait
  for the fence. Shutdown drains those callbacks before device destruction.
  Exact prediction/control is `artifacts/vulkan-plan.md`.

### Renderer and runtime evidence

The old handoff did not define an actual named switch for "renderer test modes
1..3". This continuation tests real `vid_renderer` selections instead. The harness
now records the request and requires its positive initialization witness; falling
back to another backend is NOT parity. Device-loss errors are explicitly rejected.

- `p603-scores-_7_em1io`: GL native1/native2/legacy/absent, combined local+HTTP+life,
  all four exit zero, zero faults. This is the pure-label-cache subject with the
  prior engine executable; both virtual scales, real parser and HTTP states.
- `p603-scores-48dv1m1z`: Direct3D11 native1/legacy, both exit zero, zero faults.
  Raw D3D11 screenshots are vertically inverted for the entire frame (including
  legacy/HUD), not just native ink; normalize a copy for inspection, keep originals.
- `p603-scores-hnsjlfov`: Direct3D9 device creation fails and falls back to GL.
  The new backend gate rejects it. No D3D9 acceptance claim.
- `p603-scores-2h5bgj1w`: rebuilt Vulkan native arm passes watch/line/page/input and
  all lifecycle routes, including renderer restart, plugin reload, enable/disable,
  dock exclusion, failure seams, metadata cache and real VM teardown/reconnect.
  Its legacy process has a separate startup access violation 0xC0000005 before
  fixture commands run; the whole original report remains FAILED.
- `p603-scores-xe5botp8`: isolated Vulkan legacy retry, same engine/plugin/QC hashes,
  local+life, exit zero and zero faults. `artifacts/vulkan-lifetime-combined-v2/`
  explicitly selects the successful native and legacy arms with source-report/log
  hashes; original failures are unchanged. Complete combined reader: zero faults,
  lifecycle acting/mutation reader: 39 tests pass. Different process/start times
  are a limit, not hidden simultaneous-control proof. Startup crash remains open.
- `p603-scores-3o9ntf6v`: rebuilt engine GL native1/native2/legacy, zero faults.
  `p603-scores-_9ey60o8`: fresh oldplugin/oldengine covering controls, zero faults;
  canonical old-engine SHA `e6fbc95167f6b7b6f8b1dd0a86146db08006c84fa42f8bf9a0436285cc345a28`.
- Main source/control readers: 27 local +29 HTTP +39 lifecycle tests pass. Cost
  reader: 23 acting/mutation tests pass (CPU/sample/count/config/identity/image/
  memory/route/backend/quiet/closed-work falsifiers). See commands below.

### Uninstrumented recurring-cost result (not GPU/device acceptance)

`tools/p603perf.py` uses unmodified production csprogs, a real dedicated socket,
identical offline rows/map/view/config and native/loaded-legacy/absent arms. No QC
seam/probe or injected native action is present. Engine r_speeds_dump gives
100-frame CPU-bucket snapshots, spaced >100 frames at explicit cl_maxfps=100;
profiling is off. Screenshots must contain the requested table route/real glyphs,
not merely exist. Private bytes/working set come from the owned process handle.
Draw counters/atlases must act while open and be exactly stationary/fully closed
outside it. Repeats bracket open with closed and closed-after intervals.

Use **six total rows** for equivalent visible-row work. The 64-widget model holds
six native rows; the earlier 24-row store showed six native vs ~20 legacy rows and
is NOT a speed comparison. Long interrupted/quiet runs were rejected, not rescued
by borrowing a later sample. Explicit earlier selected-arm combination is
`artifacts/cost-six-combined/` (source hashes and limitations retained).

Final whole-run subject **`p603-perf-2kdlpz_b`**: three exit-zero arms, 18 samples per
arm (six per phase), zero reader faults. Median QC UpdateView microseconds/frame:

| arm | closed | open (same six rows) | closed after |
|---|---:|---:|---:|
| native | 390.04 | 916.79 | 397.90 |
| loaded legacy | 408.94 | 855.12 | 400.70 |
| absent | 400.49 | 818.60 | 388.13 |

Native open range 888.81–967.72 us; loaded legacy 785.91–868.63 us. Earlier pre-cache
native median 1068.70 us vs 803.92 us legacy (12 samples/phase, different run/time).
Observed native median reduction ~14%; not a controlled causal/portable budget
claim. Final native–loaded-legacy median gap ~62 us/frame. Logical native resources
are fully closed and no native counter work accrues in closed intervals. Whole-
process private memory is NOT an atlas leak measurement: final native closed-after
293.97–298.32 MiB, with larger screenshot/allocator transients in legacy/absent too.
No zero-memory/long-endurance acceptance is implied. Total refresh includes
r_speeds' own overlay, pacing/present buckets; do not call it pure UI/GPU cost.

### Exact reproduction / build limits

From `C:/FTESurf-imgui-input`, with the same owned root abbreviated as ROOT:

- `python tools/test_p603scores.py --out ROOT/artifacts/narrow-final-host`
- `python tools/p598build.py --fte C:/msys64/home/Lex/fteqw-imgui-input --out ROOT/artifacts/native-build`
- `python tools/p603scores.py --qc-artifacts rig/build-nodeploy-5d660416dd5a48b1811aa35127a11551 --plugin ROOT/artifacts/native-build/fteplug_ui_imgui_x64.dll --engine ROOT/artifacts/engine-vulkan-subject.exe --renderer vk --arms native1 legacy --life --out ROOT/runtime`
- GL uses the default renderer; `--http --life --arms native1 native2 legacy absent`
  enables the complete combined suite. Direct3D11 uses `--renderer d3d11`.
- `python tools/p603perf.py --qc-artifacts rig/build-nodeploy-5d660416dd5a48b1811aa35127a11551 --plugin ROOT/artifacts/native-build/fteplug_ui_imgui_x64.dll --engine ROOT/artifacts/engine-vulkan-subject.exe --rows 6 --repeats 2 --samples 3 --out ROOT/runtime`
- `python tools/test_p603scores_unit.py ROOT/runtime/p603-scores-_7_em1io`
- `python tools/test_p603http_unit.py ROOT/runtime/p603-scores-_7_em1io ROOT/tmp/http-mutants`
- `python tools/test_p603life_unit.py ROOT/artifacts/vulkan-lifetime-combined-v2 ROOT/tmp/life-mutants`
- `python tools/test_p603perf_unit.py ROOT/runtime/p603-perf-2kdlpz_b ROOT/tmp/perf-mutants`

QC build: all three programs 0 warnings. Native build uses the documented
`-Engine -NoDeploy -Jobs 8 -FteRoot 'C:\msys64\home\Lex\fteqw-imgui-input'` procedure;
`artifacts/build-vulkan.ps1` avoids Bash's -Command path conversion and restores
normal MSYS conversion for GCC. Attempts 1/2 failed on path conversion and are
retained, not passes. Attempt 3 compiles/links client/server/plugins successfully,
then the pre-existing NoDeploy summary reads absent installed qwprogs.dat and
errors. Compiler outputs, not that wrapper exit, are the build evidence:
`vulkan-engine-build3.log`. Existing untouched pr_csqc.c -Waddress and make grouped-
.d recipe warnings remain; no new Vulkan warning. clangd shows four existing
out-of-scope tidy warnings, none at the changed lifetime call. No related code was
"repaired" merely to silence those warnings.

Preserved executable SHAs:
- predecessor: `07395139b68789a291f8ce7b36a51b7969641611fe2e8a4fb7303615a1e5e28f`
- fence subject: `f4e84cd88975895728005a17c241461952a11178c4fce298cf7320c1869b66b5`
- uninstrumented subject csprogs: `5b03759f7b63ad05fe277b89b4bbd43991b061c9a80c833a1ebe04cfd9ede7e3`

All test child handles are stopped/waited. Runtime archives/retirement are listed
in ROOT/OWNER.md and the per-file manifest, with source/diffs/reports/logs/images
retained. Historical roots and canonical installs/data/settings were not cleaned.
Retirement: 1991 manifest-selected disposable runtime files, 922.38 MiB input,
SHA/CRC-verified in `artifacts/runtime-disposable.zip` (312.31 MiB), then rehashed
and unlinked individually. Reports/configs/logs/images/rec/view/source remain;
main GL, combined Vulkan, compatibility and cost readers still return zero faults
with retired inputs. Final cost reader's 23 mutation controls also pass again.
`source-staging-snapshot.zip`/manifest/diffs retain ignored p603 source fixtures too;
publication must explicitly include those sources rather than assuming Git status
lists ignored fixtures.

Recorder regression: `python tools/test_reccheck.py`, 306 checks, 0 failures.
Read-only canonical corpus HEAD control vs unchanged staging reader: 370 rec/view
files, both 173 faults/610 notes; all findings, bytes and inventory equal. Only
aggregate output is retained, not player data/paths. Existing faults remain, so
this is no-increase evidence, emphatically not clean-corpus acceptance.

Legacy remains default (`ui_native_scores 0`). **Staging verified is not committed,
published, deployed or accepted as full scoreboard/modern UI migration.**

## Physical-font continuation — 2026-10-09, NOT published/deployed

Owned root: `C:/FTESurf-worktrees/imgui-font-20261009T131505Z/` (OWNER.md and
CHECKPOINT.md). Inspected adopted branches/refs are unchanged from above. No
canonical install/player settings, peer source, index, engine patch pin or Build
number was changed. This is a bounded sizing foundation, **not font-quality,
automatic Windows DPI, physical-device or full migration acceptance**.

### Policy and compatibility

`ui_native_scores_font` is an archived physical-pixel request, default13; it
only affects the opt-in native table. Requests in `(0,128]` snap to the nearest
**13/16/20/24** (ties smaller); other numeric values use13. FTE reads literal
`nan`, `inf`, `-inf` cvar spellings as +/-0, not IEEE non-finite QC values: the
rig proves raw spelling plus observed numeric zero/default selection. No font
preference UI, shared QC/native typography or automatic DPI selection is claimed.

Score owner205 creates four actual ProggyClean bakes in one immutable 512x256
RGBA atlas (512 KiB here) at Open. Global/font/framebuffer bitmap scales stay1.
Size changes do not reopen, recreate or upload an atlas; style dimensions scale
from an immutable base, never cumulatively. Column/button budgets scale with the
font. Wrapped heading/standing still reserve paging and usable scrollbar space;
large-size overflow is horizontally scrollable. Still **six rows per page**;
this does not solve density or wider glyph coverage.

The old five metadata widgets remain valid/default13. Optional sixth metadata
`id=6,row=1,type=TEXT,label=13|16|20|24` chooses a bake. Generic NativeUIModel/1 ABI
and 64-widget bound are unchanged; larger QC requests use60 widgets (6 metadata
+54 cells). Unsupported labels/type/row reject atomically. The actual prior
scoreboard plugin accepts default13 but rejects larger metadata, producing a
usable one-shot, gesture-latched legacy cover; a fresh default13 gesture restores
native. Changed size advances revision and abandons held authority. Equivalent
requests normalized to13 do not republish authority.

### Acting results and falsifiers

- Actual ImGui/plugin `-Werror`, both index widths: **3,750** scoreboard checks
  +109 passive adapter controls per width, zero failures. Actual rasterizer pixel
  sizes/glyph metrics, no bitmap scaling, exact geometry under independent virtual
  X/Y scales, held-change cancellation, old-schema restore, bad metadata, literal
  markers and wrapped/narrow large-font paging/wheel/drag/scrolled-line actions.
- Source-only selector-freeze control: metadata/input still ACT, but selects13.
  Exactly five actual-bake failures at each width; every other control passes.
  `control2/control.json` and `artifacts/selector-control.json` bind the factor.
- `runtime/p603-scores-i2o896au`: GL native1/native2/legacy/absent font matrix,
  zero reader faults. Actual watch identity/body at each size, native paging,
  held size-change/fresh recovery, request/boundary controls, retained context and
  atlas counters, screenshot ink height and exact heading ink equality across
  virtual scales. Screenshots inspected; larger sizes use the scrollbar. Bundled
  face aesthetics and Unicode fallback are NOT accepted.
- `runtime/p603-scores-g0sufndw`: actual prior scoreboard DLL from the parent
  root, both virtual scales. Default13 native, 16/20/24 usable legacy cover, no
  retries/closed work, fallback watch and fresh default13 recovery; zero faults.
- Font reader: **33** read-only positive/negative controls, zero failures, all
  input evidence hashes unchanged. Watch/status witnesses are interval-bound;
  missing/duplicate probes, borrowed controls, inert requests, wrong size/ink,
  stale activation, reuploads and removed plans cannot pass. Base reader27;
  input bridge929/model bridge463; real ImGui input700/model184 per width, green.
- `runtime/p603-perf-uwxgeqg0`: uninstrumented **explicit font13**, six total
  rows for equal visible work, three repeats/five 100-frame snapshots per phase,
  all three arms and complete cost reader pass; cost reader23 mutants green.
  Median QC UpdateView us/frame (closed/open/after): native364.26/820.78/354.06,
  loaded legacy353.68/738.83/351.80, absent348.72/748.39/356.18. Native open range
  735.67–895.41; loaded legacy717.52–821.47. Earlier same-six-row whole run
  `p603-perf-42q06ap5` measured973.38 vs689.66 open medians; both are retained,
  not cherry-picked or a controlled speedup claim. Summary/provenance retained;
  not all-size/GPU/device acceptance. `p603-perf-msb4cab5` also exercised128 rows,
  but its six-native/many-legacy visible work is NOT a speed comparison.
- Reccheck306/0. Read-only HEAD control vs unchanged staging reader over canonical
  data/runs: **360 rec/part/view files**, both **173 faults/610 notes**, identical
  findings and unchanged bytes/inventory. Aggregate only retained; existing faults
  remain. This is no-increase, emphatically NOT a clean-corpus claim.

Initial failures remain evidence, not passes: 12 reader failures assuming IEEE
nan/inf passed through cvars (actual numeric +/-0); two large-font line failures
from aiming at the scrollbar's old left edge after previous scroll survived.
Final controls reset through **real horizontal wheel input**, then drag the real
thumb; no product scroll reset was added. A first source-only variant omitted
pinned LICENSE.txt and could not build: not mechanism evidence. QC NoDeploy again
compiles all three programs with0 warnings, then its pre-existing install-summary
lookup fails; `artifacts/qc-build.log` and the generated outputs are the evidence.

### Reproduce and remaining work

From `C:/FTESurf-imgui-input`, with owned output paths:

```
python tools/test_p603scores.py --out ROOT/artifacts/font-host
python tools/p603scores.py --qc-artifacts <NoDeploy-output> --plugin <new-dll> --engine <subject-exe> --arms native1 native2 legacy absent --font --out ROOT/runtime
python tools/p603scores.py --qc-artifacts <NoDeploy-output> --plugin <prior-score-dll> --engine <subject-exe> --arms native1 native2 --font --font-fallback --out ROOT/runtime
python tools/test_p603font_unit.py <new-font-rig> <prior-score-rig>
python tools/p603font_variant.py --out ROOT/selector-control
```

Font runs separately from follow/HTTP/lifecycle. Its test-only command wrapper
moves real input and reports metadata; it does not inject actions or mock font,
score, watch or line bodies. Source hashes/commands, staged DLL/QC, compile logs,
PNG evidence, retirement manifest and aggregate corpus result are under ROOT.
Stage remains **uncommitted/unpushed/undeployed**, legacy default0. Next: denser
budgeted pages, better face/wider glyph and shared font/DPI policy, physical-device
and human acceptance, clean-tree review/publication and dual deployment. Fetch
both repos and reallocate max+1 then; p603 is not a reserved product patch.

## Density continuation — 2026-10-09 UTC (latest handoff)

Task root `C:/FTESurf-worktrees/imgui-dense-20261009T150334Z` (ROOT below).
Adopted QC/engine heads remain `78297a0141241a7ba8a44ed27123840419234ad1` /
`368a622ce99d17a44a17f1dee3b85859daf14836`, both on `imgui-input-600`, dirty.
No patch allocation, commit, push, Build/pin bump, install/fleet or default change.

**Change.** Separate exact-size `NativeUIModel/2`, fixed256 widgets and the same
UTF-8/ID/typed-action grammar; /1 remains exactly64 widgets. Registration2 requires
that same provider's /1 and input services; teardown clears both. The optional
`ui_native_model_limit` builtin negotiates256 or64; absent on an older engine,
the QC wrapper conservatively uses64. The real table caps24 nine-cell rows plus
5 metadata (font13) or6 metadata (other physical bakes):221/222 widgets. It does
not upload the whole data store. QC numeric/label cache halves are1024 floats /
256 labels, tokens/keys24 each. The existing physical viewport/clipper handles
vertical and horizontal overflow. Page/first-row-identity/count replacement
resets vertical scroll to the new first row; same-identity font/checkbox/geometry
revisions retain their vertical view. /1-era provider/engine combinations still
render six-row native pages; unavailable/disabled routes keep acting legacy.

**Controls.** `artifacts/dense-host-final.log`:597 /2 bridge checks; each16/32-bit
real ImGui host has2872 dense +3750 original scoreboard/font checks, all0 failed,
compilation `-Wall -Wextra -Werror`. `source-control` snapshots only source/headers:
freeze the row cap24->6; all3750 originals ACT and exactly the24-row acceptance
fails per index width, while the identical subject passes. Measured snapshot
sizes: /1 7180 bytes, /2 28684; two VM stage/current pairs114736 bytes. These are
bounds, not a measured CPU/GPU or allocator acceptance.

Final six-arm GL rig: `runtime/p603-scores-5f6pmftb`, zero faults: native1/native2,
prior physical-font provider, prior /1 engine, legacy/default-off and absent.
32 real local rows prove row9/tail watch,20-sample line on/off,24-row paging,
follow/highlight to31, held rescan/font cancellation, stable unchanged revision/
atlas and released idle work. A real loopback32-row board uses authoritative
synthetic *phash + actual callback/parser/FindMine (never ob_mine), and proves
own31, consistent mixed-rate time/ms delta, identical replacement, reorder,
shrink32->4 and cold/warm HTTP Row0 identity. Request/response/replay hashes and
PNGs are retained. All69 read-only reader positive/negative controls pass and
leave source evidence bytes identical. Common physical13px rank ink matches
at both virtual scales despite different inherited shell extents.

Regression:173 passive +929 input bridge +463 /1 model bridge; per index110
adapter/passive +701 input +184 original model controls, all0 failures. The
original eight-row HTTP suite also passes using the prior /1 font provider with
the new QC/engine (`runtime/p603-scores-n1cniwno`), and its29 reader mutants pass.
All three product QC progs compile0 warnings. Full native compilation/linking
completed; unchanged engine warning sites remain, and the known NoDeploy final
installed-DAT summary `Get-Item` failure is retained, not called a successful
wrapper exit. Final native DLL builds warning-free with warnings fatal. Corpus:
370 rec/part/view files (10 additional peer views since the font checkpoint),
HEAD and staged checker both173 existing faults/610 notes, identical findings
and unchanged bytes/inventory during the read-only sweep.306 reader tests pass.

**Retained failures.** Initial underspecified viewport and clipper row-metric
controls failed; tall font13 fits all24. Equal-sized page replacement genuinely
hid the new first row before its fix (12 failures per width). The first six-arm
reader incorrectly treated legacy peek as native-inert and compared variable
raw crop extents; legacy's existing clickable cover is now separately acted,
and common-region glyph ink is strict. The first /1 online counterpart clicked
Previous once from page30 (not24), so it had not reached row0; repaired with FIVE
real Previous actions and rerun, not by faking page state or injecting actions.
Early shell quoting/argument conversion and the QC `isfunction(functionpointer)`
warning remain logs; correct guard is `checkbuiltin` and full build is launched
through Python's Windows argv. Synthetic extension-row rates were made consistent
with their ticks/ms before final response hashes and time/delta assertions.

Reproduce from `C:/FTESurf-imgui-input` (TEMP/TMP beneath ROOT/tmp):
```
python tools/test_p603dense.py --out ROOT/artifacts/fresh-host
python tools/p603dense_variant.py --out ROOT/fresh-six-row-control
python tools/test_p603dense.py --control ROOT/fresh-six-row-control --out ROOT/artifacts/fresh-control
python tools/p603scores.py --dense --qc-artifacts ROOT/artifacts/product-qc --engine ROOT/artifacts/native-build/fteqw64.exe --plugin ROOT/artifacts/native-build/fteplug_ui_imgui_x64.dll --old-plugin ROOT/artifacts/predecessor/fteplug_ui_imgui_x64.dll --old-engine ROOT/artifacts/predecessor/fteqw64.exe --arms native1 native2 oldplugin oldengine legacy absent --out ROOT/runtime
python tools/test_p603dense_unit.py ROOT/runtime/p603-scores-5f6pmftb
python tools/p603scores.py --grade ROOT/runtime/p603-scores-5f6pmftb
```
The CLI now returns nonzero on a failed grade; inspect logs, not only subprocess
completion. Core C and nearest native C++ compile databases were regenerated;
latest LSP records can be stale/default-include fixture diagnostics, not compiler
or QC proof. Full command/output/source/binary hashes and retirement inventories
are in ROOT. Only owned, verified duplicate synthetic copies/objects are retired;
unique source, controls, inputs, logs, PNGs and synthetic data remain.

**Next goal:** dense recurring CPU/GPU/allocator/percentile and endurance budgets,
then denser-store backend parity (GL only here; earlier six-row D3D11/Vulkan
controls do not certify /2). Face/wider glyph/shared QC-native DPI policy,
physical-device/human font/input acceptance and independent clean-tree
review/publication/dual deployment remain held. Retain legacy default0.
