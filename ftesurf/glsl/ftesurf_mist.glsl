!!ver 110
!!permu FOG
!!samps noise=0
// P1302: 12 GPU-opened wisps per entity. No simulation, depth capture, dynamic
// lights, scene sampling or raymarch. cl_winter.qc caps distance/area/4 fields.
#include "sys/defs.h"
#include "sys/fog.h"
varying vec2 tc;
varying vec2 noiseoff;
varying float fade;
#ifdef VERTEX_SHADER
void main()
{
	float seed = dot(v_position.xyz, vec3(3.7, 5.1, 8.3));
	vec3 p = v_position.xyz;
	p.x += sin(e_time * 0.17 + seed) * 0.12;
	p.y += cos(e_time * 0.13 + seed) * 0.12;
	p.z += sin(e_time * 0.11 + seed) * 0.08;
	vec4 vp = m_modelview * vec4(p, 1.0);
	float scale = length(m_model[0].xyz);
	// Smoothly disappear before a puff can fill the lens. Never grow to screen size.
	fade = smoothstep(160.0, 280.0, length(vp.xyz));
	fade *= 1.0 - smoothstep(900.0, 1100.0, length(vp.xyz));
	vp.xy += (v_texcoord - 0.5) * scale * 0.6;
	tc = v_texcoord;
	noiseoff = vec2(seed * 0.13 + e_time * 0.012, seed * 0.27 - e_time * 0.009);
	gl_Position = m_projection * vp;
}
#endif
#ifdef FRAGMENT_SHADER
void main()
{
	vec2 q = (tc - 0.5) * 2.0;
	float edge = max(0.0, 1.0 - dot(q, q));
	float n = texture2D(s_noise, tc * 1.7 + noiseoff).r;
	n *= texture2D(s_noise, tc * 3.1 - noiseoff * 0.7).r;
	float a = edge * edge * smoothstep(0.12, 0.38, n) * fade * 0.11;
	gl_FragColor = fog4(vec4(e_colourident.rgb, a * e_colourident.a));
}
#endif
