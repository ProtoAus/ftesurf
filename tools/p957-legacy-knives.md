# P957 — mounted Legacy knives / local finish workshop

## Scope and use

Follow-up to the separate P955 CSS delivery. Native source/tag:
`86228bf7cfeaa175f15dd665165e094780bcaf49`, annotated `patch-957`.
Product patch957; Build89 and public release0.1.30 are not bumped.

Use `butterfly`, `m9`, `knife_css`, `inspect` and `knife_menu`.
The workshop exposes Original/Fade/Web/Marble, seed, scale, rotation, Fade % and
wear, plus inspect/random seed/drop. X or Esc closes and releases its cursor.
It uses the player's installed CS:GO Source1/Legacy models, CT arms, textures
and sound scripts. Those licensed assets are NOT redistributed. The original
shader is shipped by the existing `ftesurf/glsl` release allowlist.

On a fresh UPDATED client, if Legacy content is not mounted, enter this in the
trusted console once, then select the knife again:

```
fs_load "steam:Counter-Strike Global Offensive/csgo"
```

The existing native resolver supports both the CS2 Legacy layout and standalone
`csgo legacy/csgo`. It mounts low priority and persists through its normal mount
list. CSQC cannot run a privileged mount: do not bypass that boundary. A failed
selection leaves the current knife/model setting unchanged. Classic CSS remains
available with `knife_css`. Finishes are local cosmetic approximations, not Steam
inventory, purchases, ownership claims or exact CS paint-kit reproduction.

## Implementation and verified controls

The native importer is restricted to the two exact v49 knife families and bounded
direct include groups. Named bones, supported quaternion64/fixed48 lanes,
finite/bounds/parent checks, frame/group limits and a 64MiB pose budget precede
ordinary baked matrices. Reject unsupported external frame streams. Matrix
storage uses an explicit float[12] pointer: a void* receiving [256][12] otherwise
advances whole arrays and leaves most frames uninitialized. The synthetic test
exercises actual extracted helpers and discriminates that opaque-stride bug.

- `python tools/test_hl2_weapon.py --engine <clean-native> --work-root <owned-root>`:
  native quaternion/frame and multi-frame storage controls PASS.
- Existing `src/build.ps1 -Engine -Full -Jobs 8 -NoDeploy`, pwsh7, clean tagged
  native: PASS. All three VMs0warnings; native74 inherited warning lines EXACTLY
  match the prior full-build control, with no added/removed warning line/site.
- First Full failed on absent ignored codec dependencies in the docs-only tree;
  an owned borrowed-cache junction plus existing cached tar input, then a fresh
  Full (not reuse of pre-cache objects), fixed that environment seam. Neither
  install touched. Generated VMT header differed only in its generator-path
  comment; verified all other lines equal and restored our banner-only delta.
- Compiler database regenerated with the existing m-rel-only generator:229 TUs.
  The first wrong script path and unsuitable mixed full/plugin log failed; the
  normal supported dry-run invocation succeeded. LSP is not a QC parser.
- Actual dedicated/socket actors: stable M9 and Butterfly idle/draw/inspect,
  matching mounted CT arms, earlier acting13/16 clip tables and authored callback
  events. Inspected native PNGs show both families, changed Fade amount,
  Web/Marble, pattern transforms, wear, panel and painted M9 reselection.
- Final tagged actor `bridge_legacy-pose_20261024T103530`: ready1 for both,
  actual Butterfly inspect callbacks, panel frames132/claim2048 -> closed/claim0.
- Final corrected sound/alias actor `bridge_legacy-pose_20261024T104114`:
  `knife_css` ready1; absent M9 leaves SAME CSS ready1/kind0; explicit trusted
  mount succeeds; M9 ready1. Its Source `)` sound prefix is stripped: deploy WAV
  present1/event-sounds1, inspect advances event-sounds2/callbacks3.
- The earlier cold prototype attempted CSQC fs_load and was explicitly refused;
  that FAILED result prompted the final instructional/no-mount approach. An
  earlier missing `knife_css` route and unstripped M9 sound prefix also failed;
  the final actor above supplies their positive controls, not those failures.
- Each owned actor quit0. Its sole mutable mount-list fixture was restored to
  the original exact hash after quit; no owner configuration, consent or data
  was changed. Engine log/filename times are local UTC+11, NOT UTC.

No movement, aim, player-damage policy, recorder/verifier/evidence/schema or
backend change. Pi native need not change: selection/events use existing server
interfaces; the new model import/shader requires the updated local client.
Real mouse/slider, appearance, sound and feel acceptance remain explicitly
pending in lextest.md. No exact CSS/CSGO parity or sustained-FPS claim.

## Delivery state

Implementation and isolated native qualification COMPLETE. Source publication,
inspected-commit build, BOTH Windows promotion and ordinary player-guarded Pi
CSQC promotion/readback are recorded here when complete. No new public release
was requested by the post-release edit request.
