!!ver 130 150
!!samps scene=0 fb=1 b1=2 b2=3

// Patch 467 -- composite: scene + trails + bloom -> display range.
//
// The trails can be lit as a liquid (M_EVENT.y): the gradient of the blurred
// trails becomes a surface normal, then diffuse + a tight specular.  That is
// MilkDrop's chrome/slime trick (GetBlur1 differences as a normal) -- the
// "reflective" look is a 2D fake, and it costs four taps.

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
	float T = M_TIME.x;
	vec4 sa = texture2D(s_scene, tc);
	vec3 s  = sa.rgb;
	vec3 f  = texture2D(s_fb, tc).rgb;
#ifdef SKY
	float pm = 0.0;
#else
	// A menu panel's face (the scene's alpha, milk_panel.h): the trails are a
	// screen-space layer, and without this they would paint over the slab
	// as if it were glass.
	float pm = clamp(abs(sa.a), 0.0, 1.0);
#endif
	vec3 b1 = texture2D(s_b1, tc).rgb;
	vec3 b2 = texture2D(s_b2, tc).rgb;

	float liquid = M_EVENT.y;
	if (liquid > 0.01)
	{
		vec2 p1 = 1.5 / vec2(textureSize(s_b1, 0));
		float gx = lum(texture2D(s_b1, tc + vec2(p1.x, 0.0)).rgb) - lum(texture2D(s_b1, tc - vec2(p1.x, 0.0)).rgb);
		float gy = lum(texture2D(s_b1, tc + vec2(0.0, p1.y)).rgb) - lum(texture2D(s_b1, tc - vec2(0.0, p1.y)).rgb);
		vec3 n = normalize(vec3(-gx * 5.0, gy * 5.0, 1.0));
		vec3 L = normalize(vec3(-0.45, 0.55, 0.7));
		float dif = 0.45 + 0.55 * clamp(dot(n, L), 0.0, 1.0);
		float spc = pow(clamp(dot(reflect(-L, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 28.0);
		float cover = clamp(lum(f) * 1.6, 0.0, 1.0);
		vec3 env = milk_pal(M_LOOK.x + n.x * 0.35 + n.y * 0.2 + 0.1);
		vec3 lit = f * dif + (spc * vec3(1.0, 0.97, 0.92) * 1.4 + env * 0.25 * (1.0 - n.z)) * cover;
		f = mix(f, lit, liquid);
	}

	vec3 c = s + f * M_LOOK.y * (1.0 - 0.85 * pm) + (b1 * 0.55 + b2 * 0.85) * M_LOOK.z * (1.0 - 0.4 * pm);

	// Beat flash: a tint of the station colour, not white, so it reads as
	// light in the space rather than a camera flash.
	c += milk_pal(M_LOOK.x + 0.15) * M_EVENT.x * 0.18;

	c = aces(c * M_LOOK.w);

	// Chromatic fringe toward the edges, vignette, grain.
	vec2 v = tc - 0.5;
	float r2 = dot(v, v);
#ifndef SKY
	float ca = clamp(r2 * 3.0, 0.0, 1.0) * (1.0 - pm);
	c.r = mix(c.r, aces(texture2D(s_scene, tc - v * 0.006).rgb * M_LOOK.w).r, ca);
	c.b = mix(c.b, aces(texture2D(s_scene, tc + v * 0.006).rgb * M_LOOK.w).b, ca);
	c *= 1.0 - r2 * 0.95;
#endif
	c += (hash12(tc * 911.0 + fract(T) * 117.0) - 0.5) * 0.018;
	gl_FragColor = vec4(max(c, 0.0), 1.0);
}
#endif
