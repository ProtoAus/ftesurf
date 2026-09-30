!!ver 130 150
!!samps spec=0 scene=1 size=2

// Kick streaks (src/milk_sys.qc, Milk_WavesDraw): MilkDrop's waves, ribbons
// drawn INTO the feedback frame so the warp carries each one off as a trail.
// The line is pushed across its ribbon by the mix's waveform -- milk_spec's
// second row, oldest sample at u 0 -- and is not drawn where a model stands
// nearer than the streaks fly: the scene's alpha holds that model's distance
// (milk_common.h, milk_alpha), so an arc thrown from the cube comes out from
// behind it.  s_size is the target being drawn into's twin, for its size.
// Per vertex: texcoord.x the waveform read, its integer part the depth in
// metres (0 = in front of everything); .y across the ribbon, in line widths;
// colour rgb the light; a the swing in line widths plus the waveform's gain
// in quarters, times 1000.

#include "sys/defs.h"

varying vec2 tc;
varying vec4 vc;
varying vec2 pix;           // target pixels, y down, as the drawpic texcoords run

#ifdef VERTEX_SHADER
void main(void)
{
	tc = v_texcoord;
	vc = v_colour;
	pix = v_position.xy;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
void main(void)
{
	float code = floor(vc.a / 1000.0);
	float swing = vc.a - code * 1000.0;
	float w = texture2D(s_spec, vec2(fract(tc.x), 0.75)).r * 2.0 - 1.0;
	float d = tc.y - swing * clamp(w * code * 0.25, -1.0, 1.0);
	float l = exp(-d * d * 0.9) + 0.22 * exp(-d * d / 9.0);
	float D = floor(tc.x);
	if (D > 0.0)
	{
		float a = texture2D(s_scene, pix / vec2(textureSize(s_size, 0))).a;
		float z = (a >= 1.5) ? a - 2.0 : ((abs(a) > 0.004) ? 0.0 : 1e6);
		l *= smoothstep(D * 0.97, D * 1.03, z);
	}
	gl_FragColor = vec4(vc.rgb * l, 1.0);
}
#endif
