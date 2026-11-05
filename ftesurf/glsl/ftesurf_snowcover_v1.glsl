!!ver 110
!!samps roof=0 grain=1
// P1317 map-specific static terrain: fine32 roof clip for exposed caps, opaque
// white material replacement on actual grass. No capture/shadow/light pass.
#ifndef ZBASE
#define ZBASE -32768.0
#endif
#ifndef ZRANGE
#define ZRANGE 65536.0
#endif
#include "sys/defs.h"
varying vec2 roofuv;
varying vec2 grainuv;
varying float height;
varying float shade;
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
	vec2 packed = texture2D(s_roof, roofuv).rg;
	float top = float(ZBASE) + dot(packed, vec2(65280.0, 255.0)) / 65535.0 * float(ZRANGE);
	if (height + 3.0 < top) discard;
#endif
	float grain = texture2D(s_grain, grainuv).r;
	gl_FragColor = vec4(vec3(0.88, 0.93, 1.0) * (0.87 + grain * 0.13) * shade, 1.0);
}
#endif
