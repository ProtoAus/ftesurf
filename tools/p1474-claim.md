# P1474 claim: staggered water/glass captures (ftesurf-1d, 10 Nov)

Lex (10 Nov): "Doing over multiple frames?" for water captures. A capture frame redraws the plane's reflection AND
refraction together (r_capturerate's keep is all-or-nothing, one m_capturefix), ~3.2-4 ms on a 3.3 ms frame at a 300
cap, and those frames set the 1%/0.1% lows. Plan: keep reflection and refraction(+depth) with their own render time and
camera matrix, so a frame that finds both due renders one and keeps the other one more frame; the water/lmreflect
shaders take a second capture-fix matrix for the reflection (engine gl_backend.c, gl_shader.c, shader.h,
gl_vidcommon.c; hl2 plugin glsl/vmt/water.glsl, lmreflect.glsl, mat_vmt_progs.h). Measured against r_capturerate 30,
>=3 runs a side.
