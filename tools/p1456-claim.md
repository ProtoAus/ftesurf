# P1456 glare and sky rays capped by time (ftesurf-1d, 9 Nov 2026)

cl_sprites.qc: Sprite_SkyTick and Sprite_Glare each stop for the frame once gettime(1) has moved
`vbsp_sprite_tracems` (default 2; 0 off) since that loop began, floored at two steps of that float clock.
Sprite_Glare also skips glows the glow draw loop would not draw (Sprite_GlowDrawable: behind the sky, one-sided
from behind, outside the distance ramp) and drops their answer to -1, as P1373's jump reset does.

Why: surf_fairy (460 glows) spends ~2 ms a frame in csqc against 0.78 on surf_nuclear; the worst frames (8-9 ms of
csqc) are Sprite_Glare + Sprite_SkyTest firing per-frame ray budgets where a ray costs 100-200 us (the QC profile
counts builtins in the caller; only renderscene and entity setup are excluded). Cvars set after csprogs loads and
read back (launch-cfg vbsp_* are "Unknown command"): glows off 273/140/122 (avg/1%/0.1%), vbsp_glare 0 259/117/85,
vbsp_glare_traces 8 251/112/89 -- but 8 rays doubles the census sweep (glow answers ~2x staler), the trade Lex
chose against before (40 rays, interval 0.025).

The undrawable skip alone measured nothing (2.13 -> 2.09 ms csqc): the 40-ray budget is saturated, so saved rays go
to other glows. It stays for freshness only.

Measured (capped 300, framepacing 5, exe P1454, fairy replay; control = main 5f52a7fb built with the same compiler):
- control 1% 90-94, 0.1% 71-76 (five runs); P1456 (shared cap) 1% 99-102, 0.1% 73-88 (two runs); in its worst
  frames glare + sky fell from 6-9 ms to 2-3 ms and the frames are led by transparent draws (4-5.6 ms).
- census: cap hits rise through the run; sweep median 8 frames either way; 0 QC errors on exe P1454 and on the
  oldest released engine in the rig (bin_rel141, patch-1348).
- Review 1 (wrong picture: a skipped glow kept its answer; starvation: the sky test spent the shared cap after
  teleports; burst credit unclamped; eager && per visit) fixed in the third commit; review 2 clean (notes: a dropped
  glow comes back dark for up to a sweep; a lamp also out of view keeps its answer, as before).
