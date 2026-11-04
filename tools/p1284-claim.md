# P1284 claim

ftesurf-2b, 20261104T0517Z, Lex (4 Nov, frame pacing): a new lightstyle slot gets the colour key of its white colours (gl_rlight.c R_BumpLightstyles left it 0), so world lightmaps built at load are not all rebuilt, unchanged, the first time each surface comes into view once the server sends style 0 (surf_monolith: 2,548 surfaces in one frame, 34 ms).
State: done. Engine tag patch-1284 (98d1e240f), main 307846c39; both installs exe 9eb7aed8 (4 Nov 08:57Z); rides the next release.
