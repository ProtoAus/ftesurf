!!ver 130 150
!!samps src=0

// FSR 1 for the menu's "Upscaler" (src/milk_sys.qc): AMD FidelityFX Super
// Resolution 1.0's two passes, written after its reference (MIT), once a tick
// into targets the size of the screen past the present's crop -- so the
// present, every frame, still takes one tap.
//   #EASU  edge-adaptive upsampling of out: twelve taps round the point, a
//          Lanczos-like kernel stretched along the local edge and squeezed
//          across it, clamped to the four nearest texels (no ringing)
//   #RCAS  contrast-adaptive sharpening of that: as much negative lobe on the
//          four neighbours as keeps every channel inside 0..1

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
#ifdef EASU
vec3 tapC(ivec2 p, ivec2 hi) { return texelFetch(s_src, clamp(p, ivec2(0), hi), 0).rgb; }
float luma(vec3 c) { return c.b * 0.5 + (c.r * 0.5 + c.g); }

// One texel's cross (a above, b left, c centre, d right, e below) into the
// edge direction and length, weighted w.
void easuSet(inout vec2 dir, inout float len, float w, float a, float b, float c, float d, float e)
{
	float lx = abs(d - b) / max(max(abs(d - c), abs(c - b)), 1e-5);
	float ly = abs(e - a) / max(max(abs(e - c), abs(c - a)), 1e-5);
	dir += vec2(d - b, e - a) * w;
	lx = clamp(lx, 0.0, 1.0);
	ly = clamp(ly, 0.0, 1.0);
	len += (lx * lx + ly * ly) * w;
}

void easuTap(inout vec3 ac, inout float aw, vec2 off, vec2 dir, vec2 len2, float lob, float clp, vec3 c)
{
	vec2 v = vec2(off.x * dir.x + off.y * dir.y, -off.x * dir.y + off.y * dir.x) * len2;
	float d2 = min(dot(v, v), clp);
	float wb = 0.4 * d2 - 1.0;
	float wa = lob * d2 - 1.0;
	float w = (1.5625 * wb * wb - 0.5625) * (wa * wa);
	ac += c * w;
	aw += w;
}

void main(void)
{
	ivec2 hi = textureSize(s_src, 0) - 1;
	vec2 pp = tc * vec2(textureSize(s_src, 0)) - 0.5;
	vec2 fp = floor(pp);
	pp -= fp;
	ivec2 o = ivec2(fp);
	//      b c
	//    e f g h
	//    i j k l
	//      n o
	vec3 b = tapC(o + ivec2(0, -1), hi), c = tapC(o + ivec2(1, -1), hi);
	vec3 e = tapC(o + ivec2(-1, 0), hi), f = tapC(o, hi), g = tapC(o + ivec2(1, 0), hi), h = tapC(o + ivec2(2, 0), hi);
	vec3 i = tapC(o + ivec2(-1, 1), hi), j = tapC(o + ivec2(0, 1), hi), k = tapC(o + ivec2(1, 1), hi), l = tapC(o + ivec2(2, 1), hi);
	vec3 n = tapC(o + ivec2(0, 2), hi), oo = tapC(o + ivec2(1, 2), hi);
	float bL = luma(b), cL = luma(c), eL = luma(e), fL = luma(f), gL = luma(g), hL = luma(h);
	float iL = luma(i), jL = luma(j), kL = luma(k), lL = luma(l), nL = luma(n), oL = luma(oo);

	vec2 dir = vec2(0.0);
	float len = 0.0;
	easuSet(dir, len, (1.0 - pp.x) * (1.0 - pp.y), bL, eL, fL, gL, jL);
	easuSet(dir, len, pp.x * (1.0 - pp.y), cL, fL, gL, hL, kL);
	easuSet(dir, len, (1.0 - pp.x) * pp.y, fL, iL, jL, kL, nL);
	easuSet(dir, len, pp.x * pp.y, gL, jL, kL, lL, oL);

	float dl = dot(dir, dir);
	dir = (dl < 1.0 / 32768.0) ? vec2(1.0, 0.0) : dir * inversesqrt(dl);
	len = len * 0.5;
	len *= len;
	float stretch = 1.0 / max(abs(dir.x), abs(dir.y));
	vec2 len2 = vec2(1.0 + (stretch - 1.0) * len, 1.0 - 0.5 * len);
	float lob = 0.5 + ((1.0 / 4.0 - 0.04) - 0.5) * len;
	float clp = 1.0 / lob;

	vec3 ac = vec3(0.0);
	float aw = 0.0;
	easuTap(ac, aw, vec2( 0.0, -1.0) - pp, dir, len2, lob, clp, b);
	easuTap(ac, aw, vec2( 1.0, -1.0) - pp, dir, len2, lob, clp, c);
	easuTap(ac, aw, vec2(-1.0,  1.0) - pp, dir, len2, lob, clp, i);
	easuTap(ac, aw, vec2( 0.0,  1.0) - pp, dir, len2, lob, clp, j);
	easuTap(ac, aw, vec2( 0.0,  0.0) - pp, dir, len2, lob, clp, f);
	easuTap(ac, aw, vec2(-1.0,  0.0) - pp, dir, len2, lob, clp, e);
	easuTap(ac, aw, vec2( 1.0,  1.0) - pp, dir, len2, lob, clp, k);
	easuTap(ac, aw, vec2( 2.0,  1.0) - pp, dir, len2, lob, clp, l);
	easuTap(ac, aw, vec2( 2.0,  0.0) - pp, dir, len2, lob, clp, h);
	easuTap(ac, aw, vec2( 1.0,  0.0) - pp, dir, len2, lob, clp, g);
	easuTap(ac, aw, vec2( 1.0,  2.0) - pp, dir, len2, lob, clp, oo);
	easuTap(ac, aw, vec2( 0.0,  2.0) - pp, dir, len2, lob, clp, n);

	vec3 mn = min(min(f, g), min(j, k));
	vec3 mx = max(max(f, g), max(j, k));
	gl_FragColor = vec4(clamp(ac / aw, mn, mx), 1.0);
}
#endif

#ifdef RCAS
#define RCAS_SHARP 0.8          // exp2(-0.32 stops); 1 is AMD's sharpest
void main(void)
{
	ivec2 hi = textureSize(s_src, 0) - 1;
	ivec2 p = ivec2(tc * vec2(textureSize(s_src, 0)));
	vec3 b = texelFetch(s_src, clamp(p + ivec2(0, -1), ivec2(0), hi), 0).rgb;
	vec3 d = texelFetch(s_src, clamp(p + ivec2(-1, 0), ivec2(0), hi), 0).rgb;
	vec3 e = texelFetch(s_src, clamp(p, ivec2(0), hi), 0).rgb;
	vec3 f = texelFetch(s_src, clamp(p + ivec2(1, 0), ivec2(0), hi), 0).rgb;
	vec3 h = texelFetch(s_src, clamp(p + ivec2(0, 1), ivec2(0), hi), 0).rgb;
	vec3 mn4 = min(min(b, d), min(f, h));
	vec3 mx4 = max(max(b, d), max(f, h));
	// The largest negative weight on the ring that keeps each channel in 0..1.
	vec3 hitMin = min(mn4, e) / max(4.0 * mx4, 1e-4);
	vec3 hitMax = (1.0 - max(mx4, e)) / min(4.0 * min(mn4, e) - 4.0, -1e-4);
	vec3 lobeC = max(-hitMin, hitMax);
	float lobe = max(-0.1875, min(max(lobeC.r, max(lobeC.g, lobeC.b)), 0.0)) * RCAS_SHARP;
	gl_FragColor = vec4((lobe * (b + d + f + h) + e) / (4.0 * lobe + 1.0), 1.0);
}
#endif
#endif
