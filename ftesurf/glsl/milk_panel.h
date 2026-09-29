// milk_panel.h -- the menu's in-world panels.  src/menu/m_milk.qc writes
// w_user[12..15] (MM_PanelPack); a world shader raymarches each panel as the
// face of a slab, and milk_present.glsl #PANELS draws the same UI texture
// crisply over that face.
//
// A panel is a rectangle centred on C, facing N, half-size H.  Its UI texture
// has u to the right and v DOWN, like the 2D layout drawn into it.  H.x 0 = no
// panel in that slot.  A draws $rt:mm_ui0 and B $rt:mm_ui1; which of the two is
// the current station's alternates with every flight.

#define M_PANA   w_user[12]   // xyz centre  w lit: 0..1 powering up, -1..0 collapsing
#define M_PANA2  w_user[13]   // x yaw  y pitch of the facing (radians)  zw half-size

#define M_PANB   w_user[14]
#define M_PANB2  w_user[15]

#ifndef PANEL_RIM
#define PANEL_RIM   0.10
#endif
#ifndef PANEL_THICK
#define PANEL_THICK 0.14
#endif

vec3 PA_C, PA_R, PA_U, PA_N;  vec2 PA_H;  float PA_L;
vec3 PB_C, PB_R, PB_U, PB_N;  vec2 PB_H;  float PB_L;

// The facing from yaw/pitch, and the right/up a viewer looking along -N has --
// the same basis m_milk.qc's camera builds, so a panel laid out face-on to a
// camera gets exactly that camera's right and up.
void panFrame(vec4 a, vec4 b, out vec3 C, out vec3 R, out vec3 U, out vec3 N, out vec2 H, out float L)
{
	float cy = cos(b.x), sy = sin(b.x), cp = cos(b.y), sp = sin(b.y);
	C = a.xyz;
	N = vec3(sy * cp, sp, cy * cp);
	R = vec3(-cy, 0.0, sy);
	U = cross(-N, R);
	H = b.zw;
	L = a.w;
}

void panInit(void)
{
	panFrame(M_PANA, M_PANA2, PA_C, PA_R, PA_U, PA_N, PA_H, PA_L);
	panFrame(M_PANB, M_PANB2, PB_C, PB_R, PB_U, PB_N, PB_H, PB_L);
}

// Panel space: x right, y up, z out of the face toward the viewer.
vec3 panLocal(vec3 p, vec3 C, vec3 R, vec3 U, vec3 N)
{
	vec3 d = p - C;
	return vec3(dot(d, R), dot(d, U), dot(d, N));
}

vec2 panUV(vec3 l, vec2 H) { return vec2(0.5 + 0.5 * l.x / H.x, 0.5 - 0.5 * l.y / H.y); }

bool panInside(vec2 uv) { return uv.x >= 0.0 && uv.x <= 1.0 && uv.y >= 0.0 && uv.y <= 1.0; }

// Where a ray meets the panel's plane from the front: t, or -1.
float panRay(vec3 ro, vec3 rd, vec3 C, vec3 N)
{
	float den = dot(rd, N);
	return (den < -1e-4) ? dot(C - ro, N) / den : -1.0;
}

// Power up / down.  lit 0..1: a scan wipes the picture in from the top.
// lit -1..0: a CRT collapse as -lit runs 1 -> 0, squeezed to a line, then a
// dot.  Returns the uv to sample in .xy, the picture's gain in .z, and the
// scan line's own glow in .w.
vec4 panReveal(vec2 uv, float lit)
{
	if (lit >= 0.999)
		return vec4(uv, 1.0, 0.0);
	if (lit >= 0.0)
	{
		float head = lit * 1.2 - 0.1;
		float vis = smoothstep(head + 0.015, head - 0.015, uv.y);
		float line = exp(-abs(uv.y - head) * 90.0) * (1.0 - lit);
		return vec4(uv, vis, line * 2.0);
	}
	float x = -lit;
	float sy = clamp((x - 0.3) / 0.7, 0.003, 1.0);
	float sx = clamp(x / 0.3, 0.0, 1.0);
	vec2 q = (uv - 0.5) / vec2(max(sx, 1e-3), sy);
	float inside = step(abs(q.x), 0.5) * step(abs(q.y), 0.5);
	return vec4(q + 0.5, inside * (1.0 + 3.0 * (1.0 - sy)), 0.0);
}

// The slab behind a face is a box -- panel-space z from -2 PANEL_THICK to 0 (the
// face), the rim framing the UI rectangle, `ext` stretching it down to a floor
// -- so it is intersected, not marched: a world's march stops at the slab's t
// and the slab is never in its map().  In the map it cost the lattice 4 ms a
// frame on an N100 (75 -> 107 fps without it).  Returns t, or 1e9; the world
// normal of the face entered in n.
float panBox(vec3 ro, vec3 rd, vec3 C, vec3 R, vec3 U, vec3 N, vec2 H, float ext, out vec3 n)
{
	n = N;
	if (H.x <= 0.0)
		return 1e9;
	vec3 o = panLocal(ro, C, R, U, N);
	vec3 d = vec3(dot(rd, R), dot(rd, U), dot(rd, N));
	vec3 inv = 1.0 / (d + step(abs(d), vec3(1e-9)) * 1e-9);
	vec3 t0 = (vec3(-H.x - PANEL_RIM, -H.y - PANEL_RIM - ext, -2.0 * PANEL_THICK) - o) * inv;
	vec3 t1 = (vec3(H.x + PANEL_RIM, H.y + PANEL_RIM, 0.0) - o) * inv;
	vec3 tn3 = min(t0, t1);
	vec3 tf3 = max(t0, t1);
	float tn = max(max(tn3.x, tn3.y), tn3.z);
	float tf = min(min(tf3.x, tf3.y), tf3.z);
	if (tn > tf || tn <= 0.0)
		return 1e9;
	vec3 ln = (tn == tn3.x) ? vec3(-sign(d.x), 0.0, 0.0) : ((tn == tn3.y) ? vec3(0.0, -sign(d.y), 0.0) : vec3(0.0, 0.0, -sign(d.z)));
	n = ln.x * R + ln.y * U + ln.z * N;
	return tn;
}

// The nearer of the two slabs: t (1e9 = neither), normal, and which (+1 A, -1 B).
float panTrace(vec3 ro, vec3 rd, float extA, float extB, out vec3 n, out float which)
{
	vec3 na, nb;
	float ta = panBox(ro, rd, PA_C, PA_R, PA_U, PA_N, PA_H, extA, na);
	float tb = panBox(ro, rd, PB_C, PB_R, PB_U, PB_N, PB_H, extB, nb);
	which = (ta <= tb) ? 1.0 : -1.0;
	n = (ta <= tb) ? na : nb;
	return min(ta, tb);
}

// The picture as the raymarch sees it -- emission for the slab's face and for
// whatever reflects it.  The scene target is a third the screen's size, so a
// five-tap cross stands in for the mip chain render targets do not have.
vec3 panEmit(sampler2D ui, vec3 l, vec2 H, float lit)
{
	vec2 uv = panUV(l, H);
	if (!panInside(uv))
		return vec3(0.0);
	vec4 r = panReveal(uv, lit);
	vec2 o = 2.0 / vec2(textureSize(ui, 0));
	vec3 t = texture2D(ui, r.xy).rgb * 0.4
	       + (texture2D(ui, r.xy + vec2(o.x, 0.0)).rgb + texture2D(ui, r.xy - vec2(o.x, 0.0)).rgb
	        + texture2D(ui, r.xy + vec2(0.0, o.y)).rgb + texture2D(ui, r.xy - vec2(0.0, o.y)).rgb) * 0.15;
	return t * r.z + vec3(0.55, 0.75, 1.0) * r.w;
}

// Light a panel throws onto what is in front of it: 1 at the face, falling
// off with distance past its edges and away from it.
float panSpill(vec3 p, vec3 C, vec3 R, vec3 U, vec3 N, vec2 H, float L)
{
	if (H.x <= 0.0)
		return 0.0;
	vec3 l = panLocal(p, C, R, U, N);
	if (l.z < 0.0)
		return 0.0;
	vec2 e = max(abs(l.xy) - H, 0.0);
	return max(L, 0.0) * exp(-dot(e, e) * 0.8 - l.z * 0.9);
}
