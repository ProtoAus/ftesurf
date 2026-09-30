!!ver 130 150
!!samps spec=0

// Kick streaks (src/milk_sys.qc, Milk_WavesDraw): MilkDrop's waves, ribbons
// drawn INTO the feedback frame so the warp carries each one off as a trail.
// The line is pushed across its ribbon by the mix's waveform -- milk_spec's
// second row, oldest sample at u 0.
// Per vertex: texcoord.x the waveform read, its integer part the gain in
// quarters; .y across the ribbon, in line widths; colour rgb the light, a the
// swing in line widths.

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
	float g = floor(tc.x) * 0.25;
	float w = texture2D(s_spec, vec2(fract(tc.x), 0.75)).r * 2.0 - 1.0;
	float d = tc.y - vc.a * clamp(w * g, -1.0, 1.0);
	float l = exp(-d * d * 0.9) + 0.22 * exp(-d * d / 9.0);
	gl_FragColor = vec4(vc.rgb * l, 1.0);
}
#endif
