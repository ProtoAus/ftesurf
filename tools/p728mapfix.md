# P728 — map appearance, Prosurf B4 and OpenGL shadow lift

## Delivery state and scope

Locally implemented/built/tested; **not installed or deployed at source verification**.
The other task's published P727 acceptance explicitly released the NanoPi/deployment
hold at2026-10-15T15:35:36Z. Normal guarded development delivery can proceed; that
release/source note alone is NOT a delivery receipt for P728. Do not alter/replay
the sealed backend generation or its controls. No owner game was stopped and no
owner config or player-data tree was modified. Build number is unchanged.

Implemented: Prosurf B4's authored bhop-launch eligibility; Leidenfrost's authored
nearest sampling; Sidistic's softer light-blue automatic grade; an OpenGL
`shadows` command integrated with scene gamma/brightness. **Monolith B4's speed
is not fixed.** Its measured discrepancy and closing falsifier are in BACKLOG.

The owned retained task root is
`C:\FTESurf-worktrees\mapfix-01a13ff6\` (`OWNER.md`). QC/engine worktrees, a clean
engine control, small content overlays, generated fixtures and compact evidence
are under that one root. Sources started at QC
`36697da09d3893e2f3c192d9be55b2974287f02c` and engine
`f84fb0ada93b5197acb20aba6f3e34203c31c6ea`. No peer working-tree files were used.
A temporary shared `tools/p728mapfix.claim.md` reserves the number only; it is
not product source and is removed by its owner after the real entry is published.

## Commands / behavior

```text
gamma 1
brightness 0
shadows 0.35
shadows 0.6
shadows 0
```

`shadows` (alias `v_shadows`) is archived. Zero disables it; effective strength
clamps to0..1. It lifts scene luminance smoothly, preserves RGB ratios without
clipping a channel, leaves the deepest toe (<=2/255 luminance) and highlights
(>=0.65) alone, and uses stable sub-LSB spatial dither, not temporal noise.
The scene and grade/exposure intermediates prefer RGBA16F. Exposure sees the
map's **graded output**, before AA/bloom compositing and before the HUD.
The lift does not recover information or banding already baked into a texture.
Vulkan/D3D lift, HDR/display calibration and subjective banding comfort are not
claimed; OpenGL/Windows is the measured path.

Source OpenGL uses the scene shader for gamma/brightness rather than depending
on OS/texture gamma policy. Both controls already acted in the clean connected
control in modes0 and1: **no server cvar lock was reproduced**. Do not describe
that experiment as proof that gamma was broken on every server, or edit the
owner's saved config to force a result.

Sidistic's automatic hue is195 degrees with0.65 saturation. These values are
computed once for both diagnostics and generated shader arguments, and enter
the shader's policy hash. `hl2_colour_hue -999` selects the map default;
`hl2_colour_hue 0` retains original hue/saturation. An explicit user hue retains
its original saturation semantics. Other maps keep their automatic policy.

## Prosurf implementation and controls

The map/START/track guards restrict permission to `surf_prosurf` B4. Membership
in an authored `ZONE_BHOP` region is captured at the grounded jump-command seam
beside `run_jumpcmd`, using that command's origin/hull. The arm index is saved as
index+1; an outside attempted jump denies the whole packet and cannot be erased
by a later inside command. The consumer still requires the same arm. It suppresses
a new hopped-start accusation only: it does not forgive prior hopped/dirty taint,
change velocity, settle a start or bypass recording/evidence.

An initial previous-packet-origin implementation was rejected by two independent
reviews. Two corrected-diff re-reviews found no concrete issue. Their scope was
predicates/reset coverage, not a claim to have executed a real network recovery.

Controls retained under `artifacts/`:

- Real dedicated baseline: the natural B4 sequence earns hopped/practice. The
  first subject and the corrected final subject both reach2275 horizontal with
  practice0, recording1, hopped0 and dirty0. This is260 movement + the authored
  2015 boost; the faster foreign clip approaches with a different initial speed.
- Corrected subject with outgoing throttling (`cl_c2spps 10`) also reaches2275
  with practice0/recording1/hopped0. This is a throttled real-client arm, not a
  manufactured claim to reproduce every packet-loss/recovery topology.
- The13-check runtime fixture calls the actual helper/watcher: inside command
  with outside previous endpoint, outside command with inside previous endpoint,
  both batched orders, prior hopped+dirty preservation, other arm/map rejection,
  invalid arm and arm-change refusal. All13 pass; outside controls actually
  acquire hopped taint, so this is not a disabled-detector pass.
- Separate real-client PostThink receipts seed both permission fields13/1 and
  observe0/0 after an advancing packet on normal, no-zone timer early-return and
  held paths. All3 pass. The fixture restores its temporary state.
- An acting outside held-hop control acquires/preserves practice1/recording1.
  Attempts to combine a prior bad hop with a later **boost** missed the booster;
  those are retained non-acting boost arms, not proof of that combined path.
  The actual prior-taint classifier predicate is covered by the unit control.
- Final clean product progs contain the command hook and **no test-fixture
  functions**. On that product alone the natural launch reaches2275,
  practice0/recording1/hopped0. The original client log, not a too-short console
  read window, supplies `prosurf-clean-product-receipt.txt`.

Natural input recipe (real dedicated socket; start only after `cmd viewpos`
answers; run with all movement buttons released first):

```text
menu_restart; ui_close
cmd zone_goto 12 0 0
wait 90; +forward; wait 50; +jump; wait 80; -forward; -jump
cmd viewpos; cmd timer
```

Wait counts depend on actual frame cadence. Inspect the full logs and actual
velocity/class state; a returned-to-start body or silence is not a pass.
Generated ENT/QC fixtures are excluded from the product manifest and were moved
out of the runtime before the clean-product proof.

## Image / build verification

- Clean baseline and subject engine/client/server/HL2 plugin builds used the same
  compiler, flags and shared read-only dependency bundle, from isolated source.
  No actual install output target was used. QC builds have zero warnings.
  The clean native control has60 existing compiler warnings /36 warning payloads;
  successful full+incremental subject builds introduce no new warning payload.
  Make grouped-target notices are reported separately, not compiler diagnostics.
- clangd's database was regenerated. The edited C translation units have no new
  errors; standalone header/plugin analysis has include/configuration limitations.
  Actual native compiler/linker results, not LSP alone, establish build success.
- Leidenfrost: the packed VTF census identifies authored `POINTSAMPLE` textures.
  Successful image load preserves nearest (and authored no-mip policy where
  applicable), unless an explicit linear/nearest sampler already controls it.
  Same-camera baseline listings lack `NEAREST`; subject diffuse listings have it.
  Global `gl_texturemode` is unchanged. A static51800-pixel floor crop changes
  39895 pixels (MAE1.3675), with effectively unchanged average brightness.
- Sidistic: screenshots of old150-degree green, explicit195-degree hue, final
  automatic pastel grade and original-hue control were inspected. Final grade
  and generated policy are active; exact preferred shade remains human acceptance.
- Final native chain listings prove `rt/$lastgameview` and the colour-corrected
  intermediate are RGBA16F. On a static Sidistic crop shadows0.6 changes the mean
  from46.73 to63.41; brightness0.1 changes it to71.18. Returning both controls to
  neutral restores the crop **exactly** (MAE0). The HUD is not lifted.
- `python tools/test_image_controls.py --engine <engine-checkout>` and the same
  command under `python -O` compile the actual exposure GLSL in an owned hidden
  GL context. Native stage-order check and12 GPU checks pass: neutral identity,
  exact toe/highlight preservation against the neutral float path, acting lift,
  temporal stability, strength bounds, monotonic mean ramp, >450 spatial mean
  levels after8-bit quantization, grey/colour preservation and gamma/brightness
  action. A neutralized/optimized-out lift is specifically rejected in both modes.
- Reader tests:306 checks, zero failures. Read-only run corpus:813 recordings and
  661 views,190 pre-existing faults, zero exceptions. Candidate reader bytes are
  identical to the base reader, so the same content-set hash gives190 baseline
  and190 candidate faults: no increase and **not** a clean-corpus claim.

Screenshots, test-source variants, original failed builds/arms, sanitized summaries
and source/binary identities remain under `artifacts/`. The first hand-transcribed
base SHA was corrected after a reviewer checked it. An early reference-summary
parser reported zero rows because of a wrong width assumption; the raw frozen
recordings were not changed, and `reference/validated-snapshot.json` is the corrected
parse. Do not silently relabel these failed preparation/measurement arms as passes.

## Monolith limit / remaining work

The default and reference-lane owned physics probes both plateau near1643.13.
Three supplied clips reach about1668.86 then1666.07; the fourth has its own small
transients/plateau around1669. These are inspected foreign recordings, not proof
that the Momentum BSP's converted trigger is byte-identical to the original CSS
map. `StrictMode` is unimplemented here but not established as the cause.
No arbitrary horizontal-energy addition, global movement adjustment or guessed
strict-mode implementation is in P728. The original CSS control BSP could not be
retrieved from the attempted public endpoints. Need matching original map bytes
or authoritative trigger semantics to select/falsify a conversion versus mover fix.

Remaining: Monolith's actual fix; owner shade/display/fast-surf acceptance; then
guarded dual-install/fleet delivery after the now-released cutover hold. Record
actual destination hashes and live readback, not an inferred delivery from source.
Built, committed, published, installed and verified-live remain separate states.
