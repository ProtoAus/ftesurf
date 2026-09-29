!!ver 130 150
!!samps prev=0 spec=1 ui0=2 ui1=3

// Patch 467 -- the menu's 3D space, raymarched at the milk internal size.
//
// Four landmarks share one space so the camera can fly between them (Melee's
// menu, but abstract): the cube lattice (main), the tower field whose heights
// ARE the spectrum (play), the ring tunnel (visuals) and the liquid pool
// (music).  Everything is analytic or an SDF; nothing is loaded, so this runs
// in menu.dat, where clearscene forces RDF_NOWORLDMODEL (pr_menu.c:2146) and a
// BSP cannot be drawn.  Each landmark hides behind a bounding volume, so only
// the ones near a ray cost anything.
//
// s_prev is the previous feedback frame (the pool's liquid normal); s_spec is
// the snd_visimage spectrum (row 0 = bands, row 1 = waveform); s_ui0/s_ui1 are
// the menu panels' UI (milk_panel.h) -- black glass monoliths standing on the
// floor, their faces lit by the UI, reflected in the tiles.  Alpha out is the
// panel mask milk_present.glsl #PANELS reads.

#include "sys/defs.h"
#include "glsl/milk_common.h"
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

float T;
vec4  AA;
mat3  CROT;
float QUAL;
float PA_EXT, PB_EXT;          // how far each slab reaches down to the floor

float spec(float x) { return texture2D(s_spec, vec2(clamp(x, 0.02, 0.98), 0.25)).r; }

// ---------------------------------------------------------------- landmarks --
// Cube lattice: 3x3x3 rounded cubes, spacing breathing with the bass.
float cubeD(vec3 p)
{
	vec3 q = p - ST_CUBE;
	if (dot(q, q) > 36.0)
		return length(q) - 5.0;
	q = CROT * q;
	float s = 1.12 + 0.10 * AA.x;
	vec3 id = clamp(floor(q / s + 0.5), -1.0, 1.0);
	return sdBox(q - id * s, vec3(0.33)) - 0.06;
}

// Tower field: one box per 2.4 u cell inside a 30 u disc.  Height is a hash
// plus the spectrum band for the cell's ring, so the city IS the music.
#define TW_CELL 2.4
#define TW_RAD  30.0
float towerH(vec2 cell)
{
	float rr = length(cell) * (TW_CELL / TW_RAD);
	if (rr > 1.0)
		return 0.0;
	float h = hash12(cell + 17.0);
	return 0.5 + 2.4 * h * h + 5.0 * spec(0.04 + rr * 0.8) * (1.0 - 0.45 * rr);
}
float towersD(vec3 p)
{
	vec2 q = p.xz - ST_TOWERS.xz;
	float rq = length(q);
	if (rq > TW_RAD + 3.0)
		return rq - TW_RAD - 2.0;
	if (p.y > 9.0)
		return p.y - 8.4;
	vec2 cell = floor(q / TW_CELL + 0.5);
	vec2 l = q - cell * TW_CELL;
	float h = towerH(cell);
	float d = sdBox(vec3(l.x, p.y - h * 0.5, l.y), vec3(0.55, max(h * 0.5, 0.01), 0.55));
	// A neighbour can be taller than this cell's tower, so never step far past
	// the cell wall -- but a tower keeps 0.65 u clear of its cell's edge, so
	// that far past is safe.  At +0.1 rays crawled along every cell boundary.
	vec2 e = TW_CELL * 0.5 - abs(l);
	return min(d, min(e.x, e.y) + 0.6);
}

// Ring tunnel along +z: an open tube, glowing rings every 3 u, twelve ribs.
float tunnelD(vec3 p, out float ringd)
{
	vec3 q = p - ST_TUNNEL;
	ringd = 1e5;
	if (q.z < -8.0 || dot(q.xy, q.xy) > 49.0)
	{
		float b = max(length(q.xy) - 6.0, -8.0 - q.z);
		return max(b, 0.5);
	}
	float r = length(q.xy);
	float tube = max(abs(r - 4.7) - 0.35, -(q.z + 2.0));
	float z = mod(q.z, 3.0) - 1.5;
	ringd = (q.z > -1.5) ? length(vec2(r - 4.15, z)) - 0.09 : 1e5;
	float a = atan(q.y, q.x);
	float seg = mod(a + T * 0.05, TAU / 12.0) - TAU / 24.0;
	float rib = (q.z > -2.0) ? sdBox(vec3(r - 4.35, seg * r, 0.0), vec3(0.12, 0.05, 1e3)) : 1e5;
	return min(min(tube, rib), ringd);
}

// Twelve orbs circling the pool, riding the spectrum, mirrored in the water.
// Angular repetition: only the nearest orb is evaluated.
#define ORB_N   12.0
#define ORB_R   7.5
float orbsD(vec3 p, out float oid)
{
	vec3 q = p - ST_POOL;
	oid = 0.0;
	float rq = length(q.xz);
	if (rq > ORB_R + 3.0 || q.y > 7.5)
		return max(max(rq - ORB_R - 2.0, q.y - 6.8), 0.3);
	float seg = TAU / ORB_N;
	float a = atan(q.z, q.x) + T * 0.15;
	float idx = floor(a / seg + 0.5);
	float la = a - idx * seg;
	oid = mod(idx, ORB_N);
	float band = spec(0.05 + oid / ORB_N * 0.8);
	float h = 1.9 + 0.35 * sin(T * 0.9 + oid * 1.7) + 2.4 * band;
	vec2 lp = vec2(rq * cos(la) - ORB_R, rq * sin(la));
	return length(vec3(lp.x, q.y - h, lp.y)) - (0.42 + 0.22 * band);
}

// Everything but the floor, which is analytic.  .y is a material id.
vec2 map(vec3 p)
{
	float rd, oid;
	vec2 m = vec2(cubeD(p), 1.0);
	float t = towersD(p);
	if (t < m.x) m = vec2(t, 2.0);
	t = tunnelD(p, rd);
	if (t < m.x) m = vec2(t, (rd <= t + 1e-3) ? 4.0 : 3.0);
	t = orbsD(p, oid);
	if (t < m.x) m = vec2(t, 5.0);
	return m;
}

vec3 calcNormal(vec3 p)
{
	const vec2 k = vec2(1.0, -1.0);
	const float h = 0.0015;
	return normalize(k.xyy * map(p + k.xyy * h).x + k.yyx * map(p + k.yyx * h).x +
	                 k.yxy * map(p + k.yxy * h).x + k.xxx * map(p + k.xxx * h).x);
}

// ------------------------------------------------------------- environment --
vec3 skyCol(vec3 rd)
{
	float up = clamp(rd.y, 0.0, 1.0);
	vec3 c = mix(vec3(0.060, 0.030, 0.130), vec3(0.004, 0.005, 0.018), sqrt(up));
	float n = vnoise(rd * 2.6 + vec3(0.0, T * 0.012, T * 0.007));
	n = n * 0.65 + 0.35 * vnoise(rd * 6.3 - vec3(T * 0.02, 0.0, 0.0));
	c += milk_pal(n * 0.7 + M_LOOK.x + 0.3) * pow(n, 3.5) * (0.10 + 0.05 * AA.y);
	vec3 sp = rd * 160.0;
	vec3 si = floor(sp);
	float h = hash13(si);
	if (h > 0.982)
	{
		vec3 f = fract(sp) - 0.5;
		float tw = 0.55 + 0.45 * sin(T * (2.0 + 5.0 * h) + h * 90.0);
		c += vec3(0.75, 0.82, 1.0) * exp(-dot(f, f) * 55.0) * tw * (0.6 + 0.3 * AA.z);
	}
	return c;
}

vec3 fogCol(vec3 rd)
{
	return mix(vec3(0.050, 0.028, 0.110), vec3(0.020, 0.030, 0.070), clamp(rd.y * 2.0 + 0.5, 0.0, 1.0));
}

vec3 matGlow(float id, vec3 p)
{
	if (id < 1.5) return milk_pal(M_LOOK.x + 0.05);
	if (id < 2.5) return milk_pal(M_LOOK.x + 0.35 + length(p.xz - ST_TOWERS.xz) * 0.01);
	if (id > 4.5) return milk_pal(M_LOOK.x + 0.9 + atan(p.z - ST_POOL.z, p.x - ST_POOL.x) * 0.08);
	return milk_pal(M_LOOK.x + 0.72 + (p.z - ST_TUNNEL.z) * 0.015);
}

// A panel's slab: black glass, the UI on its face, a thin frame of light.
vec3 shadePanel(vec3 p, vec3 rd, vec3 n, bool a)
{
	vec3 l = a ? panLocal(p, PA_C, PA_R, PA_U, PA_N) : panLocal(p, PB_C, PB_R, PB_U, PB_N);
	vec2 H = a ? PA_H : PB_H;
	float L = a ? PA_L : PB_L;
	float fre = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 4.0);
	vec3 col = vec3(0.004, 0.005, 0.010) + skyCol(reflect(rd, n)) * (0.25 + 0.75 * fre);
	if (l.z > -0.03)
	{
		if (a)
			col += panEmit(s_ui0, l, H, L) * 0.35;
		else
			col += panEmit(s_ui1, l, H, L) * 0.35;
		float e = max(abs(l.x) - H.x, abs(l.y) - H.y);
		col += milk_pal(M_LOOK.x + 0.1) * smoothstep(0.03, 0.0, abs(e - 0.045)) * (0.35 + 0.5 * AA.w) * abs(L);
	}
	return col;
}

// Shade an object hit.  `lite` skips the specular and the extra lookups for
// the reflection bounce.
vec3 shadeHit(vec3 p, vec3 rd, float id, bool lite)
{
	vec3 n = calcNormal(p);
	vec3 L = normalize(vec3(-0.5, 0.8, -0.35));
	float dif = clamp(dot(n, L), 0.0, 1.0);
	float fre = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 4.0);
	vec3 base = vec3(0.020, 0.022, 0.040);
	vec3 glow = matGlow(id, p);
	vec3 col = base * (0.2 + dif) + fre * glow * 0.35;
	float emit = 0.0;

	if (id < 1.5)
	{
		// Cube: bright edges, a body glow per cube driven by its own band.
		vec3 q = CROT * (p - ST_CUBE);
		float s = 1.12 + 0.10 * AA.x;
		vec3 cid = clamp(floor(q / s + 0.5), -1.0, 1.0);
		vec3 r = abs(q - cid * s);
		float mx = max(r.x, max(r.y, r.z));
		float mid = r.x + r.y + r.z - mx - min(r.x, min(r.y, r.z));
		float edge = smoothstep(0.26, 0.37, mid);
		float idx = dot(cid + 1.0, vec3(1.0, 3.0, 9.0));
		float band = spec(0.03 + idx / 27.0 * 0.9);
		glow = milk_pal(M_LOOK.x + idx * 0.021);
		emit = edge * (0.6 + 2.2 * band) + 0.10 + 0.9 * band * band;
	}
	else if (id < 2.5)
	{
		// Tower: stacked-block seams and a hot top face.
		vec2 q = p.xz - ST_TOWERS.xz;
		vec2 cell = floor(q / TW_CELL + 0.5);
		float h = towerH(cell);
		float seam = smoothstep(0.08, 0.0, abs(fract(p.y * 1.25) - 0.5) - 0.40);
		float top = step(0.8, n.y) * smoothstep(h - 0.05, h, p.y);
		float band = spec(0.04 + length(cell) * (TW_CELL / TW_RAD) * 0.8);
		emit = seam * (0.25 + 0.8 * band) + top * (1.2 + 3.0 * band);
	}
	else if (id < 3.5)
	{
		// Tunnel wall: faint hex cells that light up with the mids.
		vec3 q = p - ST_TUNNEL;
		float a = atan(q.y, q.x) * 6.0 / PI;
		vec2 hx = vec2(a, q.z * 0.8);
		float cellv = abs(fract(hx.x + 0.5 * floor(hx.y)) - 0.5) + abs(fract(hx.y) - 0.5);
		emit = smoothstep(0.52, 0.46, cellv) * (0.08 + 0.6 * AA.y * M_FOCUS.w);
	}
	else if (id < 4.5)
	{
		// Ring: pulses on the big hits, colour walks down the tunnel.
		emit = 2.0 + 1.5 * AA.w;
	}
	else
	{
		// Orb: a hot core under a glassy skin, brighter with its own band.
		float oid;
		orbsD(p, oid);
		float band = spec(0.05 + oid / ORB_N * 0.8);
		emit = 0.7 + 2.6 * band + 1.8 * pow(clamp(dot(n, -rd), 0.0, 1.0), 3.0);
	}

	col += glow * emit;
	if (!lite)
	{
		vec3 h = normalize(L - rd);
		col += pow(clamp(dot(n, h), 0.0, 1.0), 48.0) * vec3(0.6, 0.65, 0.8) * 0.5;
	}
	return col;
}

// March objects only.  Returns t (or -1) and the material in id.
// Near misses feed the halo -- most of the "PS2 intro" softness.  It is
// accumulated as a scalar and coloured once, by the material the ray came
// closest to: colouring per step cost three cos() on every step.
float march(vec3 ro, vec3 rd, float tmax, int steps, out float id, inout vec3 glow)
{
	float t = 0.02;
	float gw = 0.0;
	float dmin = 1e5;
	vec3 pmin = ro;
	float idmin = 1.0;
	id = 0.0;
	for (int i = 0; i < 128; i++)
	{
		if (i >= steps)
			break;
		vec3 p = ro + rd * t;
		vec2 m = map(p);
		gw += 0.012 / (0.012 + m.x * m.x * 6.0);
		if (m.x < dmin)
		{
			dmin = m.x;
			pmin = p;
			idmin = m.y;
		}
		if (m.x < 0.0015 * t)
		{
			id = m.y;
			glow += matGlow(idmin, pmin) * gw * 0.018;
			return t;
		}
		t += m.x * 0.92;
		if (t > tmax)
			break;
	}
	glow += matGlow(idmin, pmin) * gw * 0.018;
	return -1.0;
}

// Pool surface height: rings pushed out by the bass, slow drifting swell.
float poolH(vec2 q)
{
	float r = length(q);
	return 0.05 * sin(r * 3.4 - T * 2.6) * (0.35 + 0.9 * AA.x * M_FOCUS.w) / (1.0 + 0.25 * r)
	     + 0.035 * vnoise(vec3(q * 0.9, T * 0.35));
}

void main(void)
{
	T = M_TIME.x;
	AA = M_AUDIOATT * M_FOCUS.w;
	QUAL = M_EXTRA.z;
	panInit();
	PA_EXT = max(0.0, (PA_C.y - (PA_H.y + PANEL_RIM) * PA_U.y) / max(PA_U.y, 0.2));
	PB_EXT = max(0.0, (PB_C.y - (PB_H.y + PANEL_RIM) * PB_U.y) / max(PB_U.y, 0.2));

	float a1 = T * 0.21, a2 = T * 0.13 + 0.6;
	mat3 ry = mat3(cos(a1), 0.0, -sin(a1), 0.0, 1.0, 0.0, sin(a1), 0.0, cos(a1));
	mat3 rx = mat3(1.0, 0.0, 0.0, 0.0, cos(a2), sin(a2), 0.0, -sin(a2), cos(a2));
	CROT = rx * ry;

	vec2 uv = tc * 2.0 - 1.0;
	uv.y = -uv.y;
	vec3 ro = M_CAMPOS.xyz;
	vec3 rd = normalize(M_CAMFWD.xyz + uv.x * M_TIME.z * M_CAMPOS.w * M_CAMRIGHT.xyz
	                                 + uv.y * M_CAMPOS.w * M_CAMUP.xyz);

	int steps  = (QUAL >= 3.0) ? 110 : ((QUAL >= 2.0) ? 84 : 60);
	int rsteps = (QUAL >= 3.0) ? 56  : ((QUAL >= 2.0) ? 40 : 24);

	// The floor is a plane, so the march can stop where it would hit it.
	float tf = (rd.y < -1e-4) ? -ro.y / rd.y : 1e5;
	float tmax = min(tf, 140.0);

	// The panels' slabs are boxes, intersected here; the march stops at them.
	vec3 pn;
	float pw;
	float tp = panTrace(ro, rd, PA_EXT, PB_EXT, pn, pw);

	vec3 glow = vec3(0.0);
	float id;
	float t = march(ro, rd, min(tmax, tp), steps, id, glow);
	vec3 col;
	float mask = 0.0;

	if (t > 0.0)
		col = shadeHit(ro + rd * t, rd, id, false);
	else if (tp < tmax)
	{
		t = tp;
		col = shadePanel(ro + rd * tp, rd, pn, pw > 0.0);
		mask = pw;
	}
	else if (tf < 140.0)
	{
		t = tf;
		vec3 p = ro + rd * tf;
		vec2 pq = p.xz - ST_POOL.xz;
		float pr = length(pq);
		vec3 n = vec3(0.0, 1.0, 0.0);
		bool pool = pr < 13.0;
		if (pool)
		{
			const float e = 0.05;
			float h0 = poolH(pq);
			n = normalize(vec3(h0 - poolH(pq + vec2(e, 0.0)), e, h0 - poolH(pq + vec2(0.0, e))));
			// MilkDrop's liquid, in 3D: last tick's trails bend the surface
			// normal, so light smearing across the frame ripples the water.
			vec2 px = 2.0 / vec2(textureSize(s_prev, 0));
			float gx = lum(texture2D(s_prev, tc + vec2(px.x, 0.0)).rgb) - lum(texture2D(s_prev, tc - vec2(px.x, 0.0)).rgb);
			float gy = lum(texture2D(s_prev, tc + vec2(0.0, px.y)).rgb) - lum(texture2D(s_prev, tc - vec2(0.0, px.y)).rgb);
			n = normalize(n + vec3(gx, 0.0, -gy) * 0.35 * M_EVENT.y);
		}
		else
		{
			// Glossy tiles: a faint grid, bent a little by the bass so the
			// floor's reflection shimmers with the music.
			n = normalize(vec3(0.012 * sin(p.x * 1.7 + T) * AA.x, 1.0, 0.012 * sin(p.z * 1.9 - T) * AA.x));
		}
		vec3 rr = reflect(rd, n);
		float rid;
		vec3 rglow = vec3(0.0);
		vec3 rn;
		float rw;
		float rtp = panTrace(p + n * 0.02, rr, PA_EXT, PB_EXT, rn, rw);
		float rt = march(p + n * 0.02, rr, min(70.0, rtp), rsteps, rid, rglow);
		vec3 refl = (rt > 0.0) ? shadeHit(p + rr * rt, rr, rid, true)
		          : ((rtp < 70.0) ? shadePanel(p + n * 0.02 + rr * rtp, rr, rn, rw > 0.0) : skyCol(rr));
		refl += rglow;
		float fre = 0.04 + 0.96 * pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), 5.0);

		if (pool)
		{
			vec3 deep = milk_pal(M_LOOK.x + 0.55) * 0.05 + vec3(0.0, 0.02, 0.04);
			col = mix(deep, refl, 0.6 + 0.4 * fre);
			float sparkle = pow(max(dot(reflect(rd, n), normalize(vec3(-0.3, 0.9, 0.2))), 0.0), 90.0);
			col += sparkle * (0.8 + 0.6 * AA.z) * vec3(0.8, 0.9, 1.0);
			col += milk_pal(M_LOOK.x + 0.9) * smoothstep(13.0, 12.6, pr) * smoothstep(12.2, 12.6, pr) * (0.8 + 1.0 * AA.w);
		}
		else
		{
			vec2 g = abs(fract(p.xz * 0.5) - 0.5);
			float line = smoothstep(0.03, 0.0, min(g.x, g.y) - 0.005);
			vec3 base = vec3(0.012, 0.012, 0.022) + line * milk_pal(M_LOOK.x + 0.4) * 0.05;
			col = mix(base, refl, (0.18 + 0.6 * fre));
			// The panels' light pooling on the tiles in front of them.
			col += mix(vec3(0.6, 0.65, 0.8), milk_pal(M_LOOK.x + 0.1), 0.6) * 0.05
			     * (panSpill(p, PA_C, PA_R, PA_U, PA_N, PA_H, PA_L) + panSpill(p, PB_C, PB_R, PB_U, PB_N, PB_H, PB_L));
		}
	}
	else
	{
		col = skyCol(rd);
		t = 140.0;
	}

	// Distance fog into the horizon colour, then the halo on top of it.
	float fog = 1.0 - exp(-t * 0.028);
	col = mix(col, fogCol(rd), fog);
	col += glow;

	gl_FragColor = vec4(col, mask * (1.0 - fog));
}
#endif
