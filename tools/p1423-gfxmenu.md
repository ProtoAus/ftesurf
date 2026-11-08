# P1423: gfx_menu Movers and Mover light rows; every row shows (n/m), fastest first (8 Nov 2026, ftesurf-3a)

Lex: "I want people to be able to disable [movers'] rendering for speed increase, and maybe disable lighting
updates? ... display the option you are on and how many there are, like Water: Full Refractive (5/5) ... the
first being the lowest setting / fastest, where the last setting is like full on."

## Change (QC client only)

- Row 34 Movers = `vbsp_movers` (registered archived, default 1). 0: the predraws of the movers csprogs poses
  (cl_trk.qc trains + riders, cl_spin.qc non-solid rotator/slider chains) return before posing, so they are
  neither posed, lit nor drawn. `gfx_movers_off` is read once a frame in CSQC_UpdateView. Solid movers are the
  server's and always draw. Hiding then showing again is safe: poses are a function of the clock (Trk_Pose,
  Sp_Place; Sp_Place's 60 s re-anchor is an identity). Inert reason "none near you": these are sent by PVS, so
  with none present there is nothing to save.
- Row 35 Mover light = `r_modellight_moverate` (P1398): 1/s (default), 4/s, every frame. Inert "needs update" on
  engines without the cvar (cvar_description empty; released 0.1.41 predates P1398).
- Every row draws "(i/n)" after its value; `gfx_menu status` prints it too. Value lists run fastest -> fullest,
  costs from the plugin's own descriptions: Water Dithered, Flat sheet, Budget, Screen-space, Cheap reflect,
  Full reflect; Glass Dithered, Translucent, Refracting; Prop distance 4k..Unlimited; Tool brushes Hidden, Shown;
  Reflection AA Off, 2x, 4x, As screen. Values are unchanged, so saved settings read the same.
- Page 6 is "Display and movers"; the box is 186 wide (was 168) for the position column.

## Measured (tools: task root artifacts/p1423arm.py; hosted game, C:\FTESurf exe 5798b897, csprogs from the build)

surf_centipedes at -730 74 -14545 (the skull swarm in view), r_frametime avg over 6 s, legs alternated:

| setting | avg ms |
|---|---|
| Movers on / off (run 1) | 2.19, 2.34 / 2.06, 1.95 |
| Movers on / off (run 2) | 2.39 / 2.07 |
| Mover light every frame / 1/s (run 1) | 5.57, 5.53 / 2.22, 2.22 |
| Mover light 0.25/s / 1/s / 4/s (run 2) | 2.36, 2.43 / 2.36, 2.40 / 2.53, 2.47 |

Movers off took "World: walk, entities, lightmaps" 0.18 -> 0.02 ms and GPU models 0.19 -> 0.11; the swarm is gone
from the screenshot. Below 1/s the light rate saves nothing, so the row starts at 1/s ("disable lighting updates"
would buy nothing over the default). surf_forbidden_tomb4 at a view with no client movers: on/off equal (1.13-1.18,
one 1.36 outlier on an off leg), the row read "inert" there -- the control.

Menu screenshots (pages 1, 3, 6) checked by eye: values and "(6/6)" columns line up, no overlap with labels.

Build: fteqcc 73f9a1a4 (P1412), 0 warnings x3.

Review (one round, code only, one reviewer): no defect. Noted: a hand-typed rate below 0.5 reads "Every frame"
(Gfx_Index shows the nearest value; hl2_propdist 1000 reads "Unlimited" the same way) -- left as is.

## Delivery

LIVE 8 Nov ~19:50 local: 12 lobbies (build.ps1 -Pi from main 0acd8d76; one occupied lobby warned) qw e1190bdf
(unchanged) + cs 0f0b5ae6, 0 QC errors in server1-12.log; codes.txt 98 -> 99 (.pre1423); both installs' csprogs
0f0b5ae6 (.prev 1de415d0), csprogsvers e6683f8a seeded in both. Players' own games get it with release 0.1.42.
