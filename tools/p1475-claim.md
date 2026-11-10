# P1475 claim: parallax for reused water/glass captures (ftesurf-1d, 10 Nov)

Lex (10 Nov): at lower capture rates the reflection "falls off the water edges" while moving; "could a parallax
capture adjustment work? ... doesn't need to be perfect". A kept capture (P1245/P1281/P1474) is turned with the
camera but not moved. Plan: shift each sample by the eye's travel since that capture, scaled by how far beyond the
surface the content is -- the refraction from its existing depth target, the reflection from a new reflection depth
target (resolved under r_reflectmultisample), one parallax step in vmt/water and vmt/lmreflect. Scored by a reused
capture against a fresh one after a slide and a turn; then r_capturerate 30 against 60. On top of P1474.
