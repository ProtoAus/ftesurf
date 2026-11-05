!!ver 110
!!samps bolt=0 cloud=1
// P1315: permanent, portal-clipped storm clouds plus brief fork/flash. Two small
// tiling-noise samples; bolt fetched only during a flash. No RT/light/shadow pass.
#include "sys/defs.h"
varying vec3 cone;
varying vec2 cloudtc;
#ifdef VERTEX_SHADER
void main()
{
	vec3 d = v_position.xyz - e_eyepos;
	vec3 ray = normalize(d);
	cloudtc = ray.xy * 1.7 + vec2(e_time * 0.004, e_time * 0.001);
	float phase = mod(floor(e_time * 0.125), 4.0);
	vec2 axis = phase < 1.0 ? vec2(1.0, 0.0) :
		phase < 2.0 ? vec2(0.0, 1.0) :
		phase < 3.0 ? vec2(-1.0, 0.0) : vec2(0.0, -1.0);
	cone = vec3(dot(d.xy, vec2(-axis.y, axis.x)), d.z, dot(d.xy, axis));
	gl_Position = ftetransform();
}
#endif
#ifdef FRAGMENT_SHADER
void main()
{
	float cloud = texture2D(s_cloud, cloudtc).r;
	cloud = cloud * 0.65 + texture2D(s_cloud, cloudtc * 2.1 - vec2(e_time * 0.002, 0.0)).r * 0.35;
	vec3 colour = mix(vec3(0.12, 0.16, 0.23), vec3(0.34, 0.40, 0.49), smoothstep(0.30, 0.72, cloud));
	float flash = clamp((e_colourident.a - 0.65) / 0.35, 0.0, 1.0);
	if (flash > 0.001)
	{
		vec2 tc = cone.xy / max(1.0, cone.z) * vec2(0.8, -0.8) + vec2(0.5, 0.9);
		float bolt = texture2D(s_bolt, tc).a * step(1.0, cone.z);
		colour += vec3(0.65 + bolt * 2.0) * flash;
	}
	gl_FragColor = vec4(colour, 0.72 + flash * 0.25);
}
#endif
