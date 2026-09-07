!!samps refract=0

//	FTESurf Patch 210 -- the linked_portal_door aperture, drawn as itself.
//
//	This is the answer to "it's a square box, and not the size of the doorway ...
//	you can't just fill the plane?"  Yes: the far side of the portal is rendered
//	into a texture by GLBE_GenerateBatchTextures, and this program paints that
//	texture onto the doorway quad.  Nothing outside the quad is touched, so the
//	rectangle, the corner leak at a yawed door, and the need for a scissor all
//	stop existing rather than being approximated away.
//
//	s_refract is $refraction, which for a SHADER_HASPORTAL material is not a
//	refraction at all -- it is the scene as seen from the far side of the link,
//	rendered with the same projection as this view.  That is the whole reason the
//	lookup below is a plain screen-space one and not a UV lookup: the far view was
//	rasterised into the same screen positions the aperture occupies, so the
//	fragment's own position on screen IS its texture coordinate.  Any tcgen here
//	would be wrong, and would put the far room on the door like wallpaper.
//
//	The projection is done in the fragment shader from an interpolated clip-space
//	position rather than from gl_FragCoord, so that it stays correct when the FBO
//	is a different size from the framebuffer.  portalfboscale is 1 in
//	ftesurf/scripts/portal.shader, but r_refractreflect_scale defaults to 0.5 and
//	is the fallback if that line is ever dropped -- with the divide by w this
//	simply gets softer, instead of being offset.
//
//	No fog: fog is applied by the recursed scene, in the FBO, at the correct
//	distances for the far room.  Applying it again here would fog the far room by
//	its distance from the DOOR, which is nearly zero.
//
//	No alpha: a portal is opaque.  The .1 alpha is written so nothing downstream
//	that reads destination alpha sees a hole here.

#include "sys/defs.h"

varying vec4 tf;

#ifdef VERTEX_SHADER
void main (void)
{
	tf = ftetransform();
	gl_Position = tf;
}
#endif

#ifdef FRAGMENT_SHADER
void main (void)
{
	//perspective divide to normalised device coords, then to 0..1 texture space.
	vec2 stc = (1.0 + (tf.xy / tf.w)) * 0.5;

	//the FBO is CLAMP_TO_EDGE, so this only matters for the half-pixel a
	//polygon edge can land outside the viewport at; clamping keeps that
	//from wrapping to the far side of the far room.
	stc = clamp(stc, 0.0, 1.0);

	gl_FragColor = vec4(texture2D(s_refract, stc).rgb, 1.0);
}
#endif
