# P955 — CSS weapon follow-up

## Scope and source

QC-only follow-up to the owner's post-0.1.30 testing. Isolated base:
`e2e4539431d149cdcbeefc69ed8e57677274ae65`. Native patch book:
`ce58677fcc31463cd44154542af5914f8668bffd`. ENGINE.txt patch955;
engine pin/tag953, Build89 and public release0.1.30 remain unchanged.

Included: zero single-Glock camera punch (burst preserved); Scout40/15/off
render-only scope with mounted CSS arc/zoom sound and shot/bolt auto-rezoom;
no save-hold re-equip; visible noclip model; bare drop unarms; mounted CSS muzzle
texture on original geometry; CSS damage1..3 hard-fall samples.

NOT included: the separate CS:GO Legacy Butterfly/M9/inspect/finish-workshop
prototype. Its hand rendering still fails visual acceptance. It is retained,
not declared complete or cancelled; see ROADMAP.md. No Valve data redistributed.
No native, movement/input/evidence-format/schema/backend change.

## Predictions and acting controls (24 Oct 2026 UTC)

Existing src/build.ps1 -Jobs8 -NoDeploy, pwsh7: all three VMs0warnings.
The transport source build is p955-css-download-build.log. A final scope-off
control then caught an over-narrow metadata-version check: it rejected the real
CSS44 models and reported muzzle attachment0. Actual installed VPK inspection
confirmed ALL three guns are44, not48. The reader now accepts the engine's
Source44..49 prefix range. Final p955-css-attachment-version-build.log has
three VMs0warnings; output build-nodeploy-9f7a52f7b6a34c74950634cdc2e577e9.
A new real socket actor reported attachment2 for ALL three actual CSS44 guns;
p955_final_flash.png was inspected and shows the corrected single-shot flash. LSP has no QC parser; actual
compiler/runtime results are the authority. Native actors use qualified installed
953 images, NOT the uncommitted experimental plugin. Client SHA256
8b29f927a925c3fff96cc1e732e68425c9bd8e1b648c90e742b444eccf1e83b5;
HL2 a73f719b12c9b663a4628ceea027493e8f4f20ba109c924d4d33c696341a385a;
dedicated e22f979863b2740d417974f1bf6eadf8919cb6013911270c17dce61dcd1508f8.

Real dedicated socket on surf_axiom; cfg_save_auto0/run_resume0,
cl_idlefps0/cl_maxfps100/r_viewmodel_fov75, synthetic isolated data only.

| Falsifier | Actual result |
|---|---|
| Single Glock must really shoot with zero punch; burst must still act/kick | Single shots0->1, kick/velocity0. Burst mode1, shots advance, pending2, kick-0.445368 at sampled frame. Input/render base angles remain0. |
| Noclip must not unequip/hide | movetype8, type8/ready1, draw-start1; p955_noclip.png inspected, gun visible. |
| Save hold/release must not start draw again | sl_save then same-packet sl_load/sl_hold, holdoff: movetype0->3, same type8/ready1 and draw-start1. Existing clip stayed idle, not draw. |
| Scope levels must change the drawn view; shot must unzoom/rezoom | zoom1 then2, scoped1; p955_scope40.png/p955_scope15.png inspected. Final third secondary returned zoom0/scoped0 and p955_scope_off.png restored full view and Scout. Shot12, zoom0/rezoom2, then zoom2/rezoom0; Weapon_Scout.Bolt callback acted. |
| Muzzle must produce actual pixels, not just a counter | p955_flash_fast1/2 and p955_usp_flash PNGs inspected: brief flame at muzzle. Early screenshots waited15frames and MISSED the40ms cue; preserved, not counted as a rendering failure/pass. Three-frame capture caught it. |
| Silenced USP must not flash despite shooting | shots13->14, flashes stayed13, mode1; normal USP shot/attach cues acted. |
| CSS fall choice must resolve to real mounted content | css-fall1, gameaudio_info fall increased calls and selected player/damage3.wav. This proves resolver/play request, NOT human listening acceptance or actual fall timing. |
| Bare drop must traverse client and server, not disconnect | First candidate said Unknown command and retained Glock: FAILED. Added CSQC route. Final actor: client type0/ready0, server type0/event0/pending0, health100 and connection retained. |
| A mesh-absent client must receive the new asset | Fresh minimal client had neither CSQC nor muzzle mesh. Normal server precache/download produced downloads/models/ftesurf/muzzle.md3,428bytes, exact source bytes/hash. First-run consent blocked that actor's visual/weapon check; NOT bypassed/accepted. Existing isolated actor supplies the pixel proof. |

Logs: bridge_source-p955_20261024T064805_cl/sv.log (main controls),
bridge_source-p955_20261024T070309_cl/sv.log (final bare drop / download server),
bridge_source-p955-cold_20261024T070507_cl.log (transport, visual blocked),
bridge_source-p955_20261024T071938_cl/sv.log (final attachment-version correction).
These are local evidence, not public raw player/profile output.

## Asset/reader boundary

Original428-byte MD3 quad, reproducible exactly with tools/build_muzzle_quad.py:
SHA25685b19acbb244587ad0f34211fddeb5daf8454595898b6fb3ef97877d81939a30.
The actual CSS attachment is read from bounded Source44..49 MDL metadata using existing
QC binary IO; finite local coordinates, bone/count/offset/file bounds are
checked. No fake bone or pose-stride mutation. A rejected virtual-bone experiment
was removed before this patch: it deformed the CSS Glock. No rejected code ships.

Normal server precache supplies the original mesh to old clients. Release
allowlist explicitly carries it. The flash's VTF and scope/sound assets stay in
the player's licensed, locally mounted CSS install. No licensed data copied to Git.

## Delivery state

Verified source, not yet deployed at this commit. A subsequent receipt update
must record clean committed rebuild, BOTH Windows destinations and the ordinary
player-guarded Pi progs/asset promotion, hashes and live proof. Do not infer
installed state from a build/commit. No new release requested or performed.

Owner-only sound/look/feel acceptance remains PENDING in lextest.md. There is
no exact CSS parity, all-asset completeness or sustained-FPS claim.
