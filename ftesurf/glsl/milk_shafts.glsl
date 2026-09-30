!!ver 130 150
!!samps scene=0

// Light shafts (src/milk_sys.qc, only while milk_shafts > 0): the scene's
// brightest light -- a sun, sky through a gap -- blurred along the line to the
// light, the station's anchor (M_FOCUS.xy), so whatever stands in front of it
// cuts dark lanes through the glow.  Volumetric light as a post-process, at a
// quarter of the milk size; milk_comp.glsl adds it at M_FOCUS.z.  A panel's
// face (the scene's alpha) casts none: text streaking toward a sun is noise.

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
vec3 lightAt(vec2 p)
{
	vec4 s = texture2D(s_scene, p);
	float l = max(s.r, max(s.g, s.b));
	return s.rgb * (smoothstep(0.6, 1.6, l) * (1.0 - clamp(abs(milk_panelmask(s.a)) * 4.0, 0.0, 1.0)));
}

void main(void)
{
	// 28 taps over 96% of the way to the light, each 5% weaker than the last.
	vec2 st = (M_FOCUS.xy - tc) * (0.96 / 28.0);
	vec2 p = tc;
	vec3 acc = vec3(0.0);
	float w = 1.0;
	for (int i = 0; i < 28; i++)
	{
		acc += lightAt(p) * w;
		w *= 0.95;
		p += st;
	}
	gl_FragColor = vec4(acc * (1.0 / 15.0), 1.0);
}
#endif
