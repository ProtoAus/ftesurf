!!ver 110
!!samps roof=0 snow=1
// P1327: mounted Source snow albedo + baked per-vertex map light, not fullbright.
// Roof data stays point-sampled; the actual snow texture retains ordinary mips.
#include "sys/defs.h"
varying vec2 roofuv, snowuv;
varying float height;
varying vec3 maplight;
#ifdef VERTEX_SHADER
void main()
{
	roofuv = v_texcoord;
	snowuv = v_position.xy * (1.0 / 128.0);
	if (abs(v_normal.z) < 0.5)
		snowuv = abs(v_normal.x) > abs(v_normal.y) ? v_position.yz * (1.0 / 128.0) : v_position.xz * (1.0 / 128.0);
	height = v_position.z;
	maplight = v_colour.rgb;
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
	vec3 albedo = texture2D(s_snow, snowuv).rgb;
	gl_FragColor = vec4(albedo * maplight * e_colour.rgb, 1.0);
}
#endif
