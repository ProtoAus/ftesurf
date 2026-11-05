!!ver 110
!!samps roof=0 grain=1
// P1319: opaque snow cover. A distinct runtime material is registered BEFORE
// IQM precache, so its missing default material cannot poison this shader name.
#include "sys/defs.h"
varying vec2 roofuv, grainuv;
varying float height, shade;
#ifdef VERTEX_SHADER
void main()
{
	roofuv = v_texcoord;
	grainuv = v_position.xy * (1.0 / 64.0);
	height = v_position.z;
	shade = 0.82 + 0.18 * abs(v_normal.z);
	gl_Position = ftetransform();
}
#endif
#ifdef FRAGMENT_SHADER
void main()
{
#ifndef GRASS
	vec2 roofdata = texture2D(s_roof, roofuv).rg;
	float roof = float(ZBASE) + dot(roofdata, vec2(65280.0, 255.0)) * (float(ZRANGE) / 65535.0);
	if (height + 3.0 < roof) discard;
#endif
	float grain = texture2D(s_grain, grainuv).r;
	vec3 snow = mix(vec3(0.82, 0.89, 0.96), vec3(0.97, 0.98, 1.0), grain);
	gl_FragColor = vec4(snow * shade * e_colourident.rgb, 1.0);
}
#endif
