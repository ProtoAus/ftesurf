# P1409 -- r_blendsort 2 keeps static blended faces' sorting centres (8 Nov 2026)

Found by Lex's 0.1%-low survey (BACKLOG "0.1%-low survey"): surf_bossfight 514 fps average with 2,861 stutters in
35 s of its top board replay. Root C:\FTESurf-worktrees\lows2-20261107-opus (artifacts/run_prof_replay.py,
run_replay_ab.py, run_toggleshots.py).

- Same replay stretch, r_blendsort 2 (Lex's) against 1: 281-288 against 541-602 fps.
- CPU sample: GLBE_SubmitBlendedFaces 36% of the main thread (self). Temporary stage timers (not committed):
  ~400 blended faces a frame; gather 2.1 ms of which GLBE_BlendAreaDepth 2.09, sort 0.05, plane proof 0.006,
  draw 0.05-0.8. The area centre sums every triangle of each dense face every frame.
- Change: on a Source map, a world or brush-entity face's model-space centre is cached (mesh pointer + xyz/index
  arrays + counts, dropped by a new map and by Surf_Clear) and only transformed per frame. r_blendcache 0 = before.
- Result (exact build): 276 -> 493 fps (playing, 15 s); revised build 281 -> 470/498. Paused frame at r_blendcache
  0/1/0 on four bossfight views: 0 pixels differ.
- A first idea, merging consecutive same-batch faces into one draw, measured ~4% and review 1 showed it changes the
  order of multi-pass materials (pass loop outside the mesh loop): removed. An A/B run first measured the old exe
  (run_replay_ab.py did not copy the new build into the fixture) -- caught by a missing timer print.
- Reviews: round 1 (the merge, scene-cache staleness on Quake worlds, Surf_Clear purges) fixed; round 2 nothing.
- Installed 8 Nov: both installs exe 684cf4a4 / fteqwsv64 6380a6b5 (artifacts/delivery-p1409); engine main 105ce85a0.
