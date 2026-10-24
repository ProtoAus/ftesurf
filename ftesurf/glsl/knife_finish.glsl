!!ver 100 150
!!permu FRAMEBLEND
!!permu SKELETAL
!!permu FOG
!!samps 3
!!cvarf cl_knife_seed
!!cvarf cl_knife_scale
!!cvarf cl_knife_rotation
!!cvarf cl_knife_fade
!!cvarf cl_knife_wear
#include "sys/defs.h"

varying vec2 knife_uv;
varying vec3 knife_light;
varying float knife_blade;
#ifdef VERTEX_SHADER
#include "sys/skeletal.h"
void main()
{
	vec3 w, n, s, t;
	gl_Position = skeletaltransform_wnst(w, n, s, t);
	knife_uv = v_texcoord;
	// The original two previews keep their measured bind-space blade axes.
	// Other installed shapes use their authored UVs, never a different knife's axis.
#if FAMILY == 1
	knife_blade = (-v_position.y - 0.5) / 8.0;
#elif FAMILY == 2
	knife_blade = (v_position.z - 0.5) / 10.5;
#else
	knife_blade = knife_uv.x;
#endif
	float incidence = max(0.0, dot(normalize(n), e_light_dir));
	knife_light = clamp(e_light_ambient + (0.25 + 0.75 * incidence) * e_light_mul, vec3(0.55), vec3(1.25));
}
#endif
#ifdef FRAGMENT_SHADER
#include "sys/fog.h"
uniform float cvar_cl_knife_seed, cvar_cl_knife_scale, cvar_cl_knife_rotation;
uniform float cvar_cl_knife_fade, cvar_cl_knife_wear;
float knife_noise(vec2 p)
{
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}
void main()
{
	vec4 base = texture2D(s_t0, knife_uv);
	float mask = texture2D(s_t2, knife_uv).r;
	float seed = clamp(cvar_cl_knife_seed, 0.0, 1000.0);
	float scale = clamp(cvar_cl_knife_scale, 0.25, 4.0);
	float angle = radians(cvar_cl_knife_rotation);
	mat2 rotation = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
	vec2 shift = seed < 0.5 ? vec2(0.0) : vec2(knife_noise(vec2(seed, 1.0)), knife_noise(vec2(seed, 2.0))) - 0.5;
	vec2 uv = rotation * (knife_uv - 0.5) * scale + 0.5 + shift;
#if STYLE == 1
	float along = (rotation * vec2(knife_blade - 0.5, knife_uv.y - 0.5)).x * scale + 0.5 + shift.x * 0.15;
	float fade = clamp(along * clamp(cvar_cl_knife_fade, 0.0, 1.0), 0.0, 1.0);
	// The Source fade texture contains palette weights, not final RGB colours.
	vec3 weights = texture2D(s_t1, vec2(mix(0.16, 0.84, fade), 0.5)).rgb;
	vec3 paint = (weights.r * vec3(1.0, 0.60, 0.12) + weights.g * vec3(1.0, 0.12, 0.48)
		+ weights.b * vec3(0.43, 0.18, 1.0)) / max(0.001, weights.r + weights.g + weights.b);
#elif STYLE == 2
	float web = dot(texture2D(s_t1, uv).rgb, vec3(0.333333));
	vec3 paint = mix(vec3(0.55, 0.035, 0.025), vec3(0.015), smoothstep(0.1, 0.7, web));
#else
	vec3 layers = texture2D(s_t1, uv).rgb;
	vec3 paint = layers.r * vec3(0.85, 0.05, 0.06) + layers.g * vec3(1.0, 0.70, 0.08)
		+ layers.b * vec3(0.04, 0.16, 0.75);
#endif
	float wear = clamp(cvar_cl_knife_wear, 0.0, 1.0);
	float grain = knife_noise(floor(knife_uv * vec2(620.0, 480.0)) + seed);
	float scratch = knife_noise(floor(knife_uv * vec2(1700.0, 90.0)) + seed);
	float threshold = 1.0 - wear * 0.85;
	float exposed = wear * smoothstep(threshold - 0.05, threshold + 0.05, grain * 0.55 + scratch * 0.45);
	float coverage = mask * (1.0 - exposed);
	vec3 colour = mix(base.rgb, paint * (0.8 + base.rgb * 0.2), coverage);
	gl_FragColor = fog4(vec4(colour * knife_light, 1.0));
}
#endif
