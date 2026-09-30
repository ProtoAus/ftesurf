!!ver 130 150
!!samps src=0 hist=1

// Checkerboard resolve (src/milk_sys.qc, the menu's "Checkerboard"): the scene
// target from the half-width raymarch (s_src) and the last resolved frame
// (s_hist).  A pixel raymarched this time is copied; the other half, whose
// four neighbours all were, keeps its old value while that sits inside their
// range -- a still view stays sharp -- and where it does not (something moved)
// is filled from the neighbour pair along the edge: clamping alone left teeth
// on every edge of a flight.  At an edge the range spans both sides, so an old
// value passes anyway; in a flight (M_CAMFWD.w) the fill wins outright.
//   #COPY  this frame into the history, texel for texel.

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
	ivec2 p = ivec2(gl_FragCoord.xy);
#ifdef COPY
	gl_FragColor = texelFetch(s_src, p, 0);
#else
	ivec2 hs = textureSize(s_src, 0) - 1;
	int par = int(M_EVENT.z);
	if (((p.x + p.y + par) & 1) == 0)
	{
		gl_FragColor = texelFetch(s_src, ivec2(p.x >> 1, p.y), 0);
		return;
	}
	vec4 l = texelFetch(s_src, clamp(ivec2((p.x - 1) >> 1, p.y), ivec2(0), hs), 0);
	vec4 r = texelFetch(s_src, clamp(ivec2((p.x + 1) >> 1, p.y), ivec2(0), hs), 0);
	vec4 u = texelFetch(s_src, clamp(ivec2(p.x >> 1, p.y + 1), ivec2(0), hs), 0);
	vec4 d = texelFetch(s_src, clamp(ivec2(p.x >> 1, p.y - 1), ivec2(0), hs), 0);
	vec4 h = texelFetch(s_hist, p, 0);
	vec4 hc = clamp(h, min(min(l, r), min(u, d)), max(max(l, r), max(u, d)));
	const vec3 W = vec3(0.3, 0.6, 0.1);
	vec4 fill = (dot(abs(l.rgb - r.rgb), W) < dot(abs(u.rgb - d.rgb), W)) ? (l + r) * 0.5 : (u + d) * 0.5;
	float moved = max(dot(abs(h.rgb - hc.rgb), W) * 8.0, M_CAMFWD.w * 3.0);
	gl_FragColor = mix(hc, fill, clamp(moved, 0.0, 1.0));
#endif
}
#endif
