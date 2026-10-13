# P686 — Perfect-board feedback

## Use

Open **`hud_edit board`** (the HUD editor's **Board** pane):

- **Perfect sound:** Off / Dong / Bong / Bell. Original soft synthesized cues.
- **Sound volume:** Mute through 100%, also scaled by master volume.
- **Perfect rainbow:** independent colours cycling across Perfect's letters.
- **Perfect bounce:** individual letter phases, with modest vertical travel.

Defaults are Dong, 35% volume, rainbow On, bounce On. Console equivalents:

```text
hud_board_sound 1       // 0 Off, 1 Dong, 2 Bong, 3 Bell
hud_board_volume 0.35   // 0..1
hud_board_rainbow 1     // 0/1
hud_board_bounce 1      // 0/1
```

The first Perfect plays at base pitch. Each subsequent Perfect requests another
semitone, capped at one octave above base (13th Perfect). A **non-perfect graded
ramp arrival** resets it; the next Perfect returns to base pitch. Bhops, ordinary
ground/air transitions, repeated snapshots and ungraded low-speed contacts do
not count as failure. Run resets preserve it; a new map/VM starts fresh. Off and
Mute continue tracking it. Replay scanning never triggers or alters live sound
feedback. The word effect is visual only and can also decorate a viewed Perfect.
The percentage, other grades and other rows retain ordinary rendering.

## Reproducible controls

QC parent: `38fec0d7edde71a986c9f21b03a50352aba5203f`.
No mover, server QC, grade thresholds, recording/evidence grammar, engine C,
engine pin/tag, Build number or release change.

Under a newly owned task root with OWNER.md, after reading workspace/harness
notes, use pwsh 7 from each clean worktree's `src/`:

```text
pwsh -NoProfile -Command "./build.ps1 -Jobs 8 -NoDeploy"
python tools/board_sounds.py --check
python -B tools/board_feedback_smoke.py --output-dir <owned-root>/subject --port 27617
python -B tools/board_feedback_smoke.py --source <parent-worktree> --control --output-dir <owned-root>/control --port 27616
```

`fteqcc64.exe` is a build prerequisite, not a committed dependency. The smoke
uses the canonical install's content and the existing `runlines_smoke.py` process
harness; numpy and Pillow grade pixels/PCM. Test-only copied CSQC intercepts
live stats and sound arguments, then invokes **production Board_Frame**, grade,
feedback, drawing and editor options. It never ships the test seam. The raw
capture is this isolated client's own mixer, not host/system loopback audio.
The control only receives an inert streak stub and predeclared test cvars so
missing feature assertions ACT instead of failing unknown-command guards.

At 2026-10-13, owned task `C:/FTESurf-worktrees/boardfx-1013043332`:

- Stock and final subject production builds: zero QC warnings, all three VMs.
- Control5: **26 checks, 20 expected failures**, zero animated pixels/cues.
- Subject6: **26 checks, zero failures**, including actual grade, single event,
  unchanged counter, ground/air bhops, run reset/resync, rejected contact,
  non-perfect reset, Off/Mute tracking, paths, volume clamps, octave cap,
  replay scanner failure/perfect and map reset, editor bindings.
- Subject6 pixel changes: rainbow **2,974**, bounce **4,901**, time-separated
  rainbow+bounce **5,750**. Percentage suffix, non-perfect and grade-hidden
  controls: **zero** changed pixels. Ten screenshots retained; Board editor
  settings are visible and its expanded pane fits. Synthetic scene backgrounds
  are blacked out locally so moving map dust cannot fake glyph changes.
- Native PCM: exactly six onsets. Dong fundamentals **391.85 → 410.52 → 434.69
  → 391.85 Hz** across Perfect/Perfect/bhop/Perfect/fail/Perfect. Bong **195.92**,
  Bell **784.06 Hz**. No hop/failure/Off/Mute extra sound. QC pitch requests are
  100/105.9463/112.2462/100%; native software mixing quantizes speed to 1/64.
- Reproducible WAV generation passes byte-for-byte. Both stock and subject
  shipguard pass against the same canonical content-directory enumeration;
  isolated Git worktrees lack ignored runtime content, so an unmodified
  direct shipguard initially stopped at their absent `particles/` directory.
  New sounds are three explicit ShipGameFiles, never a broad sound-directory
  glob (which could publish personal audio).

Harness corrections before the passing controls: initial copied fixtures used
incorrect replay-global names; those did not compile. Early configs used a
misspelled soundscape cvar and a HUD cvar before registration; runtime guards
caught them. Screenshots are deferred: a wait **after** each screenshot prevents
photographing the following arm. Summing per-glyph advances moved the percentage
one pixel; drawing its original mono-space-prefixed whole string fixes that.
Initial open-background pixel controls saw moving dust; the isolated backdrop
makes unchanged controls exact. These failed attempts are not passing evidence.

## Limits and deployment

This is a presentation integration test with injected live stat arrivals, not
new movement/physics proof. Human sound softness, preferred timbre, volume and
bounce feel remain in `lextest.md`. No private player/evidence data is used.

At **2026-10-13T05:19:28Z**, product `d18b5610d4cb0d07b24fa62c3b10f8bc27b55455`
and engine documentation `5cb53c38aa426281ba80c887b7776ecc38ce077e` are committed
and pushed. A clean product-tree `build.ps1 -Jobs 8 -Pi` passed with zero warnings,
refused no safety gate, found all twelve lobbies empty, preserved `.prev` and
restarted them. Both Windows installs have hash-matching qwprogs/csprogs/menu
and all three cues; personal `ftesurf.cfg` files are unchanged. No native binary
or plugin was rebuilt/deployed, and menu remains Windows-local.

The three WAVs require explicit copying: build.ps1 ships programs, not arbitrary
new assets. The initial Pi restart preceded the new sound directory, so its
filesystem lookup did not see them. After copying and a guarded empty-fleet
restart, fresh unseeded clients using **each installed Windows executable**
separately downloaded the exact served CSQC and all three exact WAVs. Both Board
pane screenshots were inspected, defaults read 1/0.35/1/1, and the passing logs
have no command/VM errors. All twelve final nonzero PIDs, active units, UDP ports
and fresh empty directory rows are verified. One early live client command
arrived before CSQC spawn; a longer fresh arm passed. The current HTTP mirror
returns 404 for these new cues, but engine-server download fallback is proven;
no HTTP mirror/release deployment is claimed.

Verified program/cue SHA256:

```text
qwprogs.dat    f427438dff25d08bd4d08428c9b2a4882f7549b00044898f92e9ad165dd639b6
csprogs.dat    723501aad2045fd9dd7621f2ce4cef73952be4f43d3e6b7ce0116f466a5d9e66
menu.dat       f13f792cb416ff0752ce51c1ac2cd0520e462a0f9a7c314b18caae2492e407c1
board_dong.wav e30decfff2c4ba7401af5204c5a848e926a5d2cda4e68d6dee2823a40a8d4efe
board_bong.wav f15633f3eb94da9abd9c399212810d0e8a3c41935fc26b0804e85c8b150de594
board_bell.wav 8e116a78dbd0d4b1d37854de3a7f42220ee79825f4751081068ffb87fd0a6123
```

Canonical shipguard also passes after source/assets arrive. Config defaults are
archived source; existing owner settings/config are not overwritten. Retained
small logs/metrics/PCM/screenshots and verified binaries live under the owned
task's `artifacts/`; disposable worktrees/build copies and linked overlays are
retired after the source/metadata are preserved. The canonical engine checkout's
pre-existing modified documentation and unrelated untracked file remain untouched.
