!!ver 130 150
!!samps spec=0

// Patch 467 -- the MUSIC screen's analyser: snd_visimage's row 0 as 48 bars
// with peak-hold ticks.  drawpic's rgb (v_colour) is the station colour.

#include "sys/defs.h"

varying vec2 tc;
varying vec4 vc;

#ifdef VERTEX_SHADER
void main(void)
{
	tc = v_texcoord;
	vc = v_colour;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
void main(void)
{
	const float bands = 48.0;
	float b = floor(tc.x * bands);
	float u = 0.02 + (b + 0.5) / bands * 0.96;
	vec4 s = texture2D(s_spec, vec2(u, 0.25));
	float y = 1.0 - tc.y;
	float gap = step(0.2, fract(tc.x * bands));
	float bar = step(y, s.r) * gap;
	float peak = (1.0 - step(0.025, abs(y - s.g))) * gap * step(0.03, s.g);   // no tick for a silent band
	vec3 col = vc.rgb * (0.35 + 0.65 * y) * bar + vec3(0.95) * peak;
	gl_FragColor = vec4(col, max(bar * (0.5 + 0.5 * y), peak) * vc.a);
}
#endif
