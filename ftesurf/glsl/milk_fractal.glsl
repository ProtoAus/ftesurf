!!ver 130 150
!!samps prev=0 spec=1 ui0=2 ui1=3 =CONED cone=6

// The menu's FRACTAL world (src/menu/m_milk.qc, MW_FRACTAL): four places, one
// classic fractal each.  The camera rests -- an in-world panel needs it still --
// so the fractal turns or drifts past it instead.  One variant per station,
// like milk_vessel.glsl, swapped halfway through a flight; each place is
// bounded, so the swap lands in empty fog.
//
//   #S0  MAIN   a pseudo-Kleinian cathedral, turning slowly round the camera
//   #S1  PLAY   the same fractal folded into a taller box: a moonlit hall,
//               turning
//   #S2  VIS    a Mandelbulb against a light, breathing with the bass
//   #S3  MUSIC  down a tunnel of a Menger slab, drifting; the rims of the holes
//               lit by the spectrum
//
// Volumetrics, cheap: the march gathers glow where it passes close to the
// surface, the fog scatters the light, and the pipeline's shafts pass
// (glsl/milk_shafts.glsl) blurs the bloom toward the light -- which is the
// station's anchor, M_FOCUS.xy.

#include "sys/defs.h"
#include "glsl/milk_common.h"
#define PANEL_RIM   0.10
#define PANEL_THICK 0.10
#include "glsl/milk_panel.h"

varying vec2 vtc;

#ifdef VERTEX_SHADER
void main(void)
{
	vtc = v_texcoord;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER

#define ZERO (min(int(M_TIME.w), 0))

// Each place: the world point ORG it turns about, which is the fractal-space
// point ORGQ; metres per fractal unit; and the light, a direction -- the
// anchor MM_PoseW projects for the shafts lies along it from the camera.
// MAIN, PLAY and MUSIC turn about the resting camera (MM_PoseW's ppos is ORG),
// VIS about the bulb.
#ifdef S0
#define ORG   vec3(0.0, 0.0, 0.0)
#define ORGQ  vec3(0.9, 0.9, -0.9)          // a corner of the fold box: 19 m from any surface
#define SC    26.0
#define LIGHT normalize(vec3(0.25, 0.55, 1.0))
#endif
#ifdef S1
#define ORG   vec3(800.0, 0.0, 0.0)
#define ORGQ  vec3(0.8, 1.0, 0.8)           // this box's corner: 15 m clear
#define SC    22.0
#define LIGHT normalize(vec3(0.17, 0.11, 0.98))
#endif
#ifdef S2
#define ORG   vec3(-800.0, 0.0, 0.0)
#define ORGQ  vec3(0.0)
#define SC    22.0
#define LIGHT normalize(vec3(0.2, 0.094, 0.994))    // just behind the bulb's upper right
#endif
#ifdef S3
#define ORG   vec3(0.0, 0.0, 800.0)
#define ORGQ  vec3(0.0)
#define SC    30.0
#define LIGHT normalize(vec3(1.0, 0.12, 0.0))
#endif
#define BOUND 260.0         // metres: past this the place is empty fog

float T;
vec4  AA;
float QUAL;
float TSTART;           // where the primary ray starts: the coarse pass's answer, or 0
float PIXA;             // radians per scene pixel: the hit tolerance follows it
vec3  PANN;             // the traced panel's normal (milk_panel.h's panTrace)
vec4  TRAP;             // orbit trap of the last fractal evaluation
mat3  FROT;             // world -> fractal rotation, this frame
vec3  FOFF;             // fractal-space offset, this frame

float spec(float x) { return texture2D(s_spec, vec2(clamp(x, 0.02, 0.98), 0.25)).r; }

mat3 rotY(float a) { float c = cos(a), s = sin(a); return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c); }
mat3 rotX(float a) { float c = cos(a), s = sin(a); return mat3(1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c); }

// ---------------------------------------------------------------- fractals --
// Each returns a distance in fractal units and leaves its orbit trap in TRAP.

#if defined(S0) || defined(S1)
// Knighty's pseudo-Kleinian (fractalforums, 2011): fold into a box, invert
// inside a sphere, repeat; the surface is thin discs, which the inversions
// bend into arches and domes at every scale.  The box's shape is the
// architecture: MAIN and PLAY are two of them.
vec3 KC;
float KR;
float fracDE(vec3 q)
{
	float s = 1.0;
	vec4 tr = vec4(1e5);
	for (int i = ZERO; i < 8; i++)
	{
		q = 2.0 * clamp(q, -KC, KC) - q;
		float r2 = max(dot(q, q), 1e-6);
		tr = min(tr, vec4(abs(q), r2));
		float k = max(KR / r2, 1.0);
		q *= k;
		s *= k;
	}
	TRAP = tr;
	float rxy = length(q.xy);
	return max(rxy - 0.93, abs(rxy * q.z) / max(length(q), 1e-6)) / s;
}
#endif

#ifdef S2
// The power-8 bulb, its power drifting a little.
float PW;
float fracDE(vec3 q)
{
	float r = length(q);
	if (r > 1.35)
	{
		TRAP = vec4(1.0);
		return r - 1.25;
	}
	vec3 z = q;
	float dr = 1.0;
	vec4 tr = vec4(abs(z), dot(z, z));
	for (int i = ZERO; i < 7; i++)
	{
		if (r > 2.0)
			break;
		float th = acos(clamp(z.y / r, -1.0, 1.0)) * PW;
		float ph = atan(z.z, z.x) * PW;
		dr = pow(r, PW - 1.0) * PW * dr + 1.0;
		z = pow(r, PW) * vec3(sin(th) * cos(ph), cos(th), sin(th) * sin(ph)) + q;
		tr = min(tr, vec4(abs(z), dot(z, z)));
		r = length(z);
	}
	TRAP = tr;
	return 0.5 * log(max(r, 1e-6)) * r / dr;
}
#endif

#ifdef S3
// A Menger slab: side-2 sponges tiled in x and z, one deep in y.  Each level
// removes three bars through every cell (the monolith's carve()).
float carve3(vec3 q, float s)
{
	vec3 a = abs(mod(q * s + 1.0, 2.0) - 1.0);
	return (min(max(a.x, a.y), min(max(a.y, a.z), max(a.z, a.x))) - 1.0 / 3.0) / s;
}
// The surface is the largest of five terms; where the runner-up is nearly as
// large, two faces meet -- an edge, which TRAP.y carries for the lights.
float fracDE(vec3 q)
{
	float d = abs(q.y) - 1.0;
	float d2 = -1e5, lv = -1.0;
	float s = 1.0;
	for (int i = ZERO; i < 4; i++)
	{
		float c = -carve3(q, s);
		if (c > d)
		{
			d2 = d;
			d = c;
			lv = float(i);
		}
		else
			d2 = max(d2, c);
		s *= 3.0;
	}
	TRAP = vec4(lv, d2, 0.0, 0.0);
	return d;
}
#endif

// ------------------------------------------------------------------- scene --
vec3 toF(vec3 p) { return ORGQ + FROT * ((p - ORG) / SC) + FOFF; }

// .x distance (metres), .y material: 1 the fractal.
vec2 map(vec3 p)
{
	float b = length(p - ORG) - BOUND;
	if (b > 2.0)
		return vec2(b, 0.0);
	return vec2(max(fracDE(toF(p)) * SC, b), 1.0);
}

vec3 calcNormal(vec3 p, float t)
{
	float h = max(PIXA * t * 0.5, 0.002 * SC * 0.01);
	vec3 n = vec3(0.0);
	for (int i = ZERO; i < 4; i++)
	{
		vec3 e = 0.5773 * (2.0 * vec3(float(((i + 3) >> 1) & 1), float((i >> 1) & 1), float(i & 1)) - 1.0);
		n += e * map(p + e * h).x;
	}
	float l = length(n);
	return (l > 1e-8) ? n / l : vec3(0.0, 1.0, 0.0);
}

// Occlusion from four steps out along the normal, in fractal units.
float calcAO(vec3 p, vec3 n)
{
	float occ = 0.0, w = 1.0;
	for (int i = ZERO; i < 4; i++)
	{
		float h = 0.01 + 0.035 * float(i);
		occ += (h - map(p + n * (h * SC)).x / SC) * w;
		w *= 0.7;
	}
	return clamp(1.0 - occ * 5.0, 0.0, 1.0);
}

// The sky or void behind each place, with its light.
vec3 bgCol(vec3 rd)
{
	float sd = max(dot(rd, LIGHT), 0.0);
#ifdef S0
	vec3 c = mix(vec3(0.10, 0.08, 0.07), vec3(0.20, 0.24, 0.32), clamp(rd.y * 0.8 + 0.4, 0.0, 1.0));
	return c + vec3(1.0, 0.85, 0.6) * (pow(sd, 400.0) * 6.0 + pow(sd, 12.0) * 0.35);
#endif
#ifdef S1
	vec3 c = mix(vec3(0.01, 0.015, 0.03), vec3(0.03, 0.06, 0.09), clamp(rd.y + 0.5, 0.0, 1.0));
	return c + vec3(0.5, 0.8, 1.0) * (pow(sd, 300.0) * 5.0 + pow(sd, 10.0) * 0.2);
#endif
#ifdef S2
	vec3 c = vec3(0.012, 0.008, 0.025) + milk_pal(M_LOOK.x + 0.2) * 0.02;
	// A cold star: a warm one comes out green under the cool grade.
	return c + vec3(0.9, 0.95, 1.0) * (pow(sd, 250.0) * 4.0 + pow(sd, 70.0) * 0.6 + pow(sd, 10.0) * 0.08) * (0.85 + 0.25 * AA.x);
#endif
#ifdef S3
	return vec3(0.004, 0.005, 0.009) + vec3(0.6, 0.8, 1.0) * (pow(sd, 200.0) * 5.0 + pow(sd, 6.0) * 0.12);
#endif
}

float fogK()
{
#ifdef S0
	return 0.0055;
#endif
#ifdef S1
	return 0.0035;
#endif
#ifdef S2
	return 0.002;
#endif
#ifdef S3
	return 0.006;
#endif
}

vec3 shade(vec3 pw, vec3 rd, float id, float t)
{
	vec3 n = (id > 9.5) ? PANN : calcNormal(pw, t);
	float ndv = clamp(dot(n, -rd), 0.0, 1.0);
	float fre = pow(1.0 - ndv, 3.0);

	if (id > 9.5)
	{
		// A panel: a slab of dark glass, the UI in it, a bevel of light.
		bool a = id < 10.5;
		vec3 pl = a ? panLocal(pw, PA_C, PA_R, PA_U, PA_N) : panLocal(pw, PB_C, PB_R, PB_U, PB_N);
		vec2 PH = a ? PA_H : PB_H;
		float PL = a ? PA_L : PB_L;
		vec3 col = vec3(0.01, 0.012, 0.016) + bgCol(reflect(rd, n)) * 0.3 + milk_pal(M_LOOK.x + 0.1) * fre * 0.5;
		if (pl.z > -0.03)
		{
			if (a)
				col += panEmit(s_ui0, pl, PH, PL) * 0.4;
			else
				col += panEmit(s_ui1, pl, PH, PL) * 0.4;
		}
		float e = max(abs(pl.x) - PH.x, abs(pl.y) - PH.y);
		col += milk_pal(M_LOOK.x + 0.1) * smoothstep(0.02, 0.0, abs(e - 0.03)) * (0.5 + 0.6 * AA.w) * abs(PL);
		return col;
	}

	map(pw);                // the hit's own orbit trap
	vec4 tr = TRAP;
	float ao = calcAO(pw, n);
	float dif = clamp(dot(n, LIGHT), 0.0, 1.0);
	float sky = 0.5 + 0.5 * n.y;
	vec3 col;

#ifdef S0
	// Ivory stone veined with gold where the orbit came close to the centre.
	vec3 alb = mix(vec3(0.80, 0.74, 0.64), vec3(0.95, 0.66, 0.26), smoothstep(0.35, 0.05, tr.w));
	alb = mix(alb, vec3(0.45, 0.52, 0.62), smoothstep(0.2, 0.0, tr.y) * 0.5);
	col = alb * (dif * vec3(1.0, 0.86, 0.66) * 1.6 + sky * vec3(0.20, 0.26, 0.36) * ao) * (0.3 + 0.7 * ao);
	col += vec3(1.0, 0.6, 0.25) * smoothstep(0.08, 0.0, tr.w) * (0.4 + 0.8 * AA.w) * ao;
#endif
#ifdef S1
	// Pale steel, tinted by how close the orbit came to the centre.
	vec3 alb = mix(vec3(0.55, 0.58, 0.62), vec3(0.25, 0.55, 0.75), smoothstep(0.1, 1.2, tr.w));
	col = alb * (dif * vec3(1.0, 0.95, 0.9) * 1.5 + sky * vec3(0.10, 0.14, 0.20)) * (0.2 + 0.8 * ao);
#endif
#ifdef S2
	// Pearl: the palette walked by the trap, a soft fill from the camera's
	// side, the light behind it a rim round every bulb.
	vec3 alb = milk_pal(M_LOOK.x + tr.w * 0.8 + tr.x * 0.4) * 0.8 + 0.2;
	float back = pow(clamp(dot(rd, LIGHT), 0.0, 1.0), 2.0);
	float fill = clamp(dot(n, normalize(-rd + vec3(0.0, 0.6, 0.0))), 0.0, 1.0);
	col = alb * (dif * 1.1 + fill * 0.55 + sky * 0.2 + 0.05) * (0.25 + 0.75 * ao);
	col += vec3(0.9, 0.95, 1.0) * fre * (0.3 + 1.2 * back) * ao;
	col += alb * smoothstep(0.25, 0.0, tr.w) * (0.3 + 0.9 * AA.w) * 0.5;
#endif
#ifdef S3
	// Black stone; the edges of every hole lit, the band chosen by the sponge
	// along the tunnel and the level of the hole, so the spectrum runs away
	// down it.
	vec3 alb = vec3(0.06, 0.06, 0.07);
	col = alb * (dif * 1.4 + sky * 0.3) * (0.3 + 0.7 * ao);
	float cell = floor(toF(pw).x * 0.5 + 0.5);
	float band = spec(0.04 + fract(cell * 0.137 + tr.x * 0.21) * 0.85);
	float edge = smoothstep(0.006, 0.0, -tr.y) * step(-0.5, tr.x);
	col += milk_pal(M_LOOK.x + tr.x * 0.12 + cell * 0.05) * edge * (0.08 + 2.2 * band * band);
#endif
	col += vec3(0.8, 0.9, 1.0) * fre * 0.06 * ao;
	return col;
}

// March to the fractal or a slab.  The tolerance grows with distance so the
// detail stops at the pixel; near misses gather into `glow`.
float march(vec3 ro, vec3 rd, float tmax, int steps, out float id, inout float glow)
{
	float t = max(0.05, TSTART);
	id = 0.0;
	for (int i = ZERO; i < 160; i++)
	{
		if (i >= steps)
			break;
		vec2 m = map(ro + rd * t);
		float eps = PIXA * t * 0.9 + 0.002;
		float dn = m.x / (SC * 0.03);
		glow += 1.0 / (1.0 + dn * dn);
		if (m.x < eps && m.y > 0.5)
		{
			id = m.y;
			return t;
		}
#ifdef S2
		t += m.x * 0.75;
#else
		t += m.x * 0.9;
#endif
		if (t > tmax)
			break;
	}
	return -1.0;
}

#ifdef CONE
#include "glsl/milk_cone.h"
#endif

void main(void)
{
	vec2 tc = milk_tc(vtc);
	T = M_TIME.x;
	AA = M_AUDIOATT * M_FOCUS.w;
	QUAL = M_EXTRA.z;
	// Scene pixels per unit tc down the target: the quad is full-screen, so this
	// is the same everywhere and safe to take before any branch.
	PIXA = 2.0 * M_CAMPOS.w * abs(dFdy(tc.y));
	panInit();

	FOFF = vec3(0.0);
#ifdef S0
	KC = vec3(0.93, 0.91, 0.93);
	KR = 0.72;
	FROT = rotY(T * 0.011) * rotX(0.25 * sin(T * 0.013));
#endif
#ifdef S1
	KC = vec3(0.8, 1.0, 0.8);
	KR = 0.72;
	FROT = rotY(0.785 + T * 0.011);
#endif
#ifdef S2
	FROT = rotY(T * 0.02) * rotX(0.35);
	PW = 8.0 + 0.6 * sin(T * 0.031) + 0.25 * AA.x;
#endif
#ifdef S3
	FROT = mat3(1.0);
	FOFF = vec3(fract(T * 0.01) * 2.0, 0.0, 0.0);
#endif

	vec2 uv = tc * 2.0 - 1.0;
	uv.y = -uv.y;
	vec3 ro = M_CAMPOS.xyz;
	vec3 rd = normalize(M_CAMFWD.xyz + uv.x * M_TIME.z * M_CAMPOS.w * M_CAMRIGHT.xyz
	                                 + uv.y * M_CAMPOS.w * M_CAMUP.xyz);

	int steps = (QUAL >= 3.0) ? 130 : ((QUAL >= 2.0) ? 96 : 64);
	float tmax = 2.0 * BOUND;
#ifdef CONE
	// Stops short of where march() gathers its glow.
	gl_FragColor = vec4(coneMarch(ro, rd, milk_conek(vtc), tmax, SC * 0.06, steps * 2));
	return;
#endif
	TSTART = milk_conestart(tc);
	float id, pw, glow = 0.0;
	vec3 pn;
	float tp = panTrace(ro, rd, 0.0, 0.0, pn, pw);
	float t = march(ro, rd, min(tmax, tp), steps, id, glow);
	if (t <= 0.0 && tp < tmax)
	{
		t = tp;
		id = (pw > 0.0) ? 10.0 : 11.0;
		PANN = pn;
	}
	vec3 col;
	float mask = 0.0;
	if (t > 0.0)
	{
		col = shade(ro + rd * t, rd, id, t);
		if (id > 9.5)
			mask = (id < 10.5) ? 1.0 : -1.0;
	}
	else
	{
		t = tmax;
		col = bgCol(rd);
	}

	// Fog that scatters the light: toward the light it glows.
	float fog = 1.0 - exp(-t * fogK());
	float sd = max(dot(rd, LIGHT), 0.0);
	vec3 fc = bgCol(rd) * 0.6 + vec3(0.95, 0.92, 0.88) * pow(sd, 6.0) * 0.25;
	col = mix(col, fc, fog);
	col += milk_pal(M_LOOK.x + 0.15) * glow * 0.0035 * (0.7 + 0.5 * AA.y);

	gl_FragColor = vec4(col, mask * (1.0 - fog));
}
#endif
