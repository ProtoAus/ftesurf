# P943 — matched Source viewmodel lighting exploration

No native/shader/global-brightness fix is claimed. This continues P941's open
question rather than stopping at weapon delivery. Human residual-look acceptance
is still pending; do not infer a uniform darkness bug from unmatched viewpoints.

## Provenance and acting controls

Owner current reference: cstrike/screenshots/surf_axiom0001.tga, converted ONLY
under owned artifacts as p943-owner-css.png. cl_showpos reports(-2752,0,-31.97),
angles(.45,.08,0),1920x1200. Earlier supplied FTE photo was a different camera.
Both the user's renamed surf_axiom_css and installed CSS original are EXACT BSP
SHA2562e08b68bedaf41537970dcb58c3bc41d8130dfe53274a90fbd211618b1921e61.
BSP embeds322VTFs under materials/maps/surf_axiom, not the renamed namespace.
CSS knife/hands VMTs use VertexLitGeneric/env_cubemap, not Phong.

Same owned native/QC/assets rig, real dedicated27579, public/lobby disabled;
normal gravity800, worldFOV90/viewmodelFOV75, cl_idlefps0/cl_maxfps100,
cl_nopred1 for this STATIC render probe, game SFX0, early idle0/ready1.
Defaults observed: gamma1,vid_srgb0,r_cubelight1,hl2_lt_scale255,
hl2_favour_ldr0 (HDR). Not a movement/recording/prediction/evidence grade.

Original-name final native view(-2751.94,.0625,-31.6875), angles(.4725,.0767,0).
Renamed final native same view, angles(.3666,.3000,0). Both actually drew knife
idle0/ready1, similar early phase, same BSP and approximately the CSS camera.
World landmarks align; small aim/phase/subunit differences remain, so NOT pixel
parity. Original160cubes/0missing; renamed160/160missing. This resource difference
ACTED, but hand appearance did NOT materially change at this spot. Renamed-cube
loss therefore does NOT establish the reported hand-darkness cause. Do not grow
an unrelated map-renaming patch or global brightness multiplier from it.

Visual inspection of matched CSS/FTE hands does not show a blanket darker model.
Some hand colour/blade reflection differences remain; no statistical colour or
all-map parity claim. Model/cube sites for a further qualified case remain
engine/gl/gl_alias.c:R_CalcModelLighting and plugins/hl2/mat_vmt.c.

## HDR configuration follow-up, also not a guessed repair

Read ONLY selected archived CSS rendering keys, not credentials/profile contents:
mat_hdr_level0, mat_monitorgamma2.110000, mat_colorcorrection1. These are current
saved settings, NOT proof of screenshot-time console overrides. FTE defaults to
HDR. Additional original-name native arm selected hl2_favour_ldr1 BEFORE load;
readback1, real nonzero actor, knifeidle0/ready1, same near camera. Actual image
was inspected, but no clear hand-colour repair was demonstrated. Small aim
difference remains; startup cube diagnostic reported12missing in that arm, not
zero. Do not claim that LDR fixes this or change the owner's/default profile.
No more optional harness expansion is required before the owner judges the pair.

## Failed/misinterpreted controls, retained not relabeled

- Initially assumed cl_showpos Z meant feet, added64, and raised the camera:
  WRONG. Native rendered-world landmarks establish the useful reference near
  VF_ORIGIN Z-31.97, not32.03. First original image actually fell into that view;
  later corrected explicit body target-96 reproduces it. No assumed hull offset
  is accepted as camera evidence.
- Zero-gravity exploration held server body but client prediction still dropped;
  prederr images are NOT physics or final comparison passes. Final static arm
  normal gravity and cl_nopred1 replaces it, not a product workaround.
- Blind map-change wait returned body0, then cfg commands were lost before spawn:
  weapon0/ready0 image is INVALID. Stopped that approach, reused existing fresh
  startup path. Its late-body check also expired before actual CSS asset spawn;
  observed SAME actor nonzero placement within bounded60s, then sent cfg.
  Do not restart into numbered rigs or call an echo alone readiness.

## Evidence, restoration and small owner question

Owned root C:/FTESurf-worktrees/source-polish-20261022T0746Z:
- artifacts/lighting-matched-pair.png: CSS reference LEFT, FTE original-name RIGHT.
- Original: controls/p920-ui/ftesurf/screenshots/
  bridge_lighting_20261023T205242_001.png.
- Renamed: same directory/bridge_lighting_20261023T205609_001.png.
- LDR: same directory/bridge_lighting_20261023T212522_001.png.
- Exact cfg, startup/camera logs, predictions and restored-ownership manifests
  retained under controls/p920-ui and artifacts/lighting*.

All these owned actors stopped. Two-name fixture and additional original-only
LDR copy hash-checked/unlinked after use; original absence/Momentum priority
restored. Steam and owner's CSS BSP hashes unchanged. No player data deletion,
owner process/config/native change or canonical/live map replacement.

Owner asked: does the saved matched pair now look close enough? If not, identify
the specific remaining tint/shadow, with actual CSS runtime rendering settings,
rather than applying a global brightness change to different map lighting.
