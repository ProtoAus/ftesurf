# P940 — cosmetic viewmodel motion and material footsteps

Owner request: FOV70 looks closer to CS:S; add walking rock and view-angle sway,
and make feet change sound with the material. Cosmetic/audio only: no camera,
aim, player-body, movement, timer, recorder, collection or damage-policy change.
No new assets are redistributed; mounted game content supplies scripts and WAVs.

## Reference and implementation

Public Valve Source SDK 2013 reference, read22Oct2026:
- https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/shared/baseviewmodel_shared.cpp
- https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/shared/hl2/basehlcombatweapon_shared.cpp

Use the reference's 320u/s cap,0.005 amplitude,0.45/0.9 cycles,0.1/0.8 positional
weights and0.4/0.3/0.5 angular weights. Facing lag uses Source's direction-history
idea and5-unit scale, with exponential convergence and a3-unit bound instead of
copying its frame-linear filter. Continue cycling in air as the SDK advises.
These are Source-inspired equations, not a claim of byte-exact closed CS:S parity.

Only the existing viewmodel entity moves. Its existing DPEF_NOGUNBOB flag avoids
stacking Quake bob; camera/aim and saved v_forward/right/up are untouched. Reset
on hide, weapon changes, large position changes and clock/frame discontinuities.
Default r_viewmodel_fov changes54->70 only when it is unset; explicit81 survives.

Foot cues use the existing native trace_surfacename output, with 1-based trace id
converted to a 0-based getsurfacetexture fallback. Resolve safe VMT $surfaceprop,
Patch includes (four levels), surface-profile base inheritance (eight levels),
and left/right aliases from the selected mounted game's relevant player/foot/
physics/surface sound-manifest files. Momentum's separate player file is needed;
assuming CSS's two filenames missed its definitions. Texture guesses remain for
older/truncated BSP names or absent VMTs. Missing WAVs fall back to concrete.
32 material cache entries,256 profiles/aliases,16 files per manifest, bounded
input scans and zoned-string eviction; gameaudio_info refresh and world-load
invalidate all, because a new map pak can shadow an existing texture name.
There is no repeated metadata-file parsing on a cache hit. This is not a total
filesystem-I/O or frame-time claim: existing WAV existence checks still apply.

## Preregistered controls/falsifiers

- Standing/stopping versus actual260u/s movement: only subject has rocking.
- Turning versus resting: bounded facing lag converges; hide/re-enable forgets it.
- Unset FOV->70 versus explicit81->81. No override of personal settings.
- Same metal-named floor with controlled wood/grating/glass/concrete declarations:
  declared property, not substring, must select each family. Every arm must emit.
- Correct mounted left/right variants, inherited VMT and cyclic/missing fallback.
- Repeated stepping must hold metadata-read count;135u/s walking remains silent.
- No source assignment to body, input, camera/aim, timer or recording state.

## Observed native controls — 23 Oct2026

Owned dedicated socket27579/surf_parc_colore,100fps, explicit cvars, no owner
config/data touched. Used first the matched P935 native, then the actual installed
P939 client/server and matching plugins with final compatible REC13 programs.
All launched actors stopped; the exact owned real-floor override was removed,
restoring original absence. Synthetic p940 material fixtures remain in the owned
rig only, not in either install or the repository.

- Fresh default70. Separate final process preserved explicit81, ready USP model,
  actual draw callback. At260u/s final model offset(-.0181,-.5543,-.0181) and
  angles(-.0725,-.2079,-.0906); turn lateral lag.9087. Earlier resting control
  converged to.000502 after1.5s. Hide sets motion-valid0; re-enable returns zero
  position/angles, then ready1. No visual/ear acceptance inferred from counters.
- Synthetic metal-named VMT declares wood and resolves wood_01/02 left,
  wood_06/07 right. Patch-child inherits metalgrate; glass has distinct samples;
  self-include cycle terminates in concrete fallback. Mounted111profiles/67aliases.
- Actual same-floor declarations emitted wood_06, metal_grate_08, glass_13 and
  concrete_ct_08 at260u/s. Repeated concrete stepping kept the metadata count
  while cache hits rose; walking135.2u/s added no calls. These controls used the
  initial whole-file reader; the corrected final line reader re-proved those
  material resolutions and real metal_solid_37 emission at260u/s.
- An empty texture from getsurfacetexture(world,...) was falsified, not accepted:
  existing native trace_surfacename gives metal/metalfloo on this legacy map.
- Initial FILE_READNL loops reread whole files to bounds. Native PF_fgets source
  explains the non-advancing mode. Correct FILE_READ loops keep111/67 with11
  database opens; four synthetic queries total19, then real floor20 and cache hits.
- Mainline and compatible builds compile three VMs with0warnings. Compatible
  server DAT is byte-identical to the21c087d1 predecessor (1218146 bytes).
  QuakeC has no matching LSP parser; an empty diagnostics result is not QC proof.

## Limits and delivery

Owner visual/ear acceptance remains pending in lextest.md. No precise CSS parity,
FPS improvement, actual warp/replay presentation or long-session memory claim.
No new recorder/reader/evidence semantics, so evidence/corpus suites are not a
substitute acceptance gate and were not rerun for this cosmetic/audio-only diff.

Implemented, published, locally verified and deployed to BOTH Windows installs
and all12Pi lobbies. Exact source, hashes, UTC and cold-download proof:
[tools/p940-delivery.md](p940-delivery.md). Preserve P939 native/MENU. The compatible REC13 build is a control,
not the deployment candidate: both Windows CSQCs now match the newer Pi cohort.
A clean8e897d9c control reproduced BOTH live Pi QW/CSQC hashes exactly, and its
CSQC matches both Windows installs. The current source cohort is identified.
P940 mainline QW remains byte-identical. LAN and loopback8084 initially refused;
no force/restart/swap occurred during that block. The directory later recovered,
all12were empty, and the standard guarded deployment/cold-download checks passed.
The actual installed DAT additionally re-proved all four real-floor materials,
quiet135.2u/s walking, metadata12/hits1->3, and real map-reload reset to0. Final
idle/moving screenshots were inspected; owner visual/ear acceptance stays pending.
