# P1440: Source model bodyparts and prop SetAnimation (9 Nov 2026, ftesurf-3a)

Lex, playing bhop_crash_egypt: "the crates on the map display all of their 'animation' up front, and after you
'break' them, soon after they disappear" (console: SetAnimation not implemented). crate_generic.mdl (102 crates)
has one bodypart, Box, of 16 models: the box, 14 shatter frames, a blank. The map breaks a crate by firing
SetBodyGroup 1..14 over 0.43 s, then Kill. fteplug_hl2 tagged every mesh geomset 0 / id 0, so all 16 drew at once.

## Library (2204 maps)

- SetBodyGroup keys on 66k entities (46 non-zero); the SetBodyGroup input 1,708 times on 3 maps.
- SetAnimation 447 times on 45 maps (bhop_crash_egypt's 20 nitro crates on logic_timers), SetDefaultAnimation 2.
- Every Source model with a multi-model bodypart drew all its alternatives stacked; now it draws the body's.

## Change

- Engine (tag patch-1440 = ae448df27, on P1442): two arrays appended to model_t (geombase, geomcount); GL_ChooseSkin
  draws a geomset surface while (entity body / base) % count is its id -- Source's packed m_nBody. Other formats keep
  id 0 only. The exe answers the interface "FTESurfModelTail/1440".
- hl2 plugin: a bodypart with more than one model (first 32) is a geomset, each model its id; base and the .mdl's
  count go into model_t -- only when the exe answers the marker. An older exe keeps every alternative drawn and
  gets no write past model_t (it landed in the next mod_known slot's name and load state). The prop-opacity walk
  skips alternatives a prop does not draw.
- QC: .body (the engine's networked PEXT2_BODYGROUP field) from the SetBodyGroup keyfield (any case) and input on
  props (the packed body takes the value; one bodypart, base 1, in every library case). SetAnimation plays a named
  sequence on a non-solid prop_dynamic as on a 3D-skybox prop (P1202), the same rule as DefaultAnim (P1273); the
  success line prints under developer 2 (map timers repeat it), a missing sequence under developer 1.

Left: collision is unchanged -- a prop whose collision is its render mesh still collides with hidden alternatives,
as before. Census (9 Nov, offline, the plugin's rules ported): 55 solid prop_dynamic on 13 maps (surf_happyhands3
and _css 15 each, surf_froots_ksf 7, bhop_alvo2 4, rj_beef 3, ...), all NPC models with a jointed .phy (zombies'
headcrab, antlion wings, a chicken's hat, mom_soldier's rocket); no static prop. Client prediction and the server
build the same trees and the lobby server runs engine git-8489-patch-1353 (84 commits behind), so the fix needs the
lobby server engine upgraded with it. Bodyparts past 32 and bodies over 255 (the wire's byte) draw submodel 0. A
repeated SetAnimation of the same sequence does not restart it (Source restarts a one-shot).

Follow-up (same day): csprogs train riders (P1378) and movers (P860/P1387) carry body -- ENTWIRE_TRKPROP's flag bit 2
and ENTWIRE_SPSTATE's bit 4 add the byte (clamped 0-255), so older recordings parse as written. No library prop
rides with a non-zero body today; measured by firing SetBodyGroup: surf_centipedes' skull1 riders and
bhop_lost_world_v2's carrot1 mover print the body on the client. One review (no defects; the clamp and a comment
fixed). LIVE 9 Nov ~13:10 local: lobbies qw cafb0be2 + cs e84310b0 from main 0f88c669 (nobody on, 0 QC errors),
C:\FTESurf the same, csprogsvers cd742783 seeded on the Pi and both installs, codes.txt 110 -> 111 (.pre1440b).

## Review (one reviewer, code only)

The decode, every draw pass (main, depth/shadow maps, reflections: all through GL_ChooseSkin per entity),
batch/instancing keys and body initialisation everywhere (packets, CSQC, statics, viewmodel, plugin props) were
confirmed. Fixed: the plugin/exe pairing (marker), the count from the .mdl, a compile-time check of the 32, the
opacity walk; QC comment and print level. The collision side effect was kept, as above.

## Measured (bhop_crash_egypt, runs/p1440, artifacts/p1440arm.py, private homedir, rig.lock)

Camera north of the crates at 0 1700 -230 (Lex's save spot is inside a filtered trigger_teleport, force2spawn,
that sends unnamed players to spawn -- the map names you "hi" on the way in; Source's behaviour, kept), looking at
Crate_generic1 and a stack of two. Changed pixels against the first frame:

- Test engine (gae448df27 build edf50724) + P1440 QC: the crates draw whole; SetBodyGroup 5 / 14 change the crate
  32k / 15k px (shatter frames, pieces in the air), 15 hides it (the blank), 0 brings the box back.
- Installed engine, same QC: every alternative stacked (Lex's screenshot); SetBodyGroup changes 3-6k (nothing).
- Guard: the installed P1442 exe with only the new hl2 plugin beside it loads the map, draws every alternative as
  before (2.3k px from the control frame) and SetBodyGroup changes nothing.
- SetAnimation: the map's own timers set nitro_idle on the nitro crates (frame 4).

## Delivery

LIVE 9 Nov ~12:40 local (01:40Z): 12 lobbies QC from main 35c82ca7 (build.ps1 -Pi; nobody on; warned; 0 QC errors
in server1-12.log): qw bd235ab4 (.prev 9cad7952), cs 8ab47d50 unchanged (server-side QC only; in codes.txt since
P1442). Both installs: exe edf50724 (git-8573-patch-1440-0-gae448df27; .prev 1d's P1442 7e7564ae), C:\FTEQuake
fteqwsv64 0388bbe7 (.prev d99cbbcb), fteplug_hl2 8d47ecb8 (.prev 3b085f6c), ui_imgui 6e968603, C:\FTEQuake's
cod/box3d/ode rebuilt (build.ps1's list); qwprogs bd235ab4 in both. The Pi's server engine and plugin are unchanged
(body is networked by the existing PEXT2_BODYGROUP). Players see the parts with the next release.
