!!ver 110
!!fixed
!!samps wear=0
!!cvarf r_rampwear_dirt
!!cvarf r_rampwear_scratch
!!cvarf r_rampwear_debug

// FTESurf P1278: ramp wear over the ramps (cl_rampwear.qc's polygons), blendfunc filter, so the output is a
// multiplier on the lit ramp. Mask (tools/rampwear.py): r ride wear, g boarding scratch, ba the
// travel direction in frame(n), which is built here the same way: u level along the ramp, v down it.
// Dirt is a grimy film cleared where riders pass; scratches run along the travel direction, through
// the dirt (they show the clean surface) and as grooves on it. Detail is procedural in plane units,
// faded where a scratch row is under a pixel apart, and the whole overlay fades out by 6000 units.

#include "sys/defs.h"

varying vec2 tc;
varying vec3 wpos;
varying vec3 wnorm;

#ifdef VERTEX_SHADER
void main()
{
	tc = v_texcoord;
	wpos = v_position.xyz;
	wnorm = v_colour.rgb * 2.0 - 1.0;       // cl_rampwear.qc packs the face normal here
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
uniform float cvar_r_rampwear_dirt;
uniform float cvar_r_rampwear_scratch;
uniform float cvar_r_rampwear_debug;

float hash(vec2 p)
{
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float vnoise(vec2 p)
{
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

float fbm(vec2 p)
{
	return 0.5 * vnoise(p) + 0.25 * vnoise(p * 2.03 + 7.1) + 0.125 * vnoise(p * 4.01 + 3.7) + 0.125 * vnoise(p * 8.1 + 1.3);
}

void main()
{
	vec4 m = texture2D(s_wear, tc);
	if (cvar_r_rampwear_debug > 0.0)
	{	// the mask itself: ride wear darkens blue and green, boarding scratch red and green
		gl_FragColor = vec4(1.0 - 0.9 * m.g, 1.0 - 0.9 * max(m.r, m.g), 1.0 - 0.9 * m.r, 1.0);
		return;
	}
	vec3 n = normalize(wnorm);
	float hl = length(n.xy);
	vec3 u = hl > 1e-4 ? vec3(-n.y, n.x, 0.0) / hl : vec3(1.0, 0.0, 0.0);
	vec3 v = cross(n, u);
	vec2 p = vec2(dot(wpos, u), dot(wpos, v));

	float wear = m.r;
	float scr = m.g;
	vec2 dir = m.ba * 2.0 - 1.0;
	dir = dot(dir, dir) > 0.01 ? normalize(dir) : vec2(1.0, 0.0);

	// dirt: blotchy film with grain, cleared along the ride line
	float blot = fbm(p / 160.0);
	float grain = vnoise(p / 5.0);
	float dirt = clamp(cvar_r_rampwear_dirt, 0.0, 2.0) * (0.45 + 0.55 * blot) * (1.0 - smoothstep(0.05, 0.8, wear));
	vec3 grime = mix(vec3(1.0), vec3(0.58, 0.53, 0.46) * (0.88 + 0.24 * grain), clamp(dirt, 0.0, 1.0));

	// scratches: rows across the travel direction, dashes along it
	vec2 q = vec2(dot(p, dir), dot(p, vec2(-dir.y, dir.x)));
	float rowh = 2.5;
	float row = floor(q.y / rowh);
	float fy = fract(q.y / rowh);
	float r1 = hash(vec2(row, 1.7));
	float dash = mix(30.0, 260.0, hash(vec2(row, 9.1)));
	float sx = (q.x + r1 * 977.0) / dash;
	float seg = floor(sx);
	float fx = fract(sx);
	float wid = mix(0.12, 0.4, hash(vec2(seg, row * 3.1)));
	float aa = fwidth(q.y) / rowh;
	float line = 1.0 - smoothstep(wid, wid + aa + 0.02, abs(fy - 0.5) * 2.0);
	line *= smoothstep(0.0, 0.08, fx) * smoothstep(1.0, 0.7, fx);
	float amount = clamp(cvar_r_rampwear_scratch, 0.0, 2.0) * clamp(scr + 0.45 * wear, 0.0, 1.0);
	float s = line * step(hash(vec2(row * 0.37, seg * 1.3)), amount * 1.2) * min(1.0, 0.4 + amount);
	s *= 1.0 - smoothstep(0.35, 0.9, aa);           // a row under a pixel: shimmer, not detail

	// a scratch shows the clean surface through the dirt and a groove on it; a hard boarding also scuffs
	vec3 col = mix(grime, vec3(1.0), s) * (1.0 - 0.45 * s) * (1.0 - 0.18 * clamp(scr * cvar_r_rampwear_scratch, 0.0, 1.0));
	float far = 1.0 - smoothstep(3500.0, 6000.0, distance(wpos, e_eyepos));
	gl_FragColor = vec4(mix(vec3(1.0), col, far), 1.0);
}
#endif
