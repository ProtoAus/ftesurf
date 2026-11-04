!!ver 110
!!fixed
!!permu FOG
!!samps wear=0
!!cvarf r_rampwear_dirt
!!cvarf r_rampwear_scratch
!!cvarf r_rampwear_debug
!!cvarf r_rampwear_distance
!!cvarf r_rampwear_shine

// FTESurf P1300: single-pass double modulation (dst_color, src_color), output half the multiplier.
// This retains the ramp's own lighting and permits a small view-dependent polish highlight. Mask (tools/rampwear.py): r ride wear, g boarding scratch, ba the
// travel direction as a line, (cos 2a, sin 2a) in the surface's frame -- u level along the ramp, v up
// it, built here from the surface normal that rides in v_colour exactly as frame() does there.
// Dirt is 3D noise in world space, so it runs on across faces; scratches use the surface's frame (one
// per brush face or displacement) and restart only at a surface's edge.

#include "sys/defs.h"
#include "sys/fog.h"

varying vec2 tc;
varying vec3 wpos;
varying vec3 wnorm;

#ifdef VERTEX_SHADER
void main()
{
	tc = v_texcoord;
	wpos = v_position.xyz;
	wnorm = v_colour.rgb * 2.0 - 1.0;       // cl_rampwear.qc packs the surface's frame normal here
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
uniform float cvar_r_rampwear_dirt;
uniform float cvar_r_rampwear_scratch;
uniform float cvar_r_rampwear_debug;
uniform float cvar_r_rampwear_distance;
uniform float cvar_r_rampwear_shine;

float hash(vec2 p)
{
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float hash3(vec3 p)
{
	return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453);
}

float vnoise3(vec3 p)
{
	vec3 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = mix(mix(hash3(i), hash3(i + vec3(1.0, 0.0, 0.0)), f.x), mix(hash3(i + vec3(0.0, 1.0, 0.0)), hash3(i + vec3(1.0, 1.0, 0.0)), f.x), f.y);
	float b = mix(mix(hash3(i + vec3(0.0, 0.0, 1.0)), hash3(i + vec3(1.0, 0.0, 1.0)), f.x), mix(hash3(i + vec3(0.0, 1.0, 1.0)), hash3(i + vec3(1.0, 1.0, 1.0)), f.x), f.y);
	return mix(a, b, f.z);
}

float fbm3(vec3 p)
{
	return 0.5 * vnoise3(p) + 0.25 * vnoise3(p * 2.03 + 7.1) + 0.125 * vnoise3(p * 4.01 + 3.7) + 0.125 * vnoise3(p * 8.1 + 1.3);
}

// Rows across angle bin b (15 degrees each, a line, so 12 bins), dashes along it: scratch coverage.
// aa: a row's footprint in pixels, taken once in main() -- fwidth in here would see the bin jump.
float scratches(vec2 p, float b, float amount, float aa, float rowh)
{
	b = mod(b, 12.0);
	float a = b * 0.2617994;
	vec2 d = vec2(cos(a), sin(a));
	vec2 q = vec2(dot(p, d), dot(p, vec2(-d.y, d.x)));
	float row = floor(q.y / rowh);
	float fy = fract(q.y / rowh);
	float dash = mix(30.0, 260.0, hash(vec2(row, 9.1 + b)));
	float sx = (q.x + hash(vec2(row, 1.7 + b)) * 977.0) / dash;
	float seg = floor(sx);
	float fx = fract(sx);
	float wid = mix(0.12, 0.4, hash(vec2(seg, row * 3.1 + b)));
	float line = 1.0 - smoothstep(wid, wid + aa + 0.02, abs(fy - 0.5) * 2.0);
	line *= smoothstep(0.0, 0.08, fx) * (1.0 - smoothstep(0.7, 1.0, fx));
	return line * step(hash(vec2(row * 0.37 + b, seg * 1.3)), amount * 1.2) * min(1.0, 0.4 + amount);
}

void main()
{
	vec4 m = texture2D(s_wear, tc);
	if (cvar_r_rampwear_debug > 0.0)
	{	// the mask itself: ride wear red, boarding scratch blue
		gl_FragColor = vec4(vec3(1.0 - 0.9 * m.g, 1.0 - 0.9 * max(m.r, m.g), 1.0 - 0.9 * m.r) * 0.5, 1.0);
		return;
	}
	vec3 n = normalize(wnorm);
	float hl = length(n.xy);
	vec3 u = hl > 1e-4 ? vec3(-n.y, n.x, 0.0) / hl : vec3(1.0, 0.0, 0.0);
	vec3 v = cross(n, u);
	vec2 p = vec2(dot(wpos, u), dot(wpos, v));

	float wear = m.r;
	float scr = m.g;
	vec2 c2 = m.ba * 2.0 - 1.0;
	float lineang = dot(c2, c2) > 0.01 ? 0.5 * atan(c2.y, c2.x) : 0.0;

	// dirt: blotchy film, cleared along the ride line; grain fades before it would alias
	float px = length(fwidth(wpos));
	float blot = fbm3(wpos / 160.0);
	float grain = mix(0.5, vnoise3(wpos / 5.0), 1.0 - smoothstep(0.8, 2.5, px));
	float dirt = clamp(cvar_r_rampwear_dirt, 0.0, 2.0) * (0.45 + 0.55 * blot) * (1.0 - smoothstep(0.05, 0.8, wear));
	vec3 grime = mix(vec3(1.0), vec3(0.58, 0.53, 0.46) * (0.88 + 0.24 * grain), clamp(dirt, 0.0, 1.0));

	// scratches along the travel line, at the two nearest of 12 fixed angles, blended: rotating by
	// the mask's per-texel angle itself bends the rows into swirls
	float amount = clamp(cvar_r_rampwear_scratch, 0.0, 2.0) * clamp(scr + 0.45 * wear, 0.0, 1.0);
	float aa = max(abs(fwidth(p.x)), abs(fwidth(p.y))) / 2.5;
	float bins = lineang / 0.2617994;
	float b0 = floor(bins);
	float blend = smoothstep(0.25, 0.75, bins - b0);
	// Fine grooves cannot survive below a pixel. Broader scuffs take over instead of erasing the
	// entire scratch layer at ~500 units. Both scales keep the same world-space phase at seams.
	// Only the transition evaluates both scales; no extra texture samples/passes/light traces.
	float fine = 0.0, coarse = 0.0;
	if (aa < 0.7)
		fine = mix(scratches(p, b0, amount, aa, 2.5), scratches(p, b0 + 1.0, amount, aa, 2.5), blend);
	if (aa > 0.2)
		coarse = mix(scratches(p, b0, amount, aa * 0.125, 20.0), scratches(p, b0 + 1.0, amount, aa * 0.125, 20.0), blend);
	float s = mix(fine, coarse * 0.65, smoothstep(0.2, 0.7, aa));
	s *= 1.0 - smoothstep(0.35, 0.9, aa * 0.125);

	// a scratch shows the clean surface through the dirt and a groove on it; a hard boarding also scuffs
	vec3 col = mix(grime, vec3(1.0), s) * (1.0 - 0.45 * s) * (1.0 - 0.18 * clamp(scr * cvar_r_rampwear_scratch, 0.0, 1.0));
	// Cheap polish, not a reflection capture or a light query. Only the smooth ridden band shines.
	vec3 h = normalize(normalize(e_eyepos - wpos) + normalize(vec3(0.3, 0.4, 1.0)));
	float polish = pow(max(0.0, dot(n, h)), 32.0) * wear * (1.0 - 0.65 * scr);
	col += vec3(clamp(cvar_r_rampwear_shine, 0.0, 0.5) * polish);
	float reach = clamp(cvar_r_rampwear_distance, 1024.0, 24000.0);
	col = mix(vec3(1.0), col, 1.0 - smoothstep(reach * 0.75, reach, distance(wpos, e_eyepos)));
	gl_FragColor = vec4((vec3(1.0) - fog3additive(vec3(1.0) - col)) * 0.5, 1.0);
}
#endif
