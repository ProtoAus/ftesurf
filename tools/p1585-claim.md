# Patch 1585 claim (ftesurf-46, 16 Nov 2026)

Engine + csprogs: the light glares' visibility (Sprite_Glare) from GPU occlusion queries -- a proxy quad per glare
drawn against the scene's depth after the opaque pass, read back without stalling -- instead of round-robin
tracelines, as Source does (glow_overlay.cpp). Unprofiled A/B on the live exe (artifacts/glareab): glare rays off
lifts surf_fairy 263/144/119 -> 300/160/136 fps (avg/1%/0.1%) and surf_jumble 344/216/170 -> 443/280/204. The
traceline path stays for engines without the builtin. Root C:\FTESurf-worktrees\lows4-20261116-46.

PARKED 16 Nov 2026 (ftesurf-46): engine branch p1585-glarequery (engocc, on a75914b9d; needs a rebase onto patch-1588 --
pr_csqc.c), QC branch lows4-p1585. Correct and reviewed three rounds, but only the GPU-decides mode (vbsp_glare_gpu 2)
is faster (fairy/jumble 0.1% +14-18% unprofiled), and it has three open should-fixes: the depth-hacked viewmodel
covers proxies (a lamp behind the knife fades), a stale SKY_CLEAR verdict lets the GPU light a glare through the sky
after a teleport, and far proxies alternate between "too small" (rays) and GPU answers (flicker where lamp models
disagree). Mode 1 (same look as rays) gains nothing measurable. Fixes and numbers: BACKLOG "0.1%-low round 4".
