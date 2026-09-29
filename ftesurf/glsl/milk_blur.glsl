!!ver 130 150
!!samps src=0

// Patch 467 -- separable blur for the bloom pyramid.
//   #H / #V  9-tap Gaussian (sigma ~2 texels) as 5 bilinear taps.
//   #DOWN    4-tap box into a target half the size of the source.
// Texel size comes from the source itself, so one program serves every level.

#include "sys/defs.h"

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
	vec2 px = 1.0 / vec2(textureSize(s_src, 0));
#ifdef DOWN
	vec3 c = texture2D(s_src, tc + px * vec2(-1.0, -1.0)).rgb
	       + texture2D(s_src, tc + px * vec2( 1.0, -1.0)).rgb
	       + texture2D(s_src, tc + px * vec2(-1.0,  1.0)).rgb
	       + texture2D(s_src, tc + px * vec2( 1.0,  1.0)).rgb;
	gl_FragColor = vec4(c * 0.25, 1.0);
#else
	#ifdef H
		vec2 dir = vec2(px.x, 0.0);
	#else
		vec2 dir = vec2(0.0, px.y);
	#endif
	// Linear-sampling offsets/weights for a 9-tap binomial-ish kernel.
	vec3 c = texture2D(s_src, tc).rgb * 0.2270270;
	c += (texture2D(s_src, tc + dir * 1.3846154).rgb + texture2D(s_src, tc - dir * 1.3846154).rgb) * 0.3162162;
	c += (texture2D(s_src, tc + dir * 3.2307692).rgb + texture2D(s_src, tc - dir * 3.2307692).rgb) * 0.0702703;
	gl_FragColor = vec4(c, 1.0);
#endif
}
#endif
