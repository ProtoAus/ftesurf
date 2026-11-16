# Patch 1585 claim (ftesurf-46, 16 Nov 2026)

Engine + csprogs: the light glares' visibility (Sprite_Glare) from GPU occlusion queries -- a proxy quad per glare
drawn against the scene's depth after the opaque pass, read back without stalling -- instead of round-robin
tracelines, as Source does (glow_overlay.cpp). Unprofiled A/B on the live exe (artifacts/glareab): glare rays off
lifts surf_fairy 263/144/119 -> 300/160/136 fps (avg/1%/0.1%) and surf_jumble 344/216/170 -> 443/280/204. The
traceline path stays for engines without the builtin. Root C:\FTESurf-worktrees\lows4-20261116-46.
