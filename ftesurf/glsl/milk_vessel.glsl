!!ver 130 150
!!samps prev=0 spec=1 ui0=2 ui1=3 xray1=4 xray2=5 =CONED cone=6

// The menu's VESSEL world (src/menu/m_milk.qc, MW_VESSEL): the body, close up,
// the way a medical drama's camera dives into it.  One variant per station --
// the stations are separate places, and on this GPU a shader holding all four
// ran at half the speed of one holding one (the monolith's lean test) -- so
// m_milk.qc swaps the variant halfway through a flight, inside the blur.
//
//   #S0  MAIN   inside an artery: red cells tumbling past, the wall pulsing
//               with the bass like a heartbeat
//   #S1  PLAY   darkfield: glass-shelled plankton lit only at their edges, an
//               x-ray film on a lightbox far behind them
//   #S2  VIS    an iris, its pupil breathing with the bass, under the cornea;
//               the other film is the lightbox mirrored in it
//   #S3  MUSIC  leaf cells: chloroplasts streaming round each cell's wall
//
// Panels are glass slides floating in the scene (milk_panel.h).

#include "sys/defs.h"
#include "glsl/milk_common.h"
#define PANEL_RIM   0.10
#define PANEL_THICK 0.08
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

// Each station's place, mirrored by MM_PoseW's MW_VESSEL poses: the regions
// are modelled about their own origin and moved there.
// MODEL: which ids the kick streaks hide behind -- the cells, the plankton,
// the eye; not the artery's wall or the leaf's cell walls.
#ifdef S0
#define ORG vec3(0.0, 0.0, 0.0)
#define MODEL(id) (id > 1.5)
#endif
#ifdef S1
#define ORG vec3(400.0, 0.0, 0.0)
#define MODEL(id) (id > 0.5)
#endif
#ifdef S2
#define ORG vec3(-400.0, 0.0, 0.0)
#define MODEL(id) (id > 0.5)
#endif
#ifdef S3
#define ORG vec3(0.0, -300.0, 0.0)
#define MODEL(id) (id > 1.5)
#endif

float T;
float TSTART;           // where the primary ray starts: the coarse pass's answer, or 0
vec4  AA;
float QUAL;
float BEAT;         // heartbeat: a lub-dub envelope, pushed by the bass

float spec(float x) { return texture2D(s_spec, vec2(clamp(x, 0.02, 0.98), 0.25)).r; }

#if defined(S1) || defined(S2)
// The x-ray films, gfx/env/xray1.png (front) and xray2.png (side): local
// images, git-ignored and never shipped; without them m_milk.qc binds
// $blackimage and a film adds nothing.  On a lightbox: bone lines white, the
// rest near black, the metal glowing, harder on the big hits.  uv 0..1 over the
// crop (markers and ruler cut off); hot is the metal's centre and half-size in
// image uv, located by hand.
vec3 film(sampler2D s, vec2 uv, vec4 crop, vec4 hot)
{
	vec2 f = mix(crop.xy, crop.zw, uv);
	float x = texture2D(s, f).r;
	float soft = texture2D(s, f, 2.5).r;         // a blurred read: the lines are what stands out of it
	float halo = texture2D(s, f, 4.5).r;
	vec2 pd = abs(f - hot.xy) / hot.zw;
	float onHot = smoothstep(1.15, 0.9, max(pd.x, pd.y));
	float nearHot = exp(-dot(pd, pd) * 0.35);
	float v = clamp((x - 0.2) / 0.7, 0.0, 1.0);
	float bone = v * v * 0.55 + max(x - soft, 0.0) * 3.0;
	float metal = smoothstep(0.6, 0.85, x) * onHot + smoothstep(0.45, 0.75, halo) * nearHot * 0.5;
	float edge = smoothstep(0.0, 0.08, min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y)));
	return (vec3(0.55, 0.72, 1.0) * bone + vec3(0.85, 0.95, 1.0) * metal * (0.7 + 0.9 * AA.w + 0.25 * AA.x)) * edge;
}
#endif

float sdTorus(vec3 p, vec2 t) { vec2 q = vec2(length(p.xz) - t.x, p.y); return length(q) - t.y; }
float sdCyl(vec3 p, float r, float h) { vec2 d = abs(vec2(length(p.xz), p.y)) - vec2(r, h); return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)); }
mat3 rotAxis(vec3 a, float t)
{
	float c = cos(t), s = sin(t);
	vec3 u = normalize(a);
	return mat3(c + u.x * u.x * (1.0 - c), u.y * u.x * (1.0 - c) + u.z * s, u.z * u.x * (1.0 - c) - u.y * s,
	            u.x * u.y * (1.0 - c) - u.z * s, c + u.y * u.y * (1.0 - c), u.z * u.y * (1.0 - c) + u.x * s,
	            u.x * u.z * (1.0 - c) + u.y * s, u.y * u.z * (1.0 - c) - u.x * s, c + u.z * u.z * (1.0 - c));
}

// ------------------------------------------------------------ the regions --
#ifdef S0
// The artery runs along +z; its axis wanders so the far end curves away.
vec2 axisXY(float z) { return vec2(7.0 * sin(z * 0.025), 4.0 * sin(z * 0.017)); }
float radiusAt(float z) { return 6.5 * (1.0 + 0.05 * BEAT + 0.015 * sin(z * 0.3 - T * 3.0)); }

// A red cell: a torus whose hole is closed by a thin disc -- the biconcave dip.
float rbc(vec3 q) { return smin(sdTorus(q, vec2(0.58, 0.30)), sdCyl(q, 0.6, 0.1), 0.2); }

// Cells in 3.5 m slices along the vessel, one per slice, drifting toward the
// camera, each at its own angle and tumbling on its own axis.
float cells(vec3 p, out float cid)
{
	float flow = T * 4.5;
	float zz = p.z + flow;
	float k = floor(zz / 3.5);
	float fz = zz - (k + 0.5) * 3.5;
	vec3 h = hash33(vec3(k, 7.0, 3.0));
	vec2 ax = axisXY(p.z);
	float a = h.x * TAU + T * 0.1 * (h.y - 0.5);
	float r = 1.2 + 3.6 * h.y;
	// None on the left, where the panel floats.
	a = mix(-2.2, 2.2, fract(a / TAU));
	vec3 c = vec3(ax + r * vec2(cos(a), sin(a)), 0.0);
	vec3 q = vec3(p.xy - c.xy, fz);
	q = rotAxis(h * 2.0 - 1.0 + vec3(0.0, 0.0, 0.01), T * (0.6 + h.z) + h.x * 6.0) * q;
	cid = k;
	float d = rbc(q);
	// A slice's cell never comes nearer its slice's edge than 0.8 m.
	return min(d, 1.75 - abs(fz) + 0.8);
}

// A white cell rolling along the wall ahead, knobbly.
vec3 WBC;
float wbc(vec3 p)
{
	vec3 q = p - WBC;
	if (dot(q, q) > 9.0)
		return length(q) - 2.0;
	return length(q) - 1.35 - 0.12 * sin(q.x * 7.0 + T) * sin(q.y * 6.0) * sin(q.z * 7.0 - T);
}

float wall(vec3 p)
{
	vec2 d = p.xy - axisXY(p.z);
	float a = atan(d.y, d.x);
	// Endothelium: lozenge cells laid along the flow.
	float bumps = 0.10 * sin(a * 14.0) * sin(p.z * 1.4 + a * 3.0);
	return radiusAt(p.z) + bumps - length(d);
}

vec2 regionMap(vec3 p)
{
	float cid;
	vec2 m = vec2(wall(p), 1.0);
	float d = cells(p, cid);
	if (d < m.x) m = vec2(d, 2.0);
	d = wbc(p);
	if (d < m.x) m = vec2(d, 3.0);
	return m;
}
#endif

#ifdef S1
// Darkfield plankton about (0, 0, 40): two radiolarians, a pillbox diatom, a
// boat-shaped one and a volvox colony.  Positions drift; everything turns.
vec3 O1, O2, O3, O4, O5;
mat3 R1, R2, R3, R4, R5;

// A lattice sphere with spines: holes and spines on a polar grid.
float radiolarian(vec3 p, float R, float holes, float spines)
{
	float r = length(p);
	if (r > R + 2.2)
		return r - R - 2.0;
	float th = acos(clamp(p.y / max(r, 1e-4), -1.0, 1.0));
	float ph = atan(p.z, p.x);
	vec2 g = vec2(th * holes / PI, ph * holes / PI);
	vec2 f = fract(g) - 0.5;
	float shell = abs(r - R) - 0.07;
	float hole = (length(f) - 0.33) * R * PI / holes;
	shell = max(shell, -hole);
	// A spine from the nearest grid node, outward.
	vec2 gn = (floor(g) + 0.5) * PI / holes;
	vec3 dir = vec3(sin(gn.x) * cos(gn.y), cos(gn.x), sin(gn.x) * sin(gn.y));
	float along = clamp(dot(p, dir), R, R + spines);
	float spine = length(p - dir * along) - 0.05 * (1.0 - (along - R) / spines) - 0.01;
	return min(shell, spine);
}

// A pillbox diatom: a lidded disc with radial ribs and a central boss.
float diatom(vec3 p)
{
	float d = sdCyl(p, 2.4, 0.35) - 0.12;
	if (d > 0.5)
		return d;
	float a = atan(p.z, p.x);
	d += 0.025 * abs(sin(a * 36.0)) * step(0.2, abs(p.y));
	return min(d, length(p) - 0.45);
}

// A pennate diatom: a long pointed boat with transverse striae.
float boat(vec3 p)
{
	vec3 q = p * vec3(1.0, 2.2, 4.0);
	float d = (length(q) - 3.0) / 4.0;
	if (d > 0.4)
		return d;
	return d + 0.01 * sin(p.x * 26.0);
}

// Volvox: a hollow ball of small cells, daughter colonies inside.
float volvox(vec3 p)
{
	float r = length(p);
	if (r > 4.6)
		return r - 4.4;
	float th = acos(clamp(p.y / max(r, 1e-4), -1.0, 1.0));
	float ph = atan(p.z, p.x);
	vec2 g = vec2(th * 14.0 / PI, ph * 14.0 / PI);
	vec2 gn = (floor(g) + 0.5) * PI / 14.0;
	vec3 dir = vec3(sin(gn.x) * cos(gn.y), cos(gn.x), sin(gn.x) * sin(gn.y));
	float cell = length(p - dir * 3.9) - 0.26;
	float skin = abs(r - 3.9) - 0.03;
	float kids = min(length(p - vec3(1.1, 0.4, 0.3)) - 0.9, length(p - vec3(-0.9, -0.6, -0.5)) - 0.75);
	return min(min(cell, skin), kids);
}

vec2 regionMap(vec3 p)
{
	vec2 m = vec2(radiolarian(R1 * (p - O1), 3.0, 9.0, 1.8), 1.0);
	float d = diatom(R2 * (p - O2));                  if (d < m.x) m = vec2(d, 2.0);
	d = radiolarian(R3 * (p - O3), 1.7, 6.0, 1.2);    if (d < m.x) m = vec2(d, 3.0);
	d = boat(R4 * (p - O4));                          if (d < m.x) m = vec2(d, 4.0);
	d = volvox(R5 * (p - O5));                        if (d < m.x) m = vec2(d, 5.0);
	return m;
}
#endif

#ifdef S2
// The iris at z 100, facing the camera, 30 m across; the pupil breathes with
// the bass.  The cornea is analytic (added in shading); the sclera beyond.
#define IRIS_C vec3(0.0, 0.0, 100.0)
float PUPIL;
float irisH(vec2 q)
{
	float r = length(q);
	float a = atan(q.y, q.x);
	// Stroma: radial fibres wandering a little, the collarette ridge, crypts.
	float fib = 0.16 * abs(sin(a * 56.0 + sin(r * 0.45) * 1.5)) + 0.15 * sin(a * 23.0 + r * 0.2);
	float coll = 1.2 * exp(-pow((r - PUPIL * 1.7) * 0.6, 2.0)) * (0.7 + 0.3 * sin(a * 18.0));
	float crypt = -1.0 * smoothstep(0.75, 0.9, vnoise(vec3(q * 0.35, 1.0)));
	return fib + coll + crypt - 0.08 * r;
}
vec2 regionMap(vec3 p)
{
	vec3 q = p - IRIS_C;
	float r = length(q.xy);
	if (r > 36.0 || abs(q.z) > 12.0)
		return vec2(max(r - 34.0, abs(q.z) - 10.0), 0.0);
	float d = (q.z + irisH(q.xy) * 0.9) * 0.5;
	d = max(d, PUPIL - r);                        // the pupil is a hole
	d = max(d, r - 31.0);
	// The sclera: a wall of white further out.
	float scl = max(q.z - 2.0 + 0.04 * (r - 31.0) * (r - 31.0) * 0.1, 31.0 - r);
	return (d < scl) ? vec2(d, 1.0) : vec2(scl, 2.0);
}
#endif

#ifdef S3
// Leaf cells in the plane y = -300: bricks 8 x 3.6 m, walls 3 m high.
// Chloroplasts stream round each cell's inside wall -- cyclosis; each cell's
// wall glows with its column's band.
#define LEAF_Y 0.0
#define CELL   vec2(8.0, 3.6)
vec2 cellOf(vec2 xz, out vec2 local)
{
	float row = floor(xz.y / CELL.y);
	float x = xz.x + mod(row, 2.0) * CELL.x * 0.5;
	vec2 c = vec2(floor(x / CELL.x), row);
	local = vec2(x - (c.x + 0.5) * CELL.x, xz.y - (row + 0.5) * CELL.y);
	return c;
}
float chloroplasts(vec3 p, vec2 local, vec2 c)
{
	// Round a superellipse near the wall, 14 of them, the nearest by angle.
	vec2 hs = CELL * 0.5 - vec2(0.75, 0.6);
	// No audio in the speed: the phase is T * speed, so a speed that moved with
	// the music jumped every chloroplast by T times the change.
	float speed = 0.2 + 0.4 * hash12(c);
	float ang = atan(local.y / hs.y, local.x / hs.x);
	float n = 14.0;
	float ph = T * speed + hash12(c + 3.0) * TAU;
	float k = floor((ang - ph) / TAU * n + 0.5);
	float a = ph + k * TAU / n;
	vec2 ca = vec2(cos(a), sin(a));
	vec2 pos = hs * sign(ca) * pow(abs(ca), vec2(0.5));
	vec3 q = vec3(local.x - pos.x, p.y - (LEAF_Y - 1.4) - 0.2 * sin(a * 3.0 + T), local.y - pos.y);
	return length(q * vec3(1.0, 2.2, 1.35)) / 2.2 - 0.36;
}
vec2 regionMap(vec3 p)
{
	if (p.y > LEAF_Y + 2.0)
		return vec2(p.y - LEAF_Y - 1.0, 0.0);
	vec2 local;
	vec2 c = cellOf(p.xz, local);
	vec2 e = CELL * 0.5 - abs(local);
	float wallsD = max(min(e.x, e.y) - 0.13, p.y - LEAF_Y);
	float floorD = p.y - (LEAF_Y - 3.0);
	vec2 m = vec2(min(wallsD, floorD), 1.0);
	float d = chloroplasts(p, local, c);
	if (d < m.x) m = vec2(d, 2.0);
	// A nucleus in some cells, pressed into a corner.
	if (hash12(c + 9.0) > 0.6)
	{
		d = length(vec3(local.x - 2.4 * sign(hash12(c) - 0.5), p.y - LEAF_Y + 2.0, local.y)) - 1.05;
		if (d < m.x) m = vec2(d, 3.0);
	}
	return m;
}
#endif

// --------------------------------------------------------------- the scene --
vec2 map(vec3 p)
{
	return regionMap(p - ORG);
}
vec3 PANN;              // the traced panel's normal (milk_panel.h's panTrace)

vec3 calcNormal(vec3 p, float t)
{
	float h = 0.002 + 0.0006 * t;
	vec3 n = vec3(0.0);
	for (int i = ZERO; i < 4; i++)
	{
		vec3 e = 0.5773 * (2.0 * vec3(float(((i + 3) >> 1) & 1), float((i >> 1) & 1), float(i & 1)) - 1.0);
		n += e * map(p + e * h).x;
	}
	float l = length(n);
	return (l > 1e-8) ? n / l : vec3(0.0, 1.0, 0.0);
}

vec3 bgCol(vec3 rd)
{
#ifdef S0
	return vec3(0.06, 0.004, 0.006) * (0.6 + 0.4 * BEAT);
#endif
#ifdef S1
	// Darkfield: black, and a drift of motes too small to resolve.
	vec3 sp = rd * 260.0;
	float h = hash13(floor(sp));
	vec3 f = fract(sp) - 0.5;
	return vec3(0.004, 0.005, 0.008) + milk_pal(h + M_LOOK.x) * step(0.992, h) * exp(-dot(f, f) * 40.0) * 0.5;
#endif
#ifdef S2
	return vec3(0.015, 0.012, 0.02);
#endif
#ifdef S3
	return vec3(0.01, 0.035, 0.03);
#endif
}

float fogK()
{
#ifdef S0
	return 0.035;
#endif
#ifdef S1
	return 0.012;
#endif
#ifdef S2
	return 0.004;
#endif
#ifdef S3
	return 0.02;
#endif
}

vec3 shade(vec3 pw, vec3 rd, float id, float t)
{
	vec3 n = (id > 9.5) ? PANN : calcNormal(pw, t);
	vec3 p = pw - ORG;
	float ndv = clamp(dot(n, -rd), 0.0, 1.0);
	float fre = pow(1.0 - ndv, 3.0);

	if (id > 9.5)
	{
		// A panel: a glass slide, the UI in it, a faint bevel of light.
		bool a = id < 10.5;
		vec3 pl = a ? panLocal(pw, PA_C, PA_R, PA_U, PA_N) : panLocal(pw, PB_C, PB_R, PB_U, PB_N);
		vec2 PH = a ? PA_H : PB_H;
		float PL = a ? PA_L : PB_L;
		vec3 col = vec3(0.01, 0.012, 0.016) + bgCol(reflect(rd, n)) * 0.4 + milk_pal(M_LOOK.x + 0.1) * fre * 0.6;
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

#ifdef S0
	// Lit from the camera, like an endoscope, with the warmth of blood
	// showing through everything: wrap diffuse, and edges glowing orange.
	vec3 L = normalize(M_CAMPOS.xyz - pw);
	float dif = 0.3 + 0.7 * clamp(dot(n, L) * 0.6 + 0.4, 0.0, 1.0);
	float fall = 1.0 / (1.0 + t * t * 0.0009);
	if (id < 1.5)
	{
		vec2 d = p.xy - axisXY(p.z);
		float a = atan(d.y, d.x);
		float cellv = 0.5 + 0.5 * sin(a * 14.0) * sin(p.z * 1.4 + a * 3.0);
		vec3 base = mix(vec3(0.35, 0.03, 0.04), vec3(0.62, 0.12, 0.10), cellv);
		vec3 col = base * dif * fall + vec3(1.0, 0.35, 0.15) * fre * (0.35 + 0.6 * BEAT);
		col += pow(clamp(dot(reflect(rd, n), L), 0.0, 1.0), 24.0) * vec3(1.0, 0.75, 0.65) * 0.35 * fall;
		// Capillary veins.
		col *= 1.0 - 0.35 * smoothstep(0.93, 0.99, abs(sin(p.z * 0.4 + sin(a * 3.0) * 2.0 + a * 5.0)));
		return col;
	}
	if (id < 2.5)
	{
		vec3 col = vec3(0.75, 0.05, 0.05) * dif * fall + vec3(1.0, 0.4, 0.3) * fre * 0.6;
		col += pow(clamp(dot(reflect(rd, n), L), 0.0, 1.0), 40.0) * vec3(1.0, 0.8, 0.7) * 0.6 * fall;
		return col;
	}
	return vec3(0.85, 0.8, 0.85) * dif * fall * 0.8 + vec3(0.6, 0.7, 1.0) * fre * 0.5;
#endif

#ifdef S1
	// Darkfield: only what scatters light sideways shows -- the edges -- in a
	// dispersion of colour round the rim.
	vec3 tint = milk_pal(M_LOOK.x + id * 0.13 + n.y * 0.25 + n.x * 0.15);
	float rim = pow(1.0 - ndv, 2.2);
	float body = 0.04 + 0.06 * ndv;
	return tint * (rim * (1.3 + 0.2 * AA.z + 0.3 * AA.w) + body) + vec3(0.9, 0.95, 1.0) * pow(1.0 - ndv, 8.0) * 0.8;
#endif

#ifdef S2
	vec3 L = normalize(vec3(-0.4, 0.5, -1.0));
	float dif = 0.25 + 0.75 * clamp(dot(n, L), 0.0, 1.0);
	vec3 q = p - IRIS_C;
	float r = length(q.xy);
	if (id < 1.5)
	{
		// Blue-green at the rim, gold round the pupil; fibres paler.
		float a = atan(q.y, q.x);
		float fib = abs(sin(a * 56.0 + sin(r * 0.45) * 1.5));
		vec3 outer = mix(vec3(0.10, 0.28, 0.35), vec3(0.18, 0.42, 0.40), fib);
		vec3 inner = mix(vec3(0.55, 0.35, 0.08), vec3(0.85, 0.62, 0.25), fib);
		vec3 base = mix(inner, outer, smoothstep(PUPIL * 1.4, PUPIL * 2.4, r));
		base *= 0.55 + 0.45 * smoothstep(30.5, 26.0, r);       // the dark limbal ring
		base *= smoothstep(PUPIL, PUPIL + 0.8, r);
		return base * dif + milk_pal(M_LOOK.x + r * 0.01) * fre * 0.3;
	}
	// Sclera: white, a little pink, fine red vessels.
	float a = atan(q.y, q.x);
	float vein = smoothstep(0.96, 1.0, abs(sin(a * 9.0 + sin(r * 0.3) * 2.0 + vnoise(vec3(q.xy * 0.1, 2.0)) * 3.0)));
	return mix(vec3(0.78, 0.72, 0.72), vec3(0.6, 0.08, 0.08), vein * 0.8) * dif;
#endif

#ifdef S3
	vec3 L = normalize(vec3(0.3, 1.0, 0.2));
	float dif = 0.3 + 0.7 * clamp(dot(n, L), 0.0, 1.0);
	if (id < 1.5)
	{
		vec2 local;
		vec2 c = cellOf(p.xz, local);
		float band = spec(0.04 + fract(c.x * 0.137) * 0.8);
		if (p.y > LEAF_Y - 0.15)
		{
			// The wall's top edge: the glowing line the cells are drawn in.
			return vec3(0.55, 0.95, 0.65) * (1.0 + 0.6 * band) + milk_pal(M_LOOK.x + 0.1) * 0.15 * AA.w;
		}
		if (n.y > 0.5)
		{
			// Cytoplasm floor: teal, a little mottled.
			float v = vnoise(vec3(p.xz * 0.6, T * 0.1));
			return vec3(0.07, 0.22, 0.16) * (0.6 + 0.8 * v) * dif + vec3(0.15, 0.45, 0.3) * (0.12 + band * 0.25);
		}
		return vec3(0.10, 0.30, 0.22) * dif + vec3(0.3, 0.8, 0.5) * fre * (0.3 + 0.3 * band);
	}
	if (id < 2.5)
	{
		// Chloroplast: vivid, and brighter at the edge where it is thinnest.
		float g = 0.5 + 0.5 * sin(p.x * 9.0 + p.z * 7.0);       // grana, the stacked discs inside
		return vec3(0.10, 0.50, 0.08) * dif * (0.8 + 0.3 * g) + vec3(0.7, 1.0, 0.35) * fre * 0.9 + vec3(0.08, 0.22, 0.02);
	}
	return vec3(0.5, 0.6, 0.55) * dif * 0.4 + vec3(0.7, 0.9, 0.8) * fre * 0.8;   // nucleus
#endif
}

float march(vec3 ro, vec3 rd, float tmax, int steps, out float id)
{
	float t = max(0.02, TSTART);
	id = 0.0;
	for (int i = 0; i < 160; i++)
	{
		if (i >= steps)
			break;
		vec2 m = map(ro + rd * t);
		if (m.x < 0.0006 * t + 0.001)
		{
			id = m.y;
			return t;
		}
		t += m.x * 0.8;
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
	panInit();

	// A heartbeat: lub-dub at 64 a minute, the bass leaning on it and the big
	// kicks pushing it.
	float hb = fract(T * 64.0 / 60.0);
	BEAT = exp(-hb * 18.0) + 0.6 * exp(-max(hb - 0.18, 0.0) * 22.0) * step(0.18, hb);
	BEAT = clamp(BEAT * 0.7 + AA.x * 0.2 + M_EVENT.w * M_FOCUS.w * 0.45, 0.0, 1.2);

#ifdef S0
	WBC = vec3(axisXY(34.0) + vec2(4.6, -2.8), 34.0 - mod(T * 0.6, 20.0));
#endif
#ifdef S1
	O1 = vec3(4.0 + sin(T * 0.07) * 1.5, 1.0 + sin(T * 0.05) * 1.0, 36.0);
	O2 = vec3(-5.0, -2.5 + sin(T * 0.06), 30.0 + sin(T * 0.04) * 2.0);
	O3 = vec3(9.0 + cos(T * 0.05) * 1.0, -3.5, 26.0);
	O4 = vec3(-1.5, 4.0 + sin(T * 0.08) * 0.6, 22.0);
	O5 = vec3(12.0, 5.0, 46.0 + sin(T * 0.03) * 2.0);
	R1 = rotAxis(vec3(0.3, 1.0, 0.2), T * 0.08);
	R2 = rotAxis(vec3(1.0, 0.4, 0.1), T * 0.06 + 1.0);
	R3 = rotAxis(vec3(0.2, 0.5, 1.0), -T * 0.1);
	R4 = rotAxis(vec3(0.1, 1.0, 0.6), T * 0.05 + 2.0);
	R5 = rotAxis(vec3(0.7, 0.3, 0.2), T * 0.04);
#endif
#ifdef S2
	PUPIL = max(4.5, 7.0 + 1.6 * sin(T * 0.21) - 1.0 * AA.x - 0.6 * M_EVENT.w * M_FOCUS.w);
#endif

	vec2 uv = tc * 2.0 - 1.0;
	uv.y = -uv.y;
	vec3 ro = M_CAMPOS.xyz;
	vec3 rd = normalize(M_CAMFWD.xyz + uv.x * M_TIME.z * M_CAMPOS.w * M_CAMRIGHT.xyz
	                                 + uv.y * M_CAMPOS.w * M_CAMUP.xyz);

	int steps = (QUAL >= 3.0) ? 110 : ((QUAL >= 2.0) ? 80 : 56);
	float tmax = 400.0;
#ifdef CONE
	gl_FragColor = vec4(coneMarch(ro, rd, milk_conek(vtc), tmax, 0.0, steps * 2));
	return;
#endif
	TSTART = milk_conestart(tc);
	// The panels' slabs are boxes, intersected here; the march stops at them.
	float id, pw;
	vec3 pn;
	float tp = panTrace(ro, rd, 0.0, 0.0, pn, pw);
	float t = march(ro, rd, min(tmax, tp), steps, id);
	bool model = t > 0.0 && MODEL(id);
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
	float fog = 1.0 - exp(-t * fogK());
	col = mix(col, bgCol(rd), fog);

#ifdef S1
	// The lightbox, 150 m behind the plankton and turned a little toward them;
	// a scan line crosses it every 9 s.  Drawn only where nothing is in front.
	if (t >= tmax)
	{
		vec3 FC = ORG + vec3(-58.0, 6.0 + 2.0 * sin(T * 0.05), 150.0);
		vec3 FN = vec3(0.26, 0.0, -0.966);
		vec3 FR = vec3(0.966, 0.0, 0.26);
		float dn = dot(rd, FN);
		float tf = dot(FC - ro, FN) / min(dn, -1e-3);
		vec3 q = ro + rd * tf - FC;
		vec2 fu = vec2(0.5 + dot(q, FR) / 96.0, 0.5 - q.y / 140.0);
		if (dn < 0.0 && tf > 0.0 && fu == clamp(fu, 0.0, 1.0))
		{
			float sl = exp(-pow((fu.y - (fract(T / 9.0) * 1.6 - 0.3)) / 0.02, 2.0));
			col += film(s_xray2, fu, vec4(0.095, 0.0, 1.0, 0.845), vec4(0.530, 0.575, 0.040, 0.059)) * (0.5 + 0.9 * sl);
		}
	}
#endif

#ifdef S2
	// The cornea: a clear dome over the iris -- the lightbox it is looking at
	// mirrored in it, the hexagons of its inner cell layer, a glint that moves
	// with you.
	vec3 IC = IRIS_C + ORG;
	vec3 cc = IC + vec3(0.0, 0.0, 40.0);
	vec3 oc = ro - cc;
	float b = dot(oc, rd);
	float disc = b * b - (dot(oc, oc) - 52.0 * 52.0);
	if (disc > 0.0)
	{
		float tc0 = -b - sqrt(disc);
		vec3 hp = ro + rd * tc0;
		if (tc0 > 0.0 && hp.z < IC.z - 2.0 && length(hp.xy - IC.xy) < 33.0)
		{
			vec3 n = normalize(hp - cc);
			float fr = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 4.0);
			vec3 rr = reflect(rd, n);
			vec2 fu = vec2(0.5 - (rr.x + 0.33) / 0.18, 0.5 - (rr.y - 0.40) / 0.31);
			if (fu == clamp(fu, 0.0, 1.0))
				col += film(s_xray1, fu, vec4(0.131, 0.0, 1.0, 0.915), vec4(0.544, 0.689, 0.055, 0.088)) * 1.3
				     + vec3(0.9, 0.95, 1.0) * 0.08;
			vec2 hx = (hp.xy - IC.xy) * 0.9;
			vec2 hq = vec2(hx.x * 1.1547, hx.y + hx.x * 0.57735);
			vec2 hf = fract(hq) - 0.5;
			float hexl = smoothstep(0.46, 0.5, max(abs(hf.x), abs(hf.y)));
			col += vec3(0.5, 0.7, 0.9) * fr * 0.35 + vec3(0.3, 0.5, 0.6) * hexl * 0.04;
		}
	}
	// The red reflex: light coming back out through the pupil.
	if (t >= tmax || id < 0.5)
		col += vec3(0.6, 0.12, 0.05) * 0.25 * smoothstep(PUPIL, 0.0, length((ro + rd * ((IC.z - ro.z) / max(rd.z, 1e-3))).xy - IC.xy)) * (0.6 + 0.8 * AA.x);
#endif

	gl_FragColor = vec4(col, milk_alpha(mask, fog, model, t));
}
#endif
