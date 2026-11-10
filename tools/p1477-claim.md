# P1477 claim: forced water captures staggered too; r_capturerate down to 10 (ftesurf-1d, 10 Nov)

Lex (10 Nov), after testing r_capturerate 10 ("couldn't tell a difference"): stagger (P1474) only spaces the
clock's redraws; can the forced ones (past 128 units / 30 degrees) be spaced too, and can the rate go to 10 (the
engine floors it at 20)? Plan: r_viewstats counts two-capture frames by cause; a group past the camera limits but
within 1.5x of them may wait one frame while the other renders (never two frames running); floor 10. Measured on
the surf_nuclear replay at Lex's cap, 20/10 against 60, with the histogram. On top of P1475.

DELIVERED 11 Nov 20:18Z (ftesurf-18): both installs client exe 7930cc92 (tag patch-1484-1482); record in ENGINE_PATCHES.md "Patch 1477".
