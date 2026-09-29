!!ver 130 150
!!samps src=0 scene=1 ui0=2 ui1=3

// Patch 467 -- milk_out to the screen, every display frame.  The sim runs at a
// fixed rate, so this is the only per-frame cost: one bilinear tap, a
// parallax nudge from the latest mouse position (M_EXTRA.xy, fresher than the
// sim), and screen-resolution dither so the 8-bit output never bands.
//
// #PANELS (the menu): the in-world panels' UI textures, composited over the
// slabs the scene raymarched.  The scene target's alpha says which slab face
// the ray hit first (+1 A, -1 B, scaled by the fog in front of it), so
// anything standing in front of a panel still hides it, and every other
// pixel -- most of the screen -- stops after that one extra tap.  At rest a
// panel is laid out face-on at one texel per pixel, texel edges on pixel
// edges, so the bilinear tap below returns the texel unchanged: the font's own
// raster.

#include "sys/defs.h"
#include "glsl/milk_common.h"
#ifdef PANELS
#include "glsl/milk_panel.h"
#endif

varying vec2 tc;

#ifdef VERTEX_SHADER
void main(void)
{
	tc = v_texcoord;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
#ifdef PANELS
// One panel over the picture.  fp is texels per screen pixel, from the
// geometry rather than dFdx, so the caller may branch around this freely.
vec3 panelOver(vec3 c, sampler2D ui, vec2 uv, float fp, float lit, float vis)
{
	if (!panInside(uv))
		return c;
	vec4 r = panReveal(uv, lit);
	if (r.z <= 0.0 && r.w <= 0.0)
		return c;
	vec4 t;
	if (fp < 1.2)
		t = texture2D(ui, r.xy);
	else
	{
		// Minified -- a panel far off in a flight: four taps across the footprint.
		vec2 o = 0.25 * fp / vec2(textureSize(ui, 0));
		t = 0.25 * (texture2D(ui, r.xy + o) + texture2D(ui, r.xy - o)
		          + texture2D(ui, r.xy + vec2(o.x, -o.y)) + texture2D(ui, r.xy + vec2(-o.x, o.y)));
	}
	// The target was drawn with ordinary alpha blending onto transparent black,
	// which leaves colour premultiplied and alpha squared; sqrt undoes the
	// square for a single layer, and is close for stacked ones.
	float a = sqrt(clamp(t.a, 0.0, 1.0)) * min(r.z, 1.0) * vis;
	return c * (1.0 - a) + (t.rgb * r.z + vec3(0.55, 0.75, 1.0) * r.w) * vis;
}
#endif

void main(void)
{
	vec2 uv = (tc - 0.5) * 0.97 + 0.5 + M_EXTRA.xy;
	vec3 c = texture2D(s_src, uv).rgb;
#ifdef PANELS
	// Screen height in pixels: tc runs 0..1 down it, and on a full-screen quad
	// its derivative is the same everywhere, so this is safe to take here.
	float sh = 1.0 / max(abs(dFdy(tc.y)), 1e-6);
	float m = texture2D(s_scene, uv).a;
	if (abs(m) > 0.004)
	{
		bool a = m > 0.0;
		vec3 C, R, U, N;
		vec2 H;
		float L;
		if (a)
			panFrame(M_PANA, M_PANA2, C, R, U, N, H, L);
		else
			panFrame(M_PANB, M_PANB2, C, R, U, N, H, L);
		vec2 ndc = uv * 2.0 - 1.0;
		ndc.y = -ndc.y;
		vec3 ro = M_CAMPOS.xyz;
		vec3 rd = M_CAMFWD.xyz + ndc.x * M_TIME.z * M_CAMPOS.w * M_CAMRIGHT.xyz + ndc.y * M_CAMPOS.w * M_CAMUP.xyz;
		float t = panRay(ro, rd, C, N);
		if (t > 0.0 && H.x > 0.0)
		{
			vec2 puv = panUV(panLocal(ro + rd * t, C, R, U, N), H);
			// World per screen pixel at this depth (rd has unit forward, so t
			// is the depth), over world per texel, leaning with the face.
			float texh = a ? float(textureSize(s_ui0, 0).y) : float(textureSize(s_ui1, 0).y);
			float lean = max(-dot(normalize(rd), N), 0.25);
			float fp = t * M_CAMPOS.w * 0.97 * texh / (sh * H.y * lean);
			if (a)
				c = panelOver(c, s_ui0, puv, fp, L, clamp(m, 0.0, 1.0));
			else
				c = panelOver(c, s_ui1, puv, fp, L, clamp(-m, 0.0, 1.0));
		}
	}
#endif
	c += (hash12(gl_FragCoord.xy + fract(M_TIME.x * 7.0) * 211.0) - 0.5) * (1.5 / 255.0);
	gl_FragColor = vec4(c, 1.0);
}
#endif
