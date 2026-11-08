# P1439 -- env_screenoverlay and env_shooter

ftesurf-b8, 9 Nov 2026 (entgap-20261108, the last of the look-only group). Root
C:\FTESurf-worktrees\xhair-20261108-b8 (tools/armsg.sh, ovl1.cfg, sht1.cfg, rigs/bm-ov1-new, bm-sh1-new).

## What

- env_screenoverlay (7 maps; StartOverlays / StopOverlays / SwitchOverlay) drew nothing. src/client/cl_overlay.qc
  runs c_env_screenoverlay.cpp: OverlayName1.. for OverlayTime1.. seconds each (-1 holds), the LAST overlay staying
  up when the run ends (Source's StopOverlays clears only on an active-to-inactive update, which only the
  StopOverlays input sends), SwitchOverlay N, StartOverlays deactivating the map's other overlays without clearing
  the view, nothing at all for one with no OverlayName1. Drawn full screen over the world and under the HUD
  (cl_main.qc, under env_fade); refract / screenspace / post materials are refused (FTE would paste their texture
  over the screen). Everyone sees it (FL_EDICT_ALWAYS), as in Source multiplayer. vbsp_overlays_screen 0 hides it.
- env_shooter (8 maps, 20; Shoot) shot nothing. src/client/cl_shooter.qc runs CGibShooter::ShootThink -- a gib
  every Delay (one a tick at 0) until m_iGibs, scattered by m_flVariance, at m_flVelocity, then re-armed (SF 1) or
  gone -- and flies the gibs: shootmodel at its skin, scale and render colour, from gibangles, spinning as point or
  physics gibs do, under gravity x gibgravityscale, FLY_BOUNCE at friction 0.55, resting on floors, fading out a
  second after m_flGibLife. Gibs are debris in Source (no player collision), so they live on the client.
  vbsp_shooters 0 stops them.
- Wire: ENTWIRE_FXSTATE2 classes FX_CLS_OVERLAY 9 (on = 0 stopped, else 128 if active + overlay + 1; StartOverlays
  the event; SV_OvInput) and FX_CLS_SHOOTER 10 (Shoot the event). An older client's Fx_Net matches neither.

## Measured (client C:\FTEQuake\fteqw64.exe c61f874b; 0 QC errors)

- surf_ab "oilsplat" (browser/oilsplat, OverlayTime1 2): StartOverlays puts the oil splat over the screen (q1->q2
  67629 px); 2.6 s later, past its 2 s, it is still up (q2->q3 0 px -- Source's persisting last overlay);
  StopOverlays clears it (q4 back to the start frame bar 337 px). The client logs "overlay: 0 shows 0 ... until
  50.62 (now 48.62)".
- surf_era fumo_shooter5 (models/skar/fumo_cirno.mdl, 200 gibs every 0.5 s, pitch 90): after Shoot the plushes
  fall past the camera, one spinning in the air and one lower down, none before (rigs/bm-sh1-new q1, q2); "shooters:
  8 of 8 env_shooter kept".

- Review-1 build (build-nodeploy-b598853c): surf_ab again shown, held past its time, cleared (67629 / 0 / 428 px);
  mg_remsopor_encore overlay1 (debug/yuv, held -1): "overlay: debug/yuv not drawn", the screen unchanged but for
  the map's swaying tree. The shooter's re-run (surf_era, for the review's gib physics) was stopped by Claude
  Code's low-memory guard and is NOT measured.

## Review

One round. Fixed: debug/yuv (mg_remsopor_encore, held -1) would have painted the screen white -- a YUV shader has
no base texture and FTE draws it with the white image -- so only picture shaders with a $basetexture are shown;
a refused step stopped the run with the previous overlay held (now it shows nothing for its time and the run
goes on); SwitchOverlay to an empty slot is ignored as in Source; the run advanced only while no menu was up
(Ov_Think now runs every frame); times are SendPropFloat's 11 bits over -1..63; a cvar toggle reloaded both and
revived spent shooters (a same-map reload now keeps them); gibs without SF 4 (strict remove) stay as in Source
and strict ones go at once; a gib with no velocity hung in the air (a rest flag now; gravity until it rests);
bounces keep elasticity 0.25 (not friction 0.55) and rest under 30 u/s, laid flat on floors; m_flGibScale is not
applied to model gibs; renderamt counts only with a render mode. Admitted in the headers: one overlay run at a
time; StartOverlays on a nameless overlay still deactivates the others; a spent one-shot shooter is spent on each
client separately.
