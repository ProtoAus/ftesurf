# P1427 claim -- ftesurf-1d (opus, lows2), 8 Nov 2026

Lex: worst maps, automatic glare/sprite cost. cl_sprites.qc: sprites outside the eye's PVS (checkpvs, round-robin)
are not drawn, glare-traced or sky-tested. surf_fairy/tensor2: up to ~90% of in-view sprites are outside the PVS.
