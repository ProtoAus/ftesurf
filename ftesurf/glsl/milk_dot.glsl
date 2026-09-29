!!ver 130 150
!!samps 1

// Patch 467 -- soft additive sprites drawn INTO the feedback frame (MilkDrop's
// shapes and dot-mode waves).  The warp then smears them, so a mote becomes a
// streak and the menu highlight leaves a ghost when the selection moves.
// Colour arrives per vertex (R_PolygonVertex rgb, alpha); nothing is sampled.
//   default  round falloff over texcoords 0..1
//   #BAR     soft-edged capsule, for the highlight under a menu row
//   #FLAT    vertex colour as-is -- the menu's readability gradient
//   #CLEAR   transparent black, unblended -- wipes a panel's UI target

#include "sys/defs.h"

varying vec2 tc;
varying vec4 vc;

#ifdef VERTEX_SHADER
void main(void)
{
	tc = v_texcoord;
	vc = v_colour;
	gl_Position = ftetransform();
}
#endif

#ifdef FRAGMENT_SHADER
void main(void)
{
	vec2 d = tc * 2.0 - 1.0;
#ifdef CLEAR
	gl_FragColor = vec4(0.0);
	return;
#endif
#ifdef FLAT
	// Plain vertex colour and alpha, for gradients (blendfunc blend).
	gl_FragColor = vc;
	return;
#endif
#ifdef BAR
	// texcoord .x runs along the bar, .y across; ends fade over the last 15%.
	float a = (1.0 - smoothstep(0.70, 1.0, abs(d.x))) * exp(-d.y * d.y * 3.5);
#else
	float r2 = dot(d, d);
	float a = exp(-r2 * 5.0) * (1.0 - smoothstep(0.8, 1.0, r2));
#endif
	gl_FragColor = vec4(vc.rgb * vc.a * a, 1.0);
}
#endif
