# P1456 claim (ftesurf-1d, 9 Nov 2026)

Glare traces skip glows the draw loop cannot draw (behind the sky, one-sided facing away, outside the distance fade): cl_sprites.qc Sprite_Glare. surf_fairy: glare is ~0.5 ms a frame and its 8-9 ms bursts (40 rays at 300 fps).
