!!ver 130 150
!!samps prev=0 scene=1

// Patch 467 -- the MilkDrop warp: last tick's feedback frame, pushed through a
// zoom/rotate/wobble about M_FOCUS.xy, advected along its own luminance
// gradient (MilkDrop's "slime" flow, M_EVENT.y), optionally folded into
// M_EXTRA.w kaleidoscope segments, decayed, and re-seeded from this tick's
// scene.  Runs at the fixed sim rate, so every per-tick amount below is a
// per-tick amount and the look does not change with the display's fps.
//
// MENU: only the bright part of the 3D scene seeds the trails, so the solid
// geometry stays crisp and the light smears.  SKY: the generated image IS the
// content, so it is injected whole.

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
	float asp = M_TIME.z;
	vec2 c = M_FOCUS.xy;

	vec2 d = tc - c;
	d.x *= asp;

	float segs = M_EXTRA.w;
	if (segs > 0.5)
	{
		// Polar mirror fold: the kaleidoscope that turns a tunnel into a
		// fractal cathedral once the feedback recurses it a few dozen times.
		float r = length(d);
		float a = atan(d.y, d.x);
		float w = TAU / segs;
		a = abs(mod(a + w * 0.5, w) - w * 0.5);
		d = r * vec2(cos(a), sin(a));
	}

	d = rot2(M_WARP.y) * d / M_WARP.x;
	vec2 src = c + vec2(d.x / asp, d.y);

	// MilkDrop's wobble (plugin.cpp's warp term, one octave).
	float wob = M_WARP.w * 0.0035;
	src += wob * vec2(sin(T * 0.73 + tc.y * 11.0 + tc.x * 3.1),
	                  cos(T * 0.61 + tc.x * 9.0 - tc.y * 4.3));

	// Slime: move against the brightness gradient so light pools and flows.
	vec2 px = 1.0 / vec2(textureSize(s_prev, 0));
	float gx = lum(texture2D(s_prev, src + vec2(px.x * 2.0, 0.0)).rgb) - lum(texture2D(s_prev, src - vec2(px.x * 2.0, 0.0)).rgb);
	float gy = lum(texture2D(s_prev, src + vec2(0.0, px.y * 2.0)).rgb) - lum(texture2D(s_prev, src - vec2(0.0, px.y * 2.0)).rgb);
	src -= vec2(gx, gy) * M_EVENT.y * 0.004;

	vec3 prev = texture2D(s_prev, src).rgb;

	// Zooming samples from inside the frame; anything that would come from
	// outside it is clamp-to-edge smear, so fade it rather than let it streak.
	vec2 edge = smoothstep(0.0, 0.03, src) * smoothstep(1.0, 0.97, src);
	prev *= edge.x * edge.y;

	// Per-tick decay, plus MilkDrop's small subtractive floor so dim trails
	// actually reach black instead of sitting at a haze.
	prev = max(prev * M_WARP.z - 0.0015, 0.0);

	vec3 sc = texture2D(s_scene, tc).rgb;
#ifdef SKY
	// Scaled by (1 - decay): a static seed settles at 1.6x itself instead of
	// accumulating to 1/(1-decay) -- 14x at the sky's 0.93.
	vec3 o = prev + sc * (1.0 - M_WARP.z) * 1.6;
#else
	vec3 o = prev + max(sc - 0.35, 0.0) * 0.55;
#endif
	gl_FragColor = vec4(min(o, vec3(8.0)), 1.0);
}
#endif
