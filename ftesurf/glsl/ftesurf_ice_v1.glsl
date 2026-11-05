!!ver 110
!!permu FOG
!!samps noise=0
!!cvarf r_weather_ice_shine=0.12
// P1309: one static world-space liquid mesh, one baked noise/crack fetch.
// A view-dependent highlight only: no reflection/scene/depth capture or light.
#include "sys/defs.h"
#include "sys/fog.h"
varying vec3 pos;
varying vec3 norm;
varying float lava;
#ifdef VERTEX_SHADER
void main()
{
	pos = (m_model * vec4(v_position.xyz, 1.0)).xyz;
	norm = mat3(m_model[0].xyz, m_model[1].xyz, m_model[2].xyz) * v_normal;
	lava = v_texcoord.x;
	gl_Position = ftetransform();
}
#endif
#ifdef FRAGMENT_SHADER
void main()
{
	vec2 field = texture2D(s_noise, pos.xy * (1.0 / 256.0)).rg;
	vec3 n = normalize(norm);
	vec3 view = normalize(e_eyepos - pos);
	float rim = 1.0 - max(0.0, dot(n, view));
	rim *= rim; rim *= rim;
	float shine = max(0.0, dot(n, normalize(view + vec3(0.24, 0.36, 0.9))));
	shine *= shine; shine *= shine; shine *= shine; shine *= shine; shine *= shine;
	float cracks = smoothstep(0.35, 0.8, field.g);
	vec3 cold = vec3(0.46, 0.65, 0.76) * (0.8 + 0.2 * field.r) + cracks * 0.13;
	// Warm cracks plus lower opacity keep lava recognisable as a hazard.
	vec3 hot = mix(cold * 0.8, vec3(0.8, 0.22, 0.055), cracks);
	vec3 colour = mix(cold, hot, step(0.5, lava));
	colour += (rim * 0.14 + shine * 0.18) * clamp(cvar_r_weather_ice_shine, 0.0, 1.0);
	float alpha = mix(0.66, 0.42, step(0.5, lava)) + rim * 0.1;
	gl_FragColor = fog4(vec4(colour, alpha * e_colourident.a));
}
#endif
