!!ver 130
!!permu FOG
!!samps mask=0
!!cvarf r_snow_range
!!cvarf r_snow_speed
!!cvarf r_snow_size
!!cvarf r_snow_density
!!cvarf r_snow_alpha
!!cvarf r_snow_sway
!!cvar3f r_snow_wind
!!cvar3f r_snow_colour
!!cvar3f r_snow_maskxy
!!cvar3f r_snow_maskz
!!cvarf r_snow_debug

// FTESurf P1286: the snow event's flakes. models/snow/flakes.iqm is seeds only (tools/snowflakes.py):
// each flake is one position and three corners. Here it falls, sways and drifts by e_time, wraps into a
// box round e_origin (cl_snow.qc keeps the entity on the eye), and its corners open into a
// camera-facing triangle that holds the round flake -- no CPU per flake. The sky mask
// (tools/snowmask.py) holds, per cell, the top of the highest solid under the sky, 16 bits in r (high)
// and g (low): a flake below it is under a roof.

#include "sys/defs.h"
#include "sys/fog.h"

varying vec2 tc;
varying float fade;
varying float maskv;

uniform float cvar_r_snow_range;
uniform float cvar_r_snow_speed;
uniform float cvar_r_snow_size;
uniform float cvar_r_snow_density;
uniform float cvar_r_snow_alpha;
uniform float cvar_r_snow_sway;
uniform vec3 cvar_r_snow_wind;
uniform vec3 cvar_r_snow_colour;
uniform vec3 cvar_r_snow_maskxy;	// x0 y0 and the cell's size; a 3f, as !!cvar4f uploads 3 (gl_backend.c SP_CVAR4F)
uniform vec3 cvar_r_snow_maskz;		// z of value 0, z range of 65535, 1 when a mask is bound
uniform float cvar_r_snow_debug;		// 1: a flake shows the mask value it read (white = high roof)

#ifdef VERTEX_SHADER
float hash(vec3 p)
{
	return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453);
}

void main()
{
	vec3 seed = v_position.xyz * (1.0 / 2048.0) + 0.5;
	vec3 rnd = vec3(hash(seed), hash(seed.yzx + 3.1), hash(seed.zxy + 7.7));
	vec3 box = vec3(2.0, 2.0, 1.0) * max(cvar_r_snow_range, 64.0);
	float t = e_time;
	float ph = rnd.y * 6.2832;
	vec3 s = seed * box + cvar_r_snow_wind * t;
	s.z -= t * cvar_r_snow_speed * (0.7 + 0.6 * rnd.x);
	s.x += sin(t * (0.6 + rnd.z) + ph) * cvar_r_snow_sway;
	s.y += cos(t * (0.5 + rnd.x) + ph) * cvar_r_snow_sway;
	vec3 local = mod(s - e_origin, box) - box * 0.5;
	vec3 world = e_origin + local;

	maskv = 0.0;
	float a = 1.0 - smoothstep(0.6, 1.0, length(local.xy) / (box.x * 0.5));
	a *= 1.0 - smoothstep(0.7, 1.0, abs(local.z) / (box.z * 0.5));
	a *= step(rnd.z, cvar_r_snow_density);
	if (cvar_r_snow_maskz.z > 0.0)
	{
		ivec2 cl = ivec2(floor((world.xy - cvar_r_snow_maskxy.xy) / max(cvar_r_snow_maskxy.z, 1.0)));
		ivec2 ms = textureSize(s_mask, 0);
		if (cl.x >= 0 && cl.y >= 0 && cl.x < ms.x && cl.y < ms.y)
		{
			vec4 m = texelFetch(s_mask, cl, 0);
			float h = cvar_r_snow_maskz.x + (m.r * 65280.0 + m.g * 255.0) * (1.0 / 65535.0) * cvar_r_snow_maskz.y;
			maskv = (m.r * 65280.0 + m.g * 255.0) * (1.0 / 65535.0);
			if (cvar_r_snow_debug == 0.0)
				a *= step(h, world.z);
		}
	}
	vec4 vp = m_modelview * vec4(local, 1.0);
	a *= smoothstep(12.0, 48.0, length(vp.xyz));	// a flake at the lens would fill the screen
	fade = a * cvar_r_snow_alpha;
	tc = v_texcoord;
	vp.xy += (v_texcoord - 0.5) * (a > 0.0 ? cvar_r_snow_size * (0.6 + 0.8 * rnd.y) : 0.0);
	gl_Position = m_projection * vp;
}
#endif

#ifdef FRAGMENT_SHADER
void main()
{
	float a = fade * (1.0 - smoothstep(0.3, 1.0, length(tc - 0.5) * 2.0));
	if (a <= 0.004)
		discard;
	gl_FragColor = fog4blend(vec4(cvar_r_snow_debug != 0.0 ? vec3(maskv) : cvar_r_snow_colour, a));
}
#endif
