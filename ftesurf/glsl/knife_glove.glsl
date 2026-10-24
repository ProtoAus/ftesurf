!!ver 100 150
!!permu SKELETAL
!!samps 1

#include "sys/defs.h"
varying vec2 glove_uv;
varying vec3 glove_light;
#ifdef VERTEX_SHADER
#include "sys/skeletal.h"
void main()
{
	vec3 w, n, s, t;
	gl_Position = skeletaltransform_wnst(w, n, s, t);
	glove_uv = v_texcoord;
	float incidence = max(0.0, dot(normalize(n), e_light_dir));
	glove_light = clamp(e_light_ambient + incidence * e_light_mul, vec3(0.65), vec3(1.2));
}
#endif
#ifdef FRAGMENT_SHADER
void main()
{
	// Installed AO preserves the template's seams without pretending to be an
	// inventory paint kit. Neutral matte leather, no borrowed colour texture.
	float ao = texture2D(s_t0, glove_uv).r;
	vec3 leather = vec3(0.20, 0.22, 0.24) * (0.18 + 0.82 * ao);
	gl_FragColor = vec4(leather * glove_light, 1.0);
}
#endif
