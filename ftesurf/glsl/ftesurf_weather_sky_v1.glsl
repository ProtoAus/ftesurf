!!ver 110
!!samps bolt=0
// P1309: actual sky-portal geometry only. One static sparse alpha fork fetch,
// only during a0.12s pulse. No scene/capture/light or procedural pixel noise.
#include "sys/defs.h"
varying vec3 cone;
#ifdef VERTEX_SHADER
void main()
{
	vec3 d = v_position.xyz - e_eyepos;
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
	vec2 tc = cone.xy / max(1.0, cone.z) * vec2(0.8, -0.8) + vec2(0.5, 0.9);
	float bolt = texture2D(s_bolt, tc).a * step(1.0, cone.z);
	gl_FragColor = vec4(vec3(1.0 + bolt * 2.2), e_colourident.a);
}
#endif
