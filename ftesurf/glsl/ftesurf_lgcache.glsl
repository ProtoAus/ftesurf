!!ver 110
!!samps k=0 w=1

// FTESurf Patch 837: the HUD graph's cached still layer (cl_linegraph.qc, LineGraph_CacheDraw).
// k was drawn over black and w over white, so k is the colour the layer adds and w - k how much
// of what is behind it shows through, whatever blends drew it. The output is premultiplied, for
// blendfunc gl_one gl_one_minus_src_alpha.

#include "sys/defs.h"

varying vec2 tc;

#ifdef VERTEX_SHADER
void main()
{
	tc = v_texcoord;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
void main()
{
	vec3 k = texture2D(s_k, tc).rgb;
	vec3 w = texture2D(s_w, tc).rgb;
	gl_FragColor = vec4(k, 1.0 - clamp(dot(w - k, vec3(1.0 / 3.0)), 0.0, 1.0));
}
#endif
