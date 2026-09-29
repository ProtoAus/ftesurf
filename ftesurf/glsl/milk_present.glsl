!!ver 130 150
!!samps src=0

// Patch 467 -- milk_out to the screen, every display frame.  The sim runs at a
// fixed rate, so this is the only per-frame cost: one bilinear tap, a
// parallax nudge from the latest mouse position (M_EXTRA.xy, fresher than the
// sim), and screen-resolution dither so the 8-bit output never bands.

#include "sys/defs.h"
#include "glsl/milk_common.h"

varying vec2 tc;

#ifdef VERTEX_SHADER
void main(void)
{
	tc = v_texcoord;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
void main(void)
{
	vec2 uv = (tc - 0.5) * 0.97 + 0.5 + M_EXTRA.xy;
	vec3 c = texture2D(s_src, uv).rgb;
	c += (hash12(gl_FragCoord.xy + fract(M_TIME.x * 7.0) * 211.0) - 0.5) * (1.5 / 255.0);
	gl_FragColor = vec4(c, 1.0);
}
#endif
