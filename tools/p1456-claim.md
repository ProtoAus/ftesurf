# P1456 claim (ftesurf-1d, 9 Nov 2026)

Glare traces skip glows the draw loop cannot draw (behind the sky, one-sided facing away, outside the distance fade): cl_sprites.qc Sprite_Glare. surf_fairy: glare is ~0.5 ms a frame and its 8-9 ms bursts (40 rays at 300 fps).

PARKED 9 Nov (ftesurf-1d): no frame-time gain (budget saturated); origin branch p1456-glarefade. See BACKLOG.

TIME CAP TRIED AND PARKED 10 Nov (ftesurf-1d): origin branch p1456-glarefade (time cap + review fix + record);
no measurable change in fairy's lows over 4 runs against 6 (BACKLOG). Not deployed.

NOTE 10 Nov: Sprite_GlowDrawable (branch only) copies the glow draw loop's distance ramp; P1458 (ftesurf-49) changes
that ramp (MaxDist<MinDist = always on). A revival must copy the new rule.
