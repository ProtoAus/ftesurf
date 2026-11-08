# P1422 -- the sprite sky test traces per 60th of a second, and only sprites in view (8 Nov 2026)

Found by the 0.1%-low survey (BACKLOG "0.1%-low survey"): surf_fairy was the slowest map, 209 fps average. Root
C:\FTESurf-worktrees\lows2-20261107-opus (artifacts/run_twopass.py, run_cvarab.py, run_skyturn.py, twopass/).

- r_budget 3 + r_budget_csqc 1 on fairy's board replay: CPU-bound, CSQC 2.1-4.0 ms of a 3.7-6.9 ms frame, cl_sprites
  1.1-2.8 ms of it: Sprite_SkyTest 0.67-1.59, Sprite_Glare 0.29-1.16. surf_jumble the same shape (1.0 ms).
- Sprite_SkyTick spent vbsp_sprite_skyrays (64) rays every frame; at surf speed every one of fairy's 460 sprites
  is due every frame (the eye passes its 16-unit retest), so 14,000 traces a second at 220 fps and 3,840 at 60.
  Same replay, cvars only: skyrays 64 222/229 fps, 16 289, 0 338; glare off as well 400.
- Change: rays per 60th of a second, never more a frame than before (60 fps and slower unchanged). A tested sprite
  that cannot reach the screen spends none: the cone through the corners of the drawn view (unproject; VF_FOV reads
  0 under the approximate fov) times 1.25, with the sphere test allowing for the cone's slope; a glow by angle, its
  margin the map's largest glow quad. Untested sprites and beams are always tested. vbsp_sprite_skycull 0 = before.
  Sprite_Glare's view cull now uses the same cone: its square-from-`fov` cone missed the edges of a 21:9 screen
  under scr_fov_mode 4 and of fov modes 1 and 3.
- Result, fairy, 30 s, old and new csprogs in successive sessions: 226 fps (1% 89, 0.1% 68) -> 300 (102, 79); other
  sessions 222/229 against 303/303. The per-second budget buys the average; the cull the lows (cull off: 306, 0.1% 46,
  as a teleport's 4x burst re-traces everything).
- Check (vbsp_sprite_debug prints the sprites within 30 degrees of the view axis: behind the sky, stale, contradicted
  by a fresh trace now): settled at four fairy vantages, 0 contradicted with the cull on and off. After a teleport
  and a 180-degree turn with the cull on, 178 of 195 were stale and 3 contradicted at once, 0 of either 30 ms later;
  with it off, none. A turn without a teleport gets no burst: about 4x slower to settle (review 2's estimate, ~50 ms
  for 200 sprites). The old code at 60 fps let every verdict be up to ~120 ms old.
- Reviews: round 1 (a census that could not fail, the cone from `fov` on wide screens, glows, the cone's slope, the
  stale window after a turn -- measured, kept), round 2 (the glow margin under the largest glows; comments) fixed.
- LIVE 8 Nov: 12 lobbies + both installs, qw e1190bdf, cs 9d48016d (tasrevd codes.txt, backup .pre1422), menu 8904d61a;
  csprogsvers seeded in both installs (df4654af). artifacts/delivery-p1422 (its protected-file check stopped after
  the copy on a peer's cfg/test/p1424keys.cfg written mid-delivery; postflight.json says so).
