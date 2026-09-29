!!ver 130 150
!!samps scene=0 fb=1

// Patch 467 -- bloom source: scene + trails at half size, soft-knee bright
// pass.  The target is half the milk size, so one bilinear tap per quadrant
// covers a 4x4 source footprint.

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
	vec2 px = 1.0 / vec2(textureSize(s_scene, 0));
	vec3 c = vec3(0.0);
	c += texture2D(s_scene, tc + vec2(-px.x, -px.y)).rgb + texture2D(s_fb, tc + vec2(-px.x, -px.y)).rgb * M_LOOK.y;
	c += texture2D(s_scene, tc + vec2( px.x, -px.y)).rgb + texture2D(s_fb, tc + vec2( px.x, -px.y)).rgb * M_LOOK.y;
	c += texture2D(s_scene, tc + vec2(-px.x,  px.y)).rgb + texture2D(s_fb, tc + vec2(-px.x,  px.y)).rgb * M_LOOK.y;
	c += texture2D(s_scene, tc + vec2( px.x,  px.y)).rgb + texture2D(s_fb, tc + vec2( px.x,  px.y)).rgb * M_LOOK.y;
	c *= 0.25;

	// Soft knee: highlights bloom, the dark body of the scene does not.  A
	// daylight world moves the knee up (M_CAMUP.w).
	float kn = (M_CAMUP.w > 0.0) ? M_CAMUP.w : 0.35;
	float l = max(c.r, max(c.g, c.b));
	float k = clamp(l - kn, 0.0, 0.5);
	k = k * k / 0.5;
	float w = max(k, l - kn - 0.25) / max(l, 1e-4);
	gl_FragColor = vec4(c * w, 1.0);
}
#endif
