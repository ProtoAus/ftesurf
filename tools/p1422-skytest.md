# P1422 -- the sprite sky test traces per 60th of a second, and only sprites in view (8 Nov 2026)

Found by the 0.1%-low survey (BACKLOG "0.1%-low survey"): surf_fairy was the slowest map, 209 fps average. Root
C:\FTESurf-worktrees\lows2-20261107-opus (artifacts/run_twopass.py, run_cvarab.py, run_skycheck.py, twopass/).

- r_budget 3 + r_budget_csqc 1 on fairy's board replay: CPU-bound, CSQC 2.1-4.0 ms of a 3.7-6.9 ms frame, cl_sprites
  1.1-2.8 ms of it: Sprite_SkyTest 0.67-1.59, Sprite_Glare 0.29-1.16. surf_jumble the same shape (1.0 ms).
- Sprite_SkyTick spent vbsp_sprite_skyrays (64) rays every frame; at surf speed every one of fairy's 460 sprites
  is due every frame (the eye passes its 16-unit retest), so 14,000 traces a second at 220 fps and 3,840 at 60.
- Same replay, cvars only: skyrays 64 222/229 fps, 16 289, 0 338; glare off as well 400.
- Change: rays per 60th of a second, never more a frame than before (60 fps and slower unchanged); a tested
  sprite out of Sprite_Glare's view cone, behind the eye or past vbsp_sprite_dist spends none. Untested sprites and
  beams always tested. vbsp_sprite_skycull 0 = trace out of view too.
- Result, fairy, 30 s arms: 303/303 fps (1% 103, 0.1% 80-83) against 222/229 (90, 72-74). Cull off: 306 (93, 46) --
  the per-second budget buys the average, the cull the lows (a teleport's 4x burst re-traces only what is seen).
- Check (vbsp_sprite_debug now prints sprites within 30 degrees of the view axis): settled at four fairy vantages,
  all of them were tested with and without the cull (46/46, 16/16, 6/6, 30/30). None of them was behind the sky
  there; the 216-vs-3 difference in the "behind the sky" total is sprites out of view. Not demonstrated: an
  on-screen sprite behind the sky (the verdict rule is unchanged; only which sprites are traced when changed).
