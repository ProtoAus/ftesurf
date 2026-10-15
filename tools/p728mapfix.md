# P728 — map appearance, Prosurf B4 and OpenGL shadow lift

## Delivery state and scope

Implemented, published and **installed in both Windows installs**, with actual
installed-binary/dedicated-client verification below. **Not deployed to the NanoPi**:
its directory has no lobby rows and the read-only SSH census is unavailable, so
there is no positive empty-fleet gate. No Pi upload, swap or restart was attempted.
The other task's published P727 acceptance explicitly released the NanoPi/deployment
hold at2026-10-15T15:35:36Z; that release alone is not a P728 delivery receipt. Do not alter/replay
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
The temporary shared `tools/p728mapfix.claim.md` was removed by its owner after
publication; it was a number reservation, not product source.

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
  Those source-verification builds used no actual install output target.
  QC builds have zero warnings.
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

## Windows delivery — 2026-10-15T17:05:09Z

Published product source: QC `181c2aa7ee7dd6687561a79c513365cfa96e0104` and engine
`694bdd54427d8f29937dd6e85fecb76f98f1e6f5` / `patch-728`. Subsequent receipt-only
documentation does not change those compiled product bytes. Build number unchanged.

A fresh `src/build.ps1 -Jobs 8 -Engine -Full -NoDeploy -FteRoot <owned-engine>`
completed on the exact clean product commit. The complete native baseline used
`<owned-engine-control>` at `f84fb0ada93b5197acb20aba6f3e34203c31c6ea` with the
same flags/dependencies. All five plugins were included:74 existing compiler
warnings in each arm, zero new normalized payloads;349 grouped-target Make
notices in each arm. All three QC VMs compiled with zero warnings. The shared
read-only dependency fingerprints were unchanged through both completed builds.

An exclusive file-lease/hash preflight passed before copying. Six primary and ten
secondary files were installed, each with locked and post-lease SHA256 readback.
Every predecessor remains in `.prev` and in the owned compact backup. No game was
stopped and no owner config/player-data path was a deployment target. The primary
client is `C:\FTESurf\ftesurf64.exe`; the secondary client is
`C:\FTEQuake\fteqw64.exe`; the secondary dedicated server is `fteqwsv64.exe`.
Both gamedirs contain the same three built VMs. Primary HL2/ImGui and secondary
HL2/cod/box3d/ode/ImGui are from this same full build.

| Built file (primary client renamed `ftesurf64.exe`) | SHA256 |
|---|---|
| `fteqw64.exe` | `eb9fc78df3b0f6b855f8c2427f6cf0f6985283871c53154945ee992f560e84b0` |
| `fteqwsv64.exe` | `4c269cb7824485434b61a4384ded959c0ac96677b047f6887df42002350be4a8` |
| `fteplug_hl2_x64.dll` | `6a7bea0c0621eaee552703985146d22ca05644e79aa12fcf17e89b7b1767b0cc` |
| `fteplug_ui_imgui_x64.dll` | `f05a5ebeee71c9b8d3f1cbb1e0004648c8b1ddf4e46c1435e489086855551d90` |
| `fteplug_cod_x64.dll` | `9a66260ee3a2ee734fb7af5bc35c0035d9a0fc5a68289809ec5ebaa12b91d0fe` |
| `fteplug_box3d_x64.dll` | `48f2ba081f48cdb64546abdbaacb818772fb2e1d8a02741deb8e0e09e2197e86` |
| `fteplug_ode_x64.dll` | `e1bd98e79051f50e984368e47a6a807f3f06e13a6def9b9faa465c125c3a224b` |
| `qwprogs.dat` | `c868d9289e715133c4b4b15394fdc656a972e1f40a046d08b82f0273d350ac34` |
| `csprogs.dat` | `c9568517aade358894b88b95add53e2f7e6eb83b70b17a2a1ba7fb7f416755db` |
| `menu.dat` | `faac899b3c12658a3939559c9bd1a00c493124b263effd8857449cf30fc54764` |

The installed primary client connected to the installed secondary dedicated
server on an owned27591 fixture, not a listen server. OS module readback proved
the actual installed executables and corresponding installed HL2/ImGui DLL paths;
the old owned runtime plugins were parked, not accidentally used as a substitute.

- Prosurf's natural B4 sequence again reached2275, practice0/recording1/hopped0/
  dirty0 on the compiled product. This is a run-classification gate, not a claim
  of ranked submission from the fixture account.
- Sidistic's automatic policy read195. On a static86700-pixel floor crop, mean RGB
  changed64.78 ->79.49 with shadows0.6, ->90.27 with brightness0.1, and ->80.41
  with gamma1.2. All three controls acted while connected. Returning to neutral
  restored the crop exactly (MAE0). Screenshots inspected; no runtime/shader error
  was found in the complete client-log error scan.
- Leidenfrost's three diffuse VTFs read `NEAREST ... loaded` with global
  `GL_LINEAR_MIPMAP_LINEAR` unchanged. The first non-verbose listing omitted ALL
  flag annotations; the targeted `developer 1` re-probe supplied the acting flag
  diagnostic rather than treating a bare `loaded` line as a filtering failure.
- Both owned harness sessions stopped only their own processes and reported no
  added/removed/changed player-data files or protected top-level files.

## Fleet delivery blocker / retained work

Read-only Pi asset hashes match the measured Windows Momentum Monolith/Prosurf
BSPs and Prosurf's authored zone JSON. The Pi copy is therefore not a different
original CSS control that could close Monolith's discrepancy.

The final directory check at2026-10-15T17:15:16Z returned an empty `lobbies` array;
that is NOT evidence of an empty fleet. Subsequent read-only SSH census attempts
timed out or refused (exit255). No positive complete fleet census was obtained.
Do not force the normal `-Pi` gate, start stopped units, modify backend controls,
or infer a live P728 rollout from the Windows receipt. Restore directory/SSH
availability, then use the clean worktree's guarded `build.ps1 -Pi` and verify
all destination hashes, actual restarts and fresh live-client behavior.

Remaining: Monolith's actual fix (matching original CSS/KSF trigger control needed),
owner shade/display/fast-surf acceptance, and guarded NanoPi delivery. Keep the
owned root/controls/evidence retained for these explicit unresolved gates; no
owned game/build process remains running. Built, committed, published, Windows-
installed and fleet-verified remain separate states.
