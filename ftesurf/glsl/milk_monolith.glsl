!!ver 130 150
!!samps prev=0 spec=1 ui0=2 ui1=3

// The menu's MONOLITH world (src/menu/m_milk.qc, MW_MONOLITH): a void 400 m
// across inside a megastructure that does not end.  One unit is a metre.
//
//   MAIN   a balcony high on the west wall.  Across the void: a bridge with one
//          figure on it, and on the east wall a forest terrace whose stream
//          falls off its edge into the abyss
//   PLAY   in that forest
//   VIS    a corridor into the north wall that does not end
//   MUSIC  towers of light cubes rising out of the abyss -- the spectrum --
//          seen from a flooded platform
//
// The megastructure is a box fractal: solid outside the void, carved into
// halls at three scales, with ledges and fins on the void's walls.  Light is a
// sun over the open shaft (it reaches only the upper walls), shafts of it
// down the void, and height fog -- thin above, the abyss below.  The panels
// are concrete slabs with a screen.

#include "sys/defs.h"
#include "glsl/milk_common.h"
#define PANEL_RIM   0.16
#define PANEL_THICK 0.35
#include "glsl/milk_panel.h"

varying vec2 tc;

#ifdef VERTEX_SHADER
void main(void)
{
	tc = v_texcoord;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER

#define VOID_HALF  200.0
#define BRIDGE_X   -100.0
#define BRIDGE_Y   -12.0
#define FIGURE     vec3(-100.0, -12.0, -25.0)
#define TERR_Y     -60.0                    // forest terrace, off the east wall
#define TERR_X0    96.0
#define CORR_Y     30.0                     // corridor floor, into the north wall
#define PLAT_Y     -40.0
#define TOWERS     vec3(0.0, 0.0, -150.0)
#define PLAT       vec3(30.0, 0.0, -64.0)

// ZERO is 0 that the compiler cannot see: a loop from it is not unrolled, so
// map() is inlined once per loop rather than once per iteration.  Unrolled,
// this shader took 12 s to compile on an Intel N100.
#define ZERO (min(int(M_TIME.w), 0))

float T;
vec4  AA;
float QUAL;
vec3  SUN, CAM;
float PA_EXT, PB_EXT;
vec3  PANN;             // the traced panel's normal (milk_panel.h's panTrace)

float spec(float x) { return texture2D(s_spec, vec2(clamp(x, 0.02, 0.98), 0.25)).r; }
vec2  hash22(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973)); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.xx + p3.yz) * p3.zy); }

float sdCapsule(vec3 p, vec3 a, vec3 b, float r)
{
	vec3 pa = p - a, ba = b - a;
	float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * h) - r;
}

// The stream's path across the terrace, flowing west to the edge.
float streamZ(float x) { return 12.0 * sin(x * 0.045 + 1.0); }

// -------------------------------------------------------------- structure --
// Holes of one carving scale: three bars through each cell of size S.
float carve(vec3 p, vec3 S, vec3 a)
{
	vec3 q = mod(p, S) - 0.5 * S;
	return min(sdBox2(q.yz, a.yz), min(sdBox2(q.xz, a.xz), sdBox2(q.xy, a.xy)));
}

// The corridor: a 14 x 16 bore north from z 190, a portal frame every 10 m.
// Negative = inside the empty bore.
float corridorEmpty(vec3 p)
{
	vec2 cs = vec2(p.y - CORR_Y - 8.0, p.x);
	float bore = max(sdBox2(cs, vec2(8.0, 7.0)), 190.0 - p.z);
	float zl = mod(p.z - 190.0, 10.0) - 5.0;
	float frame = max(abs(zl) - 0.8, -sdBox2(vec2(p.y - CORR_Y - 7.25, p.x), vec2(7.25, 5.4)));
	return max(bore, -frame);
}

// The megastructure: solid outside the void, halls carved at three scales.
// Some 30 m blocks keep their fine niches, some are left blank -- brutalism
// is mostly the blank wall.  The corridor sits in a solid shell so the
// fractal never opens its walls.
float mega(vec3 p)
{
	float d = -sdBox(p, vec3(VOID_HALF, 1e4, VOID_HALF));
	if (d > 4.0)
		return d;
	// Some 90 m blocks are left whole: a wall that is holes everywhere reads
	// as noise at 400 m, and a blank one as a wall.
	vec3 ac = floor((p + vec3(20.0, 0.0, 35.0)) / vec3(90.0, 120.0, 90.0));
	if (hash13(ac + 5.0) > 0.3)
		d = max(d, -carve(p + vec3(20.0, 0.0, 35.0), vec3(90.0, 120.0, 90.0), vec3(15.0, 24.0, 15.0)));
	d = max(d, -carve(p + vec3(5.0, 13.0, 9.0), vec3(30.0, 40.0, 30.0), vec3(5.0, 7.5, 5.0)));
	// The fine niches only within 220 m of the camera: beyond, they are a few
	// pixels, and the small steps they force near a wall are the cost.
	vec3 bc = floor((p + vec3(5.0, 13.0, 9.0)) / vec3(30.0, 40.0, 30.0));
	if (hash13(bc) > 0.45 && dot(p - CAM, p - CAM) < 48400.0)
		d = max(d, -carve(p, vec3(10.0, 13.333, 10.0), vec3(1.6, 2.7, 1.6)));
	if (p.z > 186.0 && abs(p.x) < 20.0 && abs(p.y - CORR_Y - 8.0) < 22.0)
	{
		float shell = max(sdBox2(vec2(p.y - CORR_Y - 8.0, p.x), vec2(14.0, 13.0)), VOID_HALF - p.z);
		d = max(min(d, shell), -corridorEmpty(p));
	}
	return d;
}

// Ledges and fins on the void's walls, for scale: a wall this big reads as a
// wall only once there is something the size of a room on it.
float wallDetail(vec3 p)
{
	vec3 a = abs(p);
	// Details reach at most 19 m out of a wall.  NOT clamped to a constant: a
	// flat plateau of distance reads as a surface once the hit tolerance grows
	// past it, far away, and a flat surface has no normal (NaN, magenta blocks).
	if (max(a.x, a.z) < VOID_HALF - 26.0)
		return VOID_HALF - 19.5 - max(a.x, a.z);
	float xw = step(a.z, a.x);
	float w = VOID_HALF - (xw > 0.5 ? a.x : a.z);            // metres out from the wall
	float u = xw > 0.5 ? p.z : p.x;                          // along it
	float side = xw > 0.5 ? sign(p.x) : 2.0 + sign(p.z);
	vec2 c = floor(vec2(u, p.y) / vec2(46.0, 52.0));
	float h = hash12(c + side * 17.0);
	float ledge = 1e5;
	if (h > 0.55)
	{
		vec2 lc = (c + 0.5) * vec2(46.0, 52.0);
		float half_ = 6.0 + 12.0 * fract(h * 7.1);
		float depth = 5.0 + 14.0 * fract(h * 3.7);
		ledge = sdBox(vec3(u - lc.x, p.y - lc.y, w - depth * 0.5), vec3(half_, 1.2, depth * 0.5));
	}
	float fu = mod(u, 23.0) - 11.5;
	float fin = sdBox(vec3(fu, 0.0, w - 1.5), vec3(0.9, 1e4, 1.5));
	// The next cell's ledge may be nearer than this one's -- but every ledge
	// keeps 5 m (along) and 24 m (up) clear of its cell's edges, so that far
	// past the edge is safe.  A clamp of the edge distance alone had rays
	// crawling a metre at a time along every cell boundary: 90 steps a pixel.
	vec2 e = min(vec2(u, p.y) - c * vec2(46.0, 52.0), (c + 1.0) * vec2(46.0, 52.0) - vec2(u, p.y));
	return min(min(ledge, fin), min(e.x + 4.5, e.y + 24.0));
}

// MAIN stands at the end of a pier out of the west wall, over nothing; the
// panel stands beside it on the top of a pillar that rises out of the abyss.
float pier(vec3 p)
{
	float walk = sdBox(p - vec3(-189.5, 9.4, -1.0), vec3(10.5, 0.6, 1.6));
	float end = sdBox(p - vec3(-178.7, 9.4, -1.2), vec3(2.3, 0.6, 2.0));
	// Its top sits a little under the slab's foot: the slab leans back with
	// the camera's pitch, and a flush top hid the panel's bottom lines.
	float pillar = sdBox(p - vec3(-175.0, -240.6, 0.7), vec3(1.7, 249.4, 1.6));
	return min(min(walk, end), pillar);
}

float bridge(vec3 p)
{
	vec3 q = p - vec3(BRIDGE_X, BRIDGE_Y - 0.75, 0.0);
	float deck = sdBox(q, vec3(3.0, 0.75, VOID_HALF));
	float rail = sdBox(vec3(abs(q.x) - 2.85, q.y - 1.25, q.z), vec3(0.08, 0.5, VOID_HALF));
	return min(deck, rail);
}

// One person, standing at the bridge rail, looking out.
float figure(vec3 p)
{
	vec3 q = p - FIGURE;
	if (dot(q, q) > 16.0)
		return length(q) - 3.0;
	float body = sdCapsule(q, vec3(0.0, 0.3, 0.0), vec3(0.0, 1.38, 0.0), 0.2);
	float head = length(q - vec3(0.0, 1.64, 0.0)) - 0.12;
	return min(body, head);
}

// The terrace's slab and stream bed, and the stream itself in `water`.
float terrace(vec3 p, out float water)
{
	vec3 q = p - vec3(148.0, TERR_Y - 3.0, 0.0);
	float slab = sdBox(q, vec3(52.0, 3.0, 70.0));
	float sz = p.z - streamZ(p.x);
	float chan = max(abs(sz) - 2.6, abs(p.y - TERR_Y) - 0.9);
	slab = max(slab, -chan);
	water = max(max(abs(sz) - 2.6, p.y - (TERR_Y - 0.35)), max(abs(q.x) - 52.0, abs(p.y - TERR_Y + 0.8) - 1.0));
	return slab;
}

// Trees: one jittered trunk per 12 m cell, flared at the root, a crown near
// the top; the four nearest cells are looked at, because crowns overlap.
// Clear of the stream and of the PLAY station.
#define TREE_CELL 12.0
float treeOne(vec2 q, float y, vec2 c, out float leaf)
{
	leaf = 1e5;
	vec2 h = hash22(c);
	vec2 ctr = (c + 0.2 + 0.6 * h) * TREE_CELL;
	if (abs(ctr.y - streamZ(ctr.x)) < 6.5 || length(ctr - vec2(140.0, -20.0)) < 10.0
	    || ctr.x < TERR_X0 + 5.0 || ctr.x > 194.0 || abs(ctr.y) > 64.0)
		return 1e5;
	float top = 44.0 + 26.0 * h.y;
	vec2 bend = vec2(sin(y * 0.05 + h.y * 6.0), cos(y * 0.043 + h.x * 5.0)) * 1.2;
	float r0 = 0.7 + 1.1 * h.x;
	float r = r0 * (1.0 + 1.8 * exp(-y * 0.45)) * (1.0 - 0.006 * y);
	vec2 tq = q - ctr - bend;
	float d = length(tq) - r - 0.05 * sin(atan(tq.y, tq.x) * 11.0 + y * 0.3);
	d = max(d, max(-y, y - top));
	vec3 cr = vec3(tq.x, y - top + 2.0, tq.y);
	float n = sin(cr.x * 0.9) * sin(cr.y * 1.1 + T * 0.2) * sin(cr.z * 0.8);
	leaf = (length(cr * vec3(1.0, 1.7, 1.0)) - 6.5 - 1.6 * h.x + n * 1.1) * 0.6;
	return d;
}
float trees(vec3 p, out float leaf)
{
	vec2 q = p.xz;
	float y = p.y - TERR_Y;
	vec2 b = floor(q / TREE_CELL - 0.5);
	float d = 1e5, l;
	leaf = 1e5;
	for (int i = ZERO; i < 4; i++)
	{
		vec2 c = b + vec2(float(i & 1), float(i >> 1));
		d = min(d, treeOne(q, y, c, l));
		leaf = min(leaf, l);
	}
	return d;
}

// Falling water: the stream's source out of the east wall, the stream again
// off the terrace's edge into the abyss, and two falls from high openings.
float falls(vec3 p)
{
	float src = sdBox(p - vec3(198.6, TERR_Y + 45.0, streamZ(198.0)), vec3(0.4, 45.0, 3.2));
	float off = sdBox(p - vec3(TERR_X0 - 0.8, TERR_Y - 500.0, streamZ(TERR_X0)), vec3(0.5, 500.0, 2.6));
	float high = sdBox(vec3(p.x - 198.8, p.y + 420.0, abs(p.z) - 112.0), vec3(0.4, 480.0, 4.5));
	return min(min(src, off), high);
}

// Towers of light: 5 x 3 at 8 m, each a stack of 3 m cubes; the band for the
// tower's column sets its height.  Their feet are lost in the abyss.
float towerBand(vec2 cell) { return spec(0.04 + (cell.x + 2.0) / 5.0 * 0.8 + (cell.y + 1.0) * 0.03); }
float towerTop(vec2 cell)  { return PLAT_Y + 4.0 + 12.0 * hash12(cell + 3.0) + 36.0 * towerBand(cell); }
float towers(vec3 p)
{
	vec3 q = p - TOWERS;
	vec2 cell = floor(q.xz / 8.0 + 0.5);
	vec2 l = q.xz - cell * 8.0;
	float d = 1e5;
	if (cell == clamp(cell, vec2(-2.0, -1.0), vec2(2.0, 1.0)))
	{
		float fy = mod(p.y - PLAT_Y, 4.0) - 2.0;
		d = max(sdBox(vec3(l.x, fy, l.y), vec3(1.45)) - 0.08, p.y - towerTop(cell));
	}
	vec2 e = 4.0 - abs(l);
	return min(d, min(e.x, e.y) + 2.4);      // a cube keeps 2.4 m clear of its cell's edge
}

// The flooded platform the towers are seen from, its walkway and its pier.
float platform(vec3 p, out float water)
{
	vec3 q = p - vec3(PLAT.x, PLAT_Y - 1.0, PLAT.z);
	float pad = sdBox(q, vec3(11.0, 1.0, 14.0));
	float walk = sdBox(q - vec3(0.0, 0.0, 45.0), vec3(2.2, 0.6, 32.0));
	float pier = sdBox(vec3(q.x, q.y + 60.0, q.z), vec3(3.0, 59.0, 3.0));
	water = sdBox(q - vec3(0.0, 1.02, 0.0), vec3(10.4, 0.03, 13.4));
	return min(min(pad, walk), pier);
}

// Material ids: 1 megastructure, 2 built concrete, 3 bark, 4 leaves, 5 terrace
// ground, 6 water, 7 falling water, 8 tower, 9 figure, 10/11 panels.
// Every group sits behind a box bound, so a step pays only for what it is near.
vec2 map(vec3 p)
{
	vec2 m = vec2(1e5, 1.0);
	float d, w, b;

	// Inside the corridor nothing but the bore can be nearer: its shell is solid.
	if (p.z > 196.0 && abs(p.x) < 13.0 && p.y > CORR_Y - 6.0 && p.y < CORR_Y + 22.0)
		m.x = -corridorEmpty(p);
	else
	{
		m.x = min(mega(p), wallDetail(p));

		b = max(max(abs(p.x + 187.0) - 14.0, abs(p.z) - 5.0), p.y - 12.0);
		if (b < m.x)
		{
			d = pier(p);
			if (d < m.x) m = vec2(d, 2.0);
		}
		b = max(abs(p.x - BRIDGE_X) - 4.0, abs(p.y - BRIDGE_Y) - 3.0);
		if (b < m.x)
		{
			d = bridge(p);  if (d < m.x) m = vec2(d, 2.0);
			d = figure(p);  if (d < m.x) m = vec2(d, 9.0);
		}
		b = sdBox(p - vec3(148.0, TERR_Y + 40.0, 0.0), vec3(54.0, 48.0, 72.0));
		if (b < m.x)
		{
			d = terrace(p, w);  if (d < m.x) m = vec2(d, 5.0);
			if (w < m.x) m = vec2(w, 6.0);
			d = trees(p, w);    if (d < m.x) m = vec2(d, 3.0);
			if (w < m.x) m = vec2(w, 4.0);
		}
		b = min(VOID_HALF - 8.0 - p.x, max(abs(p.x - TERR_X0) - 4.0, p.y - TERR_Y - 2.0));
		if (b < m.x)
		{
			d = falls(p);  if (d < m.x) m = vec2(d, 7.0);
		}
		b = max(max(abs(p.x - TOWERS.x) - 22.0, abs(p.z - TOWERS.z) - 14.0), p.y - PLAT_Y - 60.0);
		if (b < m.x)
		{
			d = towers(p);  if (d < m.x) m = vec2(d, 8.0);
		}
		b = sdBox(p - vec3(PLAT.x, PLAT_Y - 60.0, PLAT.z + 30.0), vec3(12.0, 62.0, 48.0));
		if (b < m.x)
		{
			d = platform(p, w);  if (d < m.x) m = vec2(d, 2.0);
			if (w < m.x) m = vec2(w, 6.0);
		}
	}
	return m;
}

vec3 calcNormal(vec3 p, float t)
{
	float h = 0.002 + 0.0008 * t;
	vec3 n = vec3(0.0);
	for (int i = ZERO; i < 4; i++)
	{
		vec3 e = 0.5773 * (2.0 * vec3(float(((i + 3) >> 1) & 1), float((i >> 1) & 1), float(i & 1)) - 1.0);
		n += e * map(p + e * h).x;
	}
	float l = length(n);
	return (l > 1e-8) ? n / l : vec3(0.0, 1.0, 0.0);
}

// ------------------------------------------------------------------- light --
vec3 fogCol(vec3 rd)
{
	vec3 c = mix(vec3(0.10, 0.13, 0.18), vec3(0.006, 0.012, 0.032), smoothstep(0.0, -0.5, rd.y));
	c = mix(c, vec3(0.62, 0.66, 0.72), smoothstep(0.05, 0.9, rd.y));
	c += vec3(1.0, 0.88, 0.68) * pow(max(dot(rd, SUN), 0.0), 10.0) * 0.6;
	return c;
}

// Height fog, integrated along the ray: thin above, thick in the abyss.
float fogAmount(vec3 ro, vec3 rd, float t)
{
	const float k = 0.011;
	float ry = (abs(rd.y) < 1e-4) ? 1e-4 : rd.y;
	float amt = 0.0036 * exp(-k * ro.y) * (1.0 - exp(-k * ry * t)) / (k * ry);
	return 1.0 - exp(-amt);
}

// Shafts of sun down the void, each placed by where it lands: on the bridge
// beside the figure, in the forest, the middle of the void, the towers.  Glow
// from the ray's closest approach to each axis -- closed form, no marching;
// they swell with the bass.
const vec4 BEAM[4] = vec4[4](vec4(FIGURE + vec3(0.5, 0.0, -1.5), 5.0),
                             vec4(150.0, TERR_Y, 30.0, 9.0),
                             vec4(-20.0, -150.0, 60.0, 12.0),
                             vec4(TOWERS.x - 6.0, PLAT_Y + 20.0, TOWERS.z + 8.0, 8.0));

float beamGlow(vec3 ro, vec3 rd, float tmax)
{
	vec3 D = -SUN;
	float g = 0.0;
	for (int i = 0; i < 4; i++)
	{
		vec3 bp = BEAM[i].xyz;
		float w = BEAM[i].w;
		vec3 w0 = ro - bp;
		float b = dot(rd, D), dd = dot(rd, w0), e = dot(D, w0);
		float den = max(1.0 - b * b, 1e-3);
		float tcl = clamp((b * e - dd) / den, 0.0, tmax);
		vec3 pc = ro + rd * tcl;
		vec3 v = pc - bp;
		float h2 = max(dot(v, v) - dot(v, D) * dot(v, D), 0.0);
		float above = smoothstep(bp.y - 4.0, bp.y + 2.0, pc.y);     // none below where it lands
		float flick = 0.75 + 0.25 * sin(T * (0.3 + 0.1 * float(i)) + float(i) * 2.0);
		g += exp(-h2 / (w * w)) * w / sqrt(den) * flick * above;
	}
	return g * (0.011 + 0.004 * AA.x);
}

// Sunlight where a shaft lands.
float beamLit(vec3 p)
{
	vec3 D = -SUN;
	float l = 0.0;
	for (int i = 0; i < 4; i++)
	{
		vec3 v = p - BEAM[i].xyz;
		float h2 = dot(v, v) - dot(v, D) * dot(v, D);
		l += smoothstep(BEAM[i].w * BEAM[i].w, 0.0, h2);
	}
	return l;
}

float vnoise2(vec2 p)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), f.x),
	           mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), f.x), f.y);
}

// Board-formed concrete: 2.4 x 1.2 m form panels with their seams and tie
// holes, run-off streaks, and moss where water sits.  `k` scales the pattern
// (the panels' slabs are small, and use a finer one).
vec3 concrete(vec3 p, vec3 n, float t, float k)
{
	vec3 an = abs(n);
	vec2 uv = ((an.x > an.y && an.x > an.z) ? p.zy : ((an.y > an.z) ? p.xz : p.xy)) * k;
	float big = vnoise2(uv * 0.035 + n.xz * 7.0);
	vec3 alb = vec3(0.44, 0.43, 0.41) * (0.8 + 0.35 * big);
	float det = 1.0 - smoothstep(40.0, 160.0, t);
	vec2 g = uv / vec2(2.4, 1.2);
	vec2 f = fract(g);
	vec2 dd = min(f, 1.0 - f) * vec2(2.4, 1.2);
	float seam = smoothstep(0.035, 0.0, min(dd.x, dd.y));
	vec2 th = fract(g * 2.0) - 0.5;
	float tie = smoothstep(0.045, 0.02, length(th * vec2(1.2, 0.6)));
	alb *= 1.0 - det * (0.35 * seam + 0.55 * tie);
	float moss;
	if (an.y < 0.5)
	{
		// Run-off: dark streaks down the walls, and now and then a curtain of
		// moss hanging where water comes out.
		alb *= 1.0 - 0.3 * smoothstep(0.55, 0.9, vnoise2(vec2(uv.x * 1.3, p.y * 0.04 * k)));
		moss = smoothstep(0.8, 0.95, vnoise2(vec2(uv.x * 0.7 + 31.0, p.y * 0.06 * k))) * 0.7;
	}
	else
		moss = smoothstep(0.66, 0.88, vnoise2(uv * 0.22) * 0.65 + big * 0.45) * step(0.5, n.y);
	return mix(alb, vec3(0.08, 0.17, 0.05) * (0.7 + 0.6 * vnoise2(uv * 3.0)), moss);
}

// One shading path for every material, so that concrete (which most of them
// are) is inlined once: this GPU runs a smaller shader nearly twice as fast
// for the same work (the lean-variant test, 40 -> 72 fps).
vec3 shade(vec3 p, vec3 rd, float id, float t, bool lite)
{
	if (id > 11.5)
		return vec3(0.004, 0.006, 0.01);
	vec3 n = (id > 9.5) ? PANN : calcNormal(p, t);

	vec3 alb = vec3(0.4);
	vec3 emit = vec3(0.0);
	float spc = 0.0;
	bool inCorr = p.z > 192.0 && abs(p.x) < 13.0 && p.y > CORR_Y - 4.0 && p.y < CORR_Y + 20.0;
	bool conc = id < 2.5 || (id > 4.5 && id < 5.5 && n.y < 0.6);
	float ck = 1.0;

	// The panels: the screen is dark glass with the UI in it, set in concrete
	// with a thin line of light around the glass.
	vec3 pl = vec3(0.0);
	vec2 PH = vec2(0.0);
	float PL = 0.0;
	if (id > 9.5)
	{
		bool a = id < 10.5;
		pl = a ? panLocal(p, PA_C, PA_R, PA_U, PA_N) : panLocal(p, PB_C, PB_R, PB_U, PB_N);
		PH = a ? PA_H : PB_H;
		PL = a ? PA_L : PB_L;
		if (pl.z > -0.03 && abs(pl.x) < PH.x + 0.01 && abs(pl.y) < PH.y + 0.01)
		{
			float fre = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 4.0);
			vec3 col = vec3(0.006, 0.008, 0.012) + fogCol(reflect(rd, n)) * (0.06 + 0.5 * fre);
			if (a)
				col += panEmit(s_ui0, pl, PH, PL) * 0.4;
			else
				col += panEmit(s_ui1, pl, PH, PL) * 0.4;
			return col;
		}
		conc = true;
		ck = 4.0;
	}

	if (conc)
		alb = concrete(p, n, t, ck);

	if (id > 9.5)
	{
		float e = max(abs(pl.x) - PH.x, abs(pl.y) - PH.y);
		emit = milk_pal(M_LOOK.x + 0.1) * smoothstep(0.025, 0.0, abs(e - 0.03)) * step(-0.05, pl.z)
		     * (0.6 + 0.6 * AA.w) * abs(PL);
	}
	else if (inCorr)
	{
		// The corridor's lights: a line down the middle of the floor, and one
		// round the inside of every portal frame, a wave running away from you
		// down the whole length.
		float zl = mod(p.z - 190.0, 10.0) - 5.0;
		float strip = smoothstep(0.18, 0.05, abs(p.x)) * step(0.5, n.y);
		float ring = smoothstep(0.12, 0.0, abs(abs(zl) - 0.8))
		           * step(abs(sdBox2(vec2(p.y - CORR_Y - 7.25, p.x), vec2(7.25, 5.4))), 0.25);
		float wave = 0.5 + 0.5 * sin(p.z * 0.06 - T * 2.0);
		vec3 lc = mix(vec3(1.0, 0.82, 0.55), milk_pal(M_LOOK.x + 0.1), 0.35);
		emit = lc * (strip * (0.8 + 1.4 * wave) + ring * (0.6 + 0.7 * AA.w) * (0.4 + 0.6 * wave));
	}
	else if (id < 1.5)
	{
		// Deep in a niche on the far walls: somebody's light is on.
		vec3 cell = floor(p / vec3(10.0, 13.333, 10.0));
		float h = hash13(cell);
		vec3 lq = mod(p, vec3(10.0, 13.333, 10.0)) - vec3(5.0, 6.667, 5.0);
		if (h > 0.94 && t > 60.0 && n.y < 0.3 && abs(lq.y) < 2.4 && min(abs(lq.x), abs(lq.z)) < 1.4)
			emit = mix(vec3(1.0, 0.72, 0.4), vec3(0.6, 0.8, 1.0), fract(h * 37.0)) * (1.4 + 1.2 * fract(h * 91.0));
	}
	else if (id > 2.5 && id < 3.5)
	{
		alb = vec3(0.15, 0.11, 0.08) * (0.7 + 0.6 * vnoise2(p.xz * 2.0 + p.y * 0.25));
		alb = mix(alb, vec3(0.07, 0.15, 0.04), smoothstep(0.55, 0.8, vnoise2(p.xy * 0.8)) * 0.8);
	}
	else if (id > 3.5 && id < 4.5)
	{
		float v = vnoise2(p.xz * 1.7 + p.y);
		alb = mix(vec3(0.04, 0.11, 0.03), vec3(0.15, 0.27, 0.06), v);
		emit = vec3(0.35, 0.5, 0.1) * pow(max(dot(rd, SUN), 0.0), 3.0) * 0.6 * v;    // sun through the leaves
	}
	else if (id > 4.5 && id < 5.5 && !conc)
	{
		float v = vnoise2(p.xz * 0.9) * 0.6 + vnoise2(p.xz * 4.1) * 0.4;
		alb = mix(vec3(0.045, 0.09, 0.03), vec3(0.15, 0.25, 0.06), v);
		alb += vec3(0.5, 0.55, 0.35) * step(0.985, hash12(floor(p.xz * 6.0))) * 0.6;   // flecks: flowers, or spores
	}
	else if (id > 5.5 && id < 7.5)
	{
		// Water, lying (foam running with the flow; the caller adds the
		// reflection) or falling (streaks racing down, lit through).
		bool fall = id > 6.5;
		vec2 fl = fall ? vec2(p.z * 1.4 + p.x * 1.4, p.y * 0.12 + T * 3.0) : vec2(p.x * 0.5 + T * 2.8, p.z * 1.2);
		float s = vnoise2(fl);
		alb = fall ? vec3(0.55, 0.62, 0.66) * (0.5 + 0.5 * s) : vec3(0.02, 0.05, 0.06);
		emit = vec3(0.4, 0.5, 0.55) * smoothstep(0.55, 0.9, s) * (fall ? 1.0 : 0.25);
	}
	else if (id > 7.5 && id < 8.5)
	{
		// A tower cube: glass lit from inside, its band's brightness.
		vec3 q = p - TOWERS;
		vec2 cell = clamp(floor(q.xz / 8.0 + 0.5), vec2(-2.0, -1.0), vec2(2.0, 1.0));
		float band = towerBand(cell);
		float top = towerTop(cell);
		float fre = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 3.0);
		vec3 tint = mix(vec3(0.45, 0.7, 1.0), milk_pal(M_LOOK.x + 0.12 + cell.x * 0.03), 0.35);
		vec3 r = abs(vec3(q.x - cell.x * 8.0, mod(p.y - PLAT_Y, 4.0) - 2.0, q.z - cell.y * 8.0));
		float mx = max(r.x, max(r.y, r.z));
		float mid = r.x + r.y + r.z - mx - min(r.x, min(r.y, r.z));
		float edge = smoothstep(1.25, 1.45, mid);
		float nearTop = smoothstep(top - 16.0, top, p.y);
		alb = vec3(0.02, 0.03, 0.05);
		emit = tint * (0.2 + 1.3 * band + edge * (0.7 + 2.2 * band) + fre * 0.5) * (0.3 + 0.7 * nearTop);
		spc = 1.0;
	}
	else if (id > 8.5 && id < 9.5)
		alb = vec3(0.12, 0.12, 0.13);           // the figure

	// The sun comes in at the top of the shaft; low down only the beams reach.
	// No shadow rays: the height does most of what they did, for a fraction
	// of the shader.
	vec3 sunC = vec3(1.0, 0.92, 0.78) * 2.6;
	vec3 skyC = vec3(0.20, 0.25, 0.34);
	float reach = inCorr ? 0.0 : smoothstep(20.0, 240.0, p.y);
	float dif = max(dot(n, SUN), 0.0);
	float bl = inCorr ? 0.0 : beamLit(p);
	float sky = inCorr ? 0.35 : 1.0;
	vec3 col = alb * (sunC * dif * max(reach, bl * 0.95) + skyC * (0.35 + 0.65 * n.y) * sky
	                  + vec3(0.025, 0.03, 0.045)) + emit;
	if (spc > 0.0 && !lite)
		col += pow(max(dot(reflect(rd, n), SUN), 0.0), 60.0) * vec3(1.0, 0.95, 0.85) * 0.8;
	return col;
}

// A ray 50 m into the walls stops there: the halls are unlit, fogged, and
// endless -- marching down them was two thirds of this pass's cost.  Id 12 is
// that darkness.  The corridor is the one bore that is meant to be followed.
// A miss returns minus the distance reached, for the corridor's dark.
float march(vec3 ro, vec3 rd, float tmax, int steps, out float id)
{
	float t = 0.05;
	id = 0.0;
	for (int i = 0; i < 160; i++)
	{
		if (i >= steps)
			break;
		vec3 q = ro + rd * t;
		if (max(abs(q.x), abs(q.z)) > VOID_HALF + 50.0 && !(q.z > 196.0 && abs(q.x) < 13.0 && abs(q.y - CORR_Y - 8.0) < 12.0))
		{
			id = 12.0;
			return t;
		}
		vec2 m = map(q);
		if (m.x < 0.0008 * t + 0.002)
		{
			id = m.y;
			return t;
		}
		t += m.x * 0.95;
		if (t > tmax)
			break;
	}
	return -t;
}

void main(void)
{
	T = M_TIME.x;
	AA = M_AUDIOATT * M_FOCUS.w;
	QUAL = M_EXTRA.z;
	SUN = normalize(vec3(0.32, 1.0, 0.24));
	panInit();
	// Slabs stand on whatever floor is under their station.
	float fa = (PA_C.x < -150.0) ? 8.8 : ((PA_C.z > 150.0) ? CORR_Y : ((PA_C.x > 90.0) ? TERR_Y : PLAT_Y));
	float fb = (PB_C.x < -150.0) ? 8.8 : ((PB_C.z > 150.0) ? CORR_Y : ((PB_C.x > 90.0) ? TERR_Y : PLAT_Y));
	PA_EXT = max(0.0, (PA_C.y - (PA_H.y + PANEL_RIM) * PA_U.y - fa) / max(PA_U.y, 0.2));
	PB_EXT = max(0.0, (PB_C.y - (PB_H.y + PANEL_RIM) * PB_U.y - fb) / max(PB_U.y, 0.2));

	vec2 uv = tc * 2.0 - 1.0;
	uv.y = -uv.y;
	vec3 ro = M_CAMPOS.xyz;
	CAM = ro;
	vec3 rd = normalize(M_CAMFWD.xyz + uv.x * M_TIME.z * M_CAMPOS.w * M_CAMRIGHT.xyz
	                                 + uv.y * M_CAMPOS.w * M_CAMUP.xyz);

	int steps  = (QUAL >= 3.0) ? 120 : ((QUAL >= 2.0) ? 90 : 64);
	int rsteps = (QUAL >= 3.0) ? 40 : ((QUAL >= 2.0) ? 24 : 16);
	float tmax = 1100.0;

	// One call site for march and shade -- the second pass is the water's
	// reflection -- so each is inlined once.
	vec3 col = vec3(0.0);
	float mask = 0.0;
	float t0 = tmax, te = tmax;
	vec3 o = ro, d = rd;
	float wgt = 1.0;
	for (int b = ZERO; b < 2; b++)
	{
		// The panels' slabs are boxes, intersected here; the march stops at them.
		float id, pw;
		vec3 pn;
		float tb = (b == 0) ? tmax : 400.0;
		float tp = panTrace(o, d, PA_EXT, PB_EXT, pn, pw);
		float t = march(o, d, min(tb, tp), (b == 0) ? steps : rsteps, id);
		if (t <= 0.0 && tp < tb)
		{
			t = tp;
			id = (pw > 0.0) ? 10.0 : 11.0;
			PANN = pn;
		}
		vec3 c;
		if (t > 0.0)
		{
			c = shade(o + d * t, d, id, t, b > 0);
			if (b > 0)
				c = mix(c, fogCol(d), fogAmount(o, d, t));
		}
		else
			c = fogCol(d);
		col += c * wgt;
		if (b == 0)
		{
			t0 = (t > 0.0) ? t : tmax;
			te = abs(t);
			if (t > 0.0 && id > 9.5 && id < 11.5)
				mask = (id < 10.5) ? 1.0 : -1.0;
			// Water reflects: the stream the trees, the platform the towers.
			if (t <= 0.0 || id < 5.5 || id > 6.5)
				break;
			vec3 p = o + d * t;
			vec3 n = vec3(0.0, 1.0, 0.0);
			n.xz += 0.02 * vec2(sin(p.x * 3.0 + T * 2.0), sin(p.z * 2.5 - T * 1.7)) * (0.5 + AA.x);
			n = normalize(n);
			float fre = 0.02 + 0.98 * pow(1.0 - clamp(dot(n, -d), 0.0, 1.0), 5.0);
			wgt = 0.35 + 0.65 * fre;
			o = p + n * 0.05;
			d = reflect(d, n);
		}
	}
	float t = t0;

	// The corridor is bored into solid concrete: its air is dark, not the
	// void's daylit haze, and a ray that runs out of steps down it ends in that
	// dark -- drawn as haze, it was a grey wedge at the far end.  Squared, so
	// the near corridor stays clear and the far end is gone by ~120 m.
	float fog;
	vec3 pe = ro + rd * min(te, tmax);
	if (pe.z > 196.0 && abs(pe.x) < 13.0 && pe.y > CORR_Y - 6.0 && pe.y < CORR_Y + 22.0)
	{
		float tin = max(0.0, (192.0 - ro.z) / max(rd.z, 1e-3));
		float dc = max(te - tin, 0.0) * 0.018;
		float cf = (t < tmax) ? 1.0 - exp(-dc * dc) : 1.0;
		col = mix(col, vec3(0.004, 0.005, 0.008), cf);
		float vf = fogAmount(ro, rd, tin);
		col = mix(col, fogCol(rd), vf);
		fog = 1.0 - (1.0 - vf) * (1.0 - cf);
	}
	else
	{
		fog = (t >= tmax) ? 1.0 : fogAmount(ro, rd, t);
		col = mix(col, fogCol(rd), fog);
	}
	col += vec3(1.0, 0.92, 0.78) * beamGlow(ro, rd, t);

	gl_FragColor = vec4(col, mask * (1.0 - fog));
}
#endif
