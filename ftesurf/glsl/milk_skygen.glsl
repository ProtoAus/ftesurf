!!ver 130 150
!!samps prev=0 spec=1

// Patch 467 -- the sky's seed image, 2D.  glsl/milk_sky.glsl maps the zenith
// (and, mirrored, the nadir) to the centre and the horizon to the ring r = HOR,
// so looking level -- which is most of a surf run -- reads the ring.  Content
// therefore covers the whole disc and the horizon gets the loudest element:
//   nebula    a slow palette field everywhere, so the sky is never black
//   fractal   Kali's iterated inversion across the dome, slowly turning
//   rays      god rays from the zenith, swelling with the mids
//   skyline   the spectrum as bars standing on the horizon, pointing up
//   core      bass pulse at the zenith, and a ring seeded on every beat
//   streaks   radial lines toward the horizon, brighter with speed (M_EVENT.z)
//   shock     a ring launched by a landing (M_FOCUS.z = radius)
// The warp pours all of it outward each tick; milk_warp.glsl's SKY injection
// is scaled by (1 - decay), so static parts hold a steady level.

#include "sys/defs.h"
#include "glsl/milk_common.h"

#define HOR 0.88            // 2 * K in milk_sky.glsl

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
	vec4 AU = M_AUDIO * M_FOCUS.w;
	vec4 AA = M_AUDIOATT * M_FOCUS.w;
	float spd = M_EVENT.z;
	float hue = M_LOOK.x;

	vec2 p = (tc - 0.5) * 2.0;
	float r = length(p);
	float a = atan(p.y, p.x);
	float el = clamp(1.0 - r / HOR, 0.0, 1.0);      // 0 horizon .. 1 zenith

	vec3 q = vec3(p * 1.3, T * 0.015);
	float n = vnoise(q * 2.2) * 0.6 + vnoise(q * 5.1 + 7.0) * 0.4;
	vec3 col = milk_pal(hue + n * 0.45 + el * 0.25) * (0.05 + 0.16 * n * n) * (0.55 + 0.45 * el);

	vec2 z = rot2(T * 0.035 + spd * 0.4) * p * (1.25 - 0.12 * AA.x);
	float acc = 0.0;
	for (int i = 0; i < 7; i++)
	{
		z = abs(z) / max(dot(z, z), 0.02) - vec2(0.78 + 0.04 * sin(T * 0.11), 0.61 + 0.03 * cos(T * 0.07));
		acc += exp(-abs(length(z) - 1.0) * 7.0);
	}
	col += milk_pal(hue + acc * 0.09 + T * 0.01) * acc * 0.10 * (0.7 + 0.7 * AA.y) * smoothstep(1.0, 0.75, r);

	// God rays from the zenith, slowly turning, swelling with the mids.
	float rays = pow(0.5 + 0.5 * sin(a * 9.0 + T * 0.12 + n * 2.5), 10.0)
	           * smoothstep(0.02, 0.30, r) * smoothstep(HOR, 0.35, r);
	col += milk_pal(hue + 0.2 + r * 0.3) * rays * (0.10 + 0.30 * AA.y);

	// Skyline: mirrored left/right so the two halves meet without a seam.
	float u = abs(a) / PI;
	const float nb = 72.0;
	float bi = floor(u * nb);
	float sv = texture2D(s_spec, vec2(0.03 + (bi + 0.5) / nb * 0.85, 0.25)).r;
	float gap = step(0.22, fract(u * nb));
	float top = HOR - (0.03 + sv * 0.45);
	float bar = gap * step(top, r) * step(r, HOR);
	col += milk_pal(hue + 0.30 + u * 0.4) * bar * (0.25 + 1.1 * sv) * (0.6 + 0.4 * smoothstep(top, HOR, r));
	col += milk_pal(hue + 0.45) * exp(-abs(r - HOR) * 70.0) * (0.25 + 0.9 * AA.x);

	col += milk_pal(hue + 0.05) * exp(-r * r * 70.0) * (0.35 + 1.3 * AA.w + 0.7 * AU.x);
	col += milk_pal(hue + 0.15) * smoothstep(0.012, 0.0, abs(r - 0.07)) * AA.w * 1.6;

	float lane = hash11(floor(a / TAU * 110.0));
	float streak = step(0.75, lane) * smoothstep(0.25, 0.8, r) * smoothstep(HOR + 0.02, HOR - 0.05, r)
	             * (0.5 + 0.5 * sin(T * (3.0 + lane * 7.0) + lane * 40.0));
	col += milk_pal(hue + 0.6) * streak * spd * spd * 0.5;

	float shock = M_FOCUS.z;
	if (shock > 0.0)
		col += milk_pal(hue + 0.9) * smoothstep(0.02, 0.0, abs(r - shock)) * (1.4 - shock);

	vec2 sg = p * 95.0;
	float h = hash12(floor(sg));
	if (h > 0.986)
	{
		vec2 f = fract(sg) - 0.5;
		col += vec3(0.75, 0.82, 1.0) * exp(-dot(f, f) * 45.0) * (0.35 + 0.35 * sin(T * 3.0 + h * 90.0) + 0.5 * AU.z);
	}

	gl_FragColor = vec4(col, 1.0);
}
#endif
