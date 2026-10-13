# Sound-reactive spatial sky

## Controls

Open **VISUALS → sky + audio**:

- **Audio source → Windows output** listens to the default Windows playback
  device using WASAPI loopback. Music playing outside the game, game sounds and
  system sounds drive the existing analyser. It does not play the captured sound
  again, open a microphone or save audio to disk. Capture is explicit opt-in;
  **game mix** restores the existing source. The source preference is archived.
  Choosing Windows output stops the game's menu music; automatic menu music
  does not start over your external music. The music page still allows manual
  playback if you want it.
- **Sky perspective → spatial** gives the visualizer sky a map-centred enclosing
  space with near/middle/far layers. Camera translation changes their apparent
  positions at different rates; the level itself and its physics are untouched.
- **Sky colours → map thumbnail** uses the level's existing thumbnail atlas.
  Missing thumbnails fall back to neutral colours. It does not download images
  or change the level's materials.

Enable **VISUALS → look → In-game sky → visualizer** to see the sky effects.
The saved owner preference leaves this **off** by default, so ordinary map skies
are not replaced without choosing it.

Console equivalents:

```text
snd_vis_source 1        // Windows default playback output; 0 restores game mix
snd_vis_status         // Local capture/source status; no endpoint identity printed
milk_sky 1
r_skybox milk
milk_sky_parallax 1     // 0 fixes the enclosing layers; values 0..1 scale translation
milk_sky_palette 1      // 0 restores procedural colours
milk_skyinfo            // Map, thumbnail coordinates and bounded-reader status
milk_skyinfo refresh    // Re-read regenerated metadata immediately
```

Windows capture is unavailable on non-Windows builds. The visualizer still
requires OpenGL. The output device must allow shared loopback; protected audio
or an unavailable/exclusive endpoint can produce silence. Capture follows the
Windows default playback device, not an arbitrary per-application output route.
There is no microphone, per-app capture or microphone-monitoring feature.

## Late or regenerated thumbnails (P691)

The metadata table is generated locally by `tools/mapmeta.py` /
`tools/mapthumbs.py`; it is not a menu download. Late atlas image decoding and
late metadata publication are separate cases. The sky now retries unresolved
metadata every five seconds and rechecks resolved coordinates every 30 seconds,
without requiring a map reload. `milk_skyinfo refresh` starts an immediate scan.

Lookup reads at most 64 rows per active sky view. A same-map refresh retains the
previous valid palette until it resolves; absent/malformed coordinates then
restore neutral colours. Map changes clear old coordinates immediately. World
load, renderer restart and disabling the sky close any in-flight file. Re-enabling
restarts an interrupted scan. Status reports `rows` and `maxbatch`, which is the
largest actual row batch in the current scan, not an assumed frame count.

Acted P691 controls in an isolated dedicated `surf_rookie` session:

- Missing row → late row: neutral → tan sky, same map, no explicit refresh.
- Replace coordinates behind 1,024 unrelated rows: tan → olive sky; 1,025 rows
  resolved with measured `maxbatch 64`. Clearing the row restores neutral.
- Non-numeric page is rejected rather than silently becoming page zero. File
  disappearance clears stale colours; reappearance recovers without refresh.
  Blank lines before the late/restored row are read rather than mistaken for EOF.
- `vid_restart`, sky off during a scan, re-enable and automatic 30-second
  successful-row refresh all recover. The off-state scan closes without reading.
- Otherwise-identical compiled no-retry control is rejected specifically at
  `META-RECOVERED`, with all writer phases and the client end marker acted.
- All three QC programs compile at zero warnings; eight static production/mutant
  contracts and the 17-default consistency check pass.

Reproduce with an owned task-root output directory and installed P688+ native
client/server/plugins:

```text
python tools/test_soundsky_metadata.py --output-dir <owned-artifact-folder>
```

The test edits only its private overlay's `data/mapmeta.txt`, never the install's
metadata or player profile. Page 5 cells 0/1 and `surf_rookie` require the existing
installed content. It keeps logs/screenshots/VM hash and a phase-action receipt.
P691 changes CSQC, not capture or renderer code. The existing engine pin/tag
is not moved by this patch; its tests ran on the P688 native runtime. No Build/public release bump is implied.

## Visual defaults

The shipped visual settings match the owner's saved profile snapshot: menu on,
ultra quality, native resolution, lattice world, flat panels, trails and normal
reactivity on, natural colour grading, menu+sky streaks, sounds/muffle on, FSR /
checkerboard / coarse pass off. Existing saved preferences continue to win.
Music remains **auto**, rather than shipping somebody's personal track selection.

## Verification

Patch **688**. Native source: `73322dff5b6898511d62ed775286b23a91b8aad0`,
annotated tag `patch-688`. QC Build/public release number unchanged. The feature
was integrated on published P687 sources, not another session's working edits.
No launcher/bootstrap/feed publication is part of this deployment.

| Control | Result |
|---|---|
| Native float/PCM downmix, finite input, silent packets, ring/reset | C99 `-Wall -Wextra -Werror` passes, Windows and forced non-Windows fallback |
| Real Windows external tone vs game-only source | Selected loopback captures packets and ~0.177 RMS; game-only has capture inactive and zero RMS |
| Quiet tone-stop/source switch | Initial controlled silence reaches zero; source0 closes capture and clears output |
| Later quiet rerun | Not measured: other playback remained active; it was not stopped or muted to manufacture silence |
| Production sky-fragment pixels | Near/middle/far move 13/6/3 pixels; fixed sky stays fixed; equal-depth/disabled-parallax mutants rejected |
| Thumbnail colours | Red/blue controls follow their hue; mixed image retains both; single-average mutant rejected; missing/grey remain valid |
| Fresh profile + saved override | 46 runtime readbacks pass, including overrides across menu_restart; wrong-default mutant rejected |
| Actual engine sky | Dedicated surf_rookie: atlas5 and 32x18 thumbnail RT load, olive/tan vs procedural blue, moved eye and vid_restart screenshots inspected |
| Windows-source menu | Selected chip visible, capture active, automatic menu track empty, 19-second snapshot flight completes with live audio |
| Build/diagnostics | All three QC programs zero warnings; cold native subject/control both 35 compiler occurrences/26 payloads (zero new); database-aware clangd check zero errors |
| Static lifecycle/sampler contracts | Production passes; omitted blank upload, initial-only lookup and shader-level program mutants rejected |
| Independent review | One stale-spectrum blocker fixed; final review OK with notes |

Live native renderer/CSQC temporary probes were removed: no renderer change or
preview overlay ships. Map lookup must be deferred because WorldLoaded's map
key was empty even though its world bounds were valid. `program milk_sky` stays
inside its pass so successive RT maps bind distinct samplers.

Reproducible public checks:

```text
python tools/test_milk_defaults.py [isolated-client.log]
python tools/test_soundsky_contracts.py
python tools/test_soundsky_sky_pixels.py --output <owned-artifact-folder>
```

Runtime fixtures: `cfg/test/milk_defaults.cfg`, `soundsky_sky.cfg`,
`soundsky_menu.cfg`, through `tools/runlines_smoke.py` in an owned task root.
The sky test needs `--put data/mapmeta.txt=<install>/ftesurf/data/mapmeta.txt`
and `--mount`; use the paired inspected native client/server/plugins. Menu
snapshot flight must disconnect first. The harness's legacy-profile GLSL
`varying`/gl_Vertex/gl_FragColor deprecation notices are not new QC/native
warnings. Compiler and actual output, not the material diagnostic's shader-only
`prog` count, establish whether the program acted.

Physical endpoint replacement/unplug, live server-origin command refusal,
Linux runtime and broad in-game performance remain unmeasured. The blank GPU
spectrum on unavailable input is code-reviewed against the native blank-image
path, not claimed as a new GPU readback test. Human acceptance of scale, art
direction and feel while surfing is listed in `lextest.md`.

Exact Windows client SHA256:
`5c77bd8175b01da20989c33ac4839edc61bd0ba546c315863dbbf864068070f7`.

## P691 deployment — 2026-10-13

Feature commit `70e92c1` was integrated with published P690 documentation at exact
clean QC source `1d4e3a75ffd73677b3a604d3a744342e7eca5740`. Engine patch record is
`9c7737643`; no new native runtime was built or shipped. The original unpublished
P689 claim was renumbered after concurrent P689/P690 publication, without changing
or force-pushing anybody's history. The existing P690 source pin/tag is retained;
it is not proof of native delivery.

`build.ps1 -Jobs 8 -Pi` from that clean source compiled all three VMs with zero
warnings. All 12 live lobby rows proved zero players before the swap; previous
progs were kept as `.prev` and all 12 units restarted. Windows delivery at
**2026-10-13T10:35:26Z** copied only the three inspected progs to both installs,
keeping `.prev`; no native binaries, shaders, configs or tracked source were
replaced. Canonical uncommitted visual work was left alone.

Deployed CSQC SHA256 (same as the complete acted metadata subject):
`4263647246709487775dae4d2aba9a74f43b09beb98950992ca24c7d2fffa2b8`.
Both Windows destinations match. Fleet readback at **2026-10-13T10:37:35Z** confirms
matching qwprogs/CSQC, 12 running units and 12 healthy zero-player lobby rows.
A fresh client with no preseeded CSQC downloaded that exact hash from lobby1,
drew an 8-column/type14 board, captured an inspected screenshot and exited zero
with no QC error. That proves serving/live loading, not just remote file copies.
The continuation's saved-profile hash and mtime remained unchanged.

This is a development progs deployment, not a signed updater/feed, native P690
release, Build-number decision or performance/art-direction certification.
